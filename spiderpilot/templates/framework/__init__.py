"""SpiderPilot Framework

AI 生成的爬虫使用此框架来获得统一的下载、解析、字段提取能力。

用法（AI 生成的爬虫代码示例）:

    from spider_framework.base_spider import BaseSpider

    class EmpikSpider(BaseSpider):
        name = "empik"
        fingerprint = "chrome120"

        field_spec = {
            "title": {"source": "json_response", "path": "$.data.title"},
        }

        def parse(self, response):
            data = response.json()
            yield self.extract_fields(data)
"""

from .base_spider import BaseSpider
from .downloader import Downloader
from .helpers import json_path, normalize, safe_get, extract_product_id

__all__ = [
    "BaseSpider",
    "Downloader",
    "json_path",
    "normalize",
    "safe_get",
    "extract_product_id",
]
