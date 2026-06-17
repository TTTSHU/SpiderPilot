"""
SpiderPilot Framework — 下载器

基于 curl_cffi 的下载器，支持 TLS 指纹伪装和代理轮换。
AI 生成的爬虫不需要关心下载细节。
"""

from __future__ import annotations

import logging
import os
import random
from collections import deque
from typing import Any

from curl_cffi import requests as curl_requests

logger = logging.getLogger(__name__)

DEFAULT_PROXY_FILE = "ips.txt"

# 已知的 TLS 指纹版本
FINGERPRINTS = {
    "chrome120": "chrome120",
    "chrome110": "chrome110",
    "chrome107": "chrome107",
    "chrome99": "chrome99",
    "safari15_5": "safari15_5",
    "firefox117": "firefox117",
    "edge101": "edge101",
}


def load_proxy_list(proxy_file: str = DEFAULT_PROXY_FILE) -> list[str]:
    """从文件加载代理列表。格式: ip:port:user:pass 或 ip:port。"""
    proxies = []
    if not os.path.exists(proxy_file):
        # 尝试当前目录、上级目录
        for alt in [
            os.path.join(os.path.dirname(__file__), proxy_file),
            os.path.join(os.path.dirname(__file__), "..", proxy_file),
            os.path.join(os.path.dirname(__file__), "..", "..", proxy_file),
        ]:
            if os.path.exists(alt):
                proxy_file = alt
                break
        else:
            logger.warning("代理文件不存在: %s，将直连", proxy_file)
            return []

    try:
        with open(proxy_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(":")
                if len(parts) == 4:
                    ip, port, user, passwd = parts
                    proxies.append(f"http://{user}:{passwd}@{ip}:{port}")
                elif len(parts) == 2:
                    ip, port = parts
                    proxies.append(f"http://{ip}:{port}")
    except Exception as e:
        logger.warning("加载代理失败: %s", e)

    logger.info("加载 %d 条代理", len(proxies))
    return proxies


class Downloader:
    """
    通用下载器。

    用法:
        dl = Downloader(fingerprint="chrome120", proxy_file="ips.txt")
        resp = dl.get("https://example.com")
        resp = dl.post("https://api.example.com", json={"key": "val"})
        resp = dl.graphql("https://api.example.com/graphql", query="...", variables={...})

    Session 会自动复用，代理自动轮换。
    """

    def __init__(
        self,
        fingerprint: str = "chrome120",
        proxy_file: str | None = DEFAULT_PROXY_FILE,
        max_sessions: int = 10,
        timeout: int = 30,
    ):
        self.fingerprint = FINGERPRINTS.get(fingerprint, fingerprint)
        self.timeout = timeout
        self.proxy_list = load_proxy_list(proxy_file) if proxy_file else []
        self.max_sessions = max_sessions
        self._pool: deque[dict[str, Any]] = deque()

    def _get_session(self):
        """从池中获取或创建 session。"""
        if self._pool:
            return self._pool.pop()
        return {
            "session": curl_requests.Session(
                impersonate=self.fingerprint, verify=False
            ),
            "proxy": self._random_proxy(),
        }

    def _return_session(self, session_info: dict):
        if len(self._pool) < self.max_sessions:
            self._pool.append(session_info)

    def _random_proxy(self) -> dict[str, str] | None:
        if not self.proxy_list:
            return None
        proxy = random.choice(self.proxy_list)
        return {"http": proxy, "https": proxy}

    def _build_headers(self, extra: dict | None = None) -> dict:
        h = {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        if extra:
            h.update(extra)
        return h

    def get(
        self,
        url: str,
        headers: dict | None = None,
        proxy: str | None = None,
        timeout: int | None = None,
    ):
        """GET 请求。"""
        si = self._get_session()
        session = si["session"]
        proxies = {"http": proxy, "https": proxy} if proxy else si["proxy"]
        try:
            resp = session.get(
                url,
                headers=self._build_headers(headers),
                proxies=proxies,
                timeout=timeout or self.timeout,
            )
            return resp
        finally:
            self._return_session(si)

    def post(
        self,
        url: str,
        json: dict | None = None,
        data: str | bytes | None = None,
        headers: dict | None = None,
        proxy: str | None = None,
        timeout: int | None = None,
    ):
        """POST 请求。"""
        si = self._get_session()
        session = si["session"]
        proxies = {"http": proxy, "https": proxy} if proxy else si["proxy"]
        try:
            h = self._build_headers(headers)
            h.setdefault("content-type", "application/json")
            resp = session.post(
                url,
                json=json,
                data=data,
                headers=h,
                proxies=proxies,
                timeout=timeout or self.timeout,
            )
            return resp
        finally:
            self._return_session(si)

    def graphql(
        self,
        url: str,
        query: str,
        variables: dict | None = None,
        operation_name: str | None = None,
        headers: dict | None = None,
        proxy: str | None = None,
        timeout: int | None = None,
    ):
        """
        GraphQL POST 请求。

        Args:
            url: GraphQL endpoint
            query: GraphQL query/mutation string
            variables: query variables
            operation_name: optional operation name
        """
        import json

        body = {"query": query}
        if variables:
            body["variables"] = variables
        if operation_name:
            body["operationName"] = operation_name

        return self.post(
            url,
            data=json.dumps(body, ensure_ascii=False),
            headers=headers,
            proxy=proxy,
            timeout=timeout,
        )

    def download(
        self,
        url: str,
        method: str = "GET",
        json: dict | None = None,
        data: str | bytes | None = None,
        headers: dict | None = None,
        proxy: str | None = None,
        timeout: int | None = None,
    ):
        """通用下载入口。"""
        method = method.upper()
        if method == "GET":
            return self.get(url, headers, proxy, timeout)
        if method == "POST":
            return self.post(url, json=json, data=data, headers=headers, proxy=proxy, timeout=timeout)
        raise ValueError(f"不支持的方法: {method}")
