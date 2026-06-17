"""SpiderPilot Framework — Scrapy 下载中间件

将框架的 Downloader 注入到 Scrapy 请求流程中。
"""

from __future__ import annotations

import logging

from scrapy.http import HtmlResponse, Response

logger = logging.getLogger(__name__)


class FrameworkDownloadMiddleware:
    """
    Scrapy 下载中间件。

    检查请求 meta 中是否有 download_method 标记，
    如果有则使用框架的 Downloader 而非 Scrapy 默认下载器。
    """

    def __init__(self):
        self._initialized = False

    @classmethod
    def from_crawler(cls, crawler):
        mw = cls()
        mw.crawler = crawler
        return mw

    def process_request(self, request, spider):
        """拦截请求，使用 curl_cffi Downloader 下载。"""
        downloader = getattr(spider, "downloader", None)
        if downloader is None:
            return None

        method = request.meta.get("download_method", "")
        if method not in ("curl_cffi", "requests", "framework"):
            return None

        try:
            resp = downloader.download(
                url=request.url,
                method=request.method,
                data=request.body,
                headers=dict(request.headers.to_unicode_dict()),
                proxy=request.meta.get("proxy"),
            )
            headers = dict(resp.headers)
            headers.pop("Content-Encoding", None)
            headers.pop("content-encoding", None)
            return HtmlResponse(
                url=resp.url,
                status=resp.status_code,
                headers=headers,
                body=resp.content,
                encoding=resp.encoding or "utf-8",
                request=request,
            )
        except Exception as e:
            logger.warning("下载中间件失败: %s", e)
            return Response(
                url=request.url,
                status=500,
                request=request,
                body=str(e).encode("utf-8"),
            )
