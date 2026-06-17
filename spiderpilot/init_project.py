"""Project initializer — copies framework template into a new project."""

from __future__ import annotations

import shutil
from pathlib import Path


FRAMEWORK_SRC = Path(__file__).resolve().parent / "templates" / "framework"

SCHEMAS_SRC = Path(__file__).resolve().parent / "templates" / "domains"


def init_project(
    name: str,
    target_dir: str | Path = ".",
    platform: str = "",
    template: str = "generic",
) -> Path:
    """
    创建新的爬虫项目。

    生成目录结构:
        {target_dir}/{name}/
        ├── spider_framework/     ← 框架代码
        │   ├── __init__.py
        │   ├── base_spider.py
        │   ├── downloader.py
        │   ├── helpers.py
        │   └── middleware.py
        ├── spiders/              ← AI 生成的爬虫放这里
        │   └── __init__.py
        ├── specs/                ← 任务 Spec YAML
        ├── ips.txt               ← 代理文件（空模板）
        ├── scrapy.cfg
        ├── settings.py
        └── requirements.txt
    """
    root = Path(target_dir).resolve() / name
    root.mkdir(parents=True, exist_ok=True)

    _copy_framework(root)
    _create_scrapy_config(root, name, platform, template)
    _create_readme(root, name)
    _create_placeholder_files(root)

    return root


def _copy_framework(root: Path):
    """复制框架模板到项目目录。"""
    dest = root / "spider_framework"
    if FRAMEWORK_SRC.exists():
        shutil.copytree(FRAMEWORK_SRC, dest, dirs_exist_ok=True)
        # 清理 __pycache__
        for pycache in dest.rglob("__pycache__"):
            shutil.rmtree(pycache, ignore_errors=True)


def _create_scrapy_config(root: Path, name: str, platform: str, template: str):
    """创建 Scrapy 配置文件。"""

    # scrapy.cfg
    (root / "scrapy.cfg").write_text(
        f"[settings]\ndefault = settings\n\n[deploy]\nproject = {name}\n",
        encoding="utf-8",
    )

    # settings.py
    (root / "settings.py").write_text(
        f'''"""Scrapy settings for {name}"""
BOT_NAME = "{name}"
SPIDER_MODULES = ["spiders"]
NEWSPIDER_MODULE = "spiders"

ROBOTSTXT_OBEY = False
CONCURRENT_REQUESTS = 8
DOWNLOAD_DELAY = 0.5
DOWNLOAD_TIMEOUT = 30

# curl_cffi 下载中间件
DOWNLOADER_MIDDLEWARES = {{
    "spider_framework.middleware.FrameworkDownloadMiddleware": 543,
}}

# Redis 队列（分布式部署时启用）
# SCHEDULER = "scrapy_redis.scheduler.Scheduler"
# DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
# REDIS_URL = "redis://localhost:6379"

# MongoDB Pipeline
# ITEM_PIPELINES = {{
#     "spider_framework.pipeline.MongoDBPipeline": 300,
# }}

LOG_LEVEL = "INFO"
''',
        encoding="utf-8",
    )

    # spiders/__init__.py
    spiders_dir = root / "spiders"
    spiders_dir.mkdir(exist_ok=True)
    (spiders_dir / "__init__.py").write_text(
        f"""# {name} — AI 生成的爬虫放这里

from spider_framework.base_spider import BaseSpider
from spider_framework.helpers import json_path, normalize, safe_get
""",
        encoding="utf-8",
    )

    # specs/ 目录
    specs_dir = root / "specs"
    specs_dir.mkdir(exist_ok=True)

    # specs/ 模板
    (specs_dir / "example.yaml").write_text(
        f"""# Example Spec for {name}
version: 1
name: "{name}_example"
platform: "{platform}"
target_type: "detail"
samples:
  - id: s1
    url: "https://..."
    expected:
      title:
        equals: "Example Title"
fields:
  title:
    type: string
    required: true
""",
        encoding="utf-8",
    )


def _create_readme(root: Path, name: str):
    (root / "README.md").write_text(
        f"""# {name}

SpiderPilot 爬虫项目。

## 目录结构

```
├── spider_framework/   # 框架基类（下载器/解析器/辅助函数）
├── spiders/            # AI 生成的爬虫代码
├── specs/              # 任务 Spec YAML
├── ips.txt             # 代理列表（格式: ip:port:user:pass）
├── scrapy.cfg
├── settings.py
└── requirements.txt
```

## 添加代理

编辑 `ips.txt`，每行格式：
```
ip:port:user:password
```

## 运行爬虫

```bash
cd {name}
scrapy crawl {name} -o results.json
```

## 需要 CodeWhale

AI 分析由 CodeWhale 驱动，不是 LLM API。
下载: https://codewhale.ai

## AI 工作流

1. 在 Web UI 创建任务，输入 URL，点「AI 分析」
2. 打开 CodeWhale 终端，说「处理 spiderpilot 待办」
3. CodeWhale 自动分析页面、推荐字段、生成爬虫
4. 刷新 Web UI 查看结果，爬虫代码在 `spiders/`
5. 直接运行爬虫
""",
        encoding="utf-8",
    )


def _create_placeholder_files(root: Path):
    """创建空文件模板。"""

    # ips.txt
    ips_path = root / "ips.txt"
    if not ips_path.exists():
        ips_path.write_text(
            "# 代理列表，格式: ip:port:user:password\n"
            "# 如: 192.168.1.1:8080:username:password\n"
        )

    # requirements.txt
    req_path = root / "requirements.txt"
    if not req_path.exists():
        req_path.write_text(
            "scrapy>=2.11\n"
            "scrapy-redis>=0.9\n"
            "curl-cffi>=0.14\n"
            "pymongo>=4.6\n"
        )
