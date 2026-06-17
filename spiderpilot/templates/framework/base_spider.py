"""
SpiderPilot Framework — BaseSpider 基类

AI 生成的爬虫继承此基类，只需声明 field_spec 和 chain 即可运行。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Generator

import scrapy
from scrapy.http import Response
from scrapy_redis.spiders import RedisSpider

from .downloader import Downloader
from .helpers import json_path, normalize, extract_product_id

logger = logging.getLogger(__name__)


class BaseSpider(RedisSpider):
    """
    标准化爬虫基类。

    子类必须定义:
      - name: str              爬虫名称
      - field_spec: dict        字段声明

    子类可选覆盖:
      - chain: list             多步请求链路
      - mode: str               模式 (single | multi_step | variant_chain)
      - fingerprint: str        TLS 指纹版本
      - proxy_file: str         代理文件
      - start_urls: list        初始 URL（不使用 Redis 队列时）

    示例:
        class MySpider(BaseSpider):
            name = "my_spider"
            fingerprint = "chrome120"

            field_spec = {
                "title": {"source": "json_response", "path": "$.data.title", "type": str, "required": True},
                "price": {"source": "json_response", "path": "$.data.price", "type": float, "normalize": "parse_price"},
            }

            start_urls = ["https://example.com/api/products"]

            def parse(self, response):
                data = response.json()
                yield self.extract_fields(data, self.field_spec)
    """

    name: str = ""
    field_spec: dict[str, dict] = {}

    # 可选覆盖
    mode: str = "single"                    # single | multi_step | variant_chain
    chain: list[dict] = []                  # 多步链路声明
    fingerprint: str = "chrome120"          # TLS 指纹
    proxy_file: str = "ips.txt"             # 代理文件
    handle_httpstatus_list = [200, 400, 403, 404, 429, 500, 502, 503]

    # 框架注入的下载器实例
    downloader: Downloader | None = None

    @classmethod
    def update_settings(cls, settings):
        super().update_settings(settings)
        # 使用 curl_cffi 下载中间件
        settings.set("DOWNLOADER_MIDDLEWARES", {
            "spider_framework.middleware.FrameworkDownloadMiddleware": 543,
        }, priority="spider")

    def make_request_from_data(self, data: bytes):
        """
        从 Redis 队列消费任务。

        子类通常不需要覆盖此方法。
        框架自动解析 JSON → 提取 URL/product_id → 调用 build_request。
        """
        try:
            payload = json.loads(data.decode() if isinstance(data, bytes) else data)
        except Exception:
            return None

        url = payload.get("url") if isinstance(payload, dict) else str(payload)
        product_id = payload.get("product_id") or payload.get("id") if isinstance(payload, dict) else None
        if not product_id and url:
            product_id = extract_product_id(url)

        return self._default_request(url, product_id, payload if isinstance(payload, dict) else {})

    def _default_request(self, url: str, product_id: str | None, context: dict):
        """框架默认的请求构建，子类可覆盖 build_request 来定制。"""
        if hasattr(self, "build_request"):
            return self.build_request(url, product_id, context)

        return scrapy.Request(
            url=url,
            callback=self.parse,
            errback=self._on_error,
            meta={"product_id": product_id, "source_url": url, "context": context},
        )

    def _on_error(self, failure):
        """请求失败回调，记录日志。子类可覆盖。"""
        logger.error("请求失败: %s", failure.request.url)
        if hasattr(self, "on_error"):
            self.on_error(failure)

    # ── 字段提取（框架自动处理）──

    def extract_fields(self, data: dict, field_spec: dict | None = None) -> dict:
        """
        从数据中按 field_spec 提取字段。

        Args:
            data: JSON 数据或 HTML Response
            field_spec: 字段声明（默认用 self.field_spec）

        Returns:
            {"field_name": value, ...}
        """
        spec = field_spec or self.field_spec
        item = {}
        for name, cfg in spec.items():
            value = self._extract_one(data, name, cfg)
            item[name] = value
        return item

    def _extract_one(self, data: Any, name: str, cfg: dict) -> Any:
        source = cfg.get("source", "json_response")
        path = cfg.get("path")
        fallback = cfg.get("fallback")
        normalize_method = cfg.get("normalize")

        value = None

        if source == "json_response" and isinstance(data, dict):
            value = json_path(data, path) if path else data
        elif source == "html_selector" and hasattr(data, "css"):
            value = data.css(path).get(default="") if path else ""
        elif source == "html_xpath" and hasattr(data, "xpath"):
            value = data.xpath(path).get(default="") if path else ""
        elif source == "json_doc" and isinstance(data, dict):
            value = json_path(data, path) if path else data
        elif source == "raw_text":
            value = str(data)

        if value is None and fallback is not None:
            value = fallback

        return normalize(value, normalize_method)

    def extract_list(self, data: dict, list_path: str, field_spec: dict) -> list[dict]:
        """
        从 JSON 数组中提取字段列表。

        用法:
            items = self.extract_list(data, "$.data.offers", {
                "offer_id": {"path": "$.offerId"},
                "price": {"path": "$.originalPrice", "normalize": "parse_price"},
            })
        """
        arr = json_path(data, list_path)
        if not isinstance(arr, list):
            return []
        results = []
        for item_data in arr:
            results.append(self.extract_fields(item_data, field_spec))
        return results

    # ── 链路方法（多步模式专用）──

    def build_chain_request(self, product_data: dict, step_index: int) -> scrapy.Request | None:
        """
        根据 chain 声明构建第 step_index 步的请求。

        chain 声明格式:
            {"name": "step_name", "url": "...", "method": "POST",
             "body_template": "...", "variables": {...}}
        """
        if step_index >= len(self.chain):
            return None

        step = self.chain[step_index]
        url = step["url"]
        method = step.get("method", "GET").upper()
        body = None
        headers = step.get("headers", {})
        headers.setdefault("content-type", "application/json")
        headers.setdefault("accept", "*/*")

        if "body_template" in step:
            tmpl = getattr(self, step["body_template"], step["body_template"])
            variables = step.get("variables", {})
            # 替换模板变量
            body_data = {"query": tmpl}
            for k, v in variables.items():
                if isinstance(v, str) and v.startswith("$"):
                    # $product_id 从 product_data 中取
                    key = v[1:]
                    body_data.setdefault("variables", {})[k] = product_data.get(key)
                else:
                    body_data.setdefault("variables", {})[k] = v

            body = json.dumps(body_data, ensure_ascii=False)

        return scrapy.Request(
            url=url,
            method=method,
            body=body,
            headers=headers,
            callback=self.parse,
            errback=self._on_error,
            meta={
                "stage": step.get("name"),
                "step_index": step_index,
                "product_data": product_data,
            },
        )

    def build_chain_field_spec(self, field_spec: dict, prefix: str):
        """
        为链路模式生成带前缀的 field_spec。

        用法:
            step_spec = self.build_chain_field_spec(self.field_spec,
                step_meta.get("stage", ""))
            item = self.extract_fields(data, step_spec)
        """
        return {
            f"{prefix}_{name}": {**cfg, "source": cfg.get("source", "json_response")}
            for name, cfg in field_spec.items()
        }

    # ── 生命周期钩子 ──

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        spider.downloader = Downloader(
            fingerprint=getattr(spider, "fingerprint", "chrome120"),
            proxy_file=getattr(spider, "proxy_file", "ips.txt"),
        )
        return spider
