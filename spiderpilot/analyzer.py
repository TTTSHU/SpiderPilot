"""页面自动分析引擎 — 触发后直接在后台运行。"""

from __future__ import annotations

import json
import re
import threading

from spiderpilot.store import (
    append_think, save_analysis, save_raw_html, update_status,
    get_task,
)


def analyze_in_background(task_id: str):
    """在后台线程中执行完整分析流程。"""
    t = threading.Thread(target=_do_analyze, args=(task_id,), daemon=True)
    t.start()


def _do_analyze(task_id: str):
    task = get_task(task_id) or {}
    spec = task.get("spec", {})
    url = spec.get("url", "")
    platform = spec.get("platform", "") or task_id

    if not url:
        append_think(task_id, "❌ 任务没有 URL")
        return

    update_status(task_id, "probing")
    append_think(task_id, f"🧠 开始自动分析任务 {task_id}")
    append_think(task_id, f"📡 目标URL: {url}")

    try:
        html, cookies = _fetch_page(url)
        save_raw_html(task_id, html[:100000])
        append_think(task_id, f"✅ 获取到 HTML ({len(html)} 字节)")

        fields = _extract_all_fields(html, url)
        append_think(task_id, f"✅ 找到 {len(fields)} 个字段")

        analysis = {
            "page_type": "product_detail",
            "fields": fields,
            "antibot": {"status": "clear", "vendor": None},
            "log": f"自动分析完成, 找到 {len(fields)} 个字段",
        }
        save_analysis(task_id, analysis)
    except Exception as e:
        append_think(task_id, f"❌ 分析失败: {e}")
        update_status(task_id, "error")


def _fetch_page(url: str) -> tuple[str, list]:
    try:
        from curl_cffi import requests as cr
        session = cr.Session(impersonate="chrome120", verify=False)
        r = session.get(url, timeout=15)
        return r.text, list(session.cookies)
    except Exception:
        import requests
        r = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 Chrome/120 Safari/537.36",
            "Accept": "text/html",
        })
        return r.text, []


def _extract_all_fields(html: str, url: str) -> list:
    fields = []

    # 1. Title
    for pattern in [r'<title>(.*?)</title>',
                    r'name["\s:]+["\'](.*?)["\']',
                    r'"name"\s*:\s*"(.*?)"']:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            val = m.group(1).strip()[:200]
            if val and len(val) > 5:
                fields.append({
                    "name": "title", "value": val,
                    "source": "html", "business_value": 5, "priority": "high",
                })
                break

    # 2. Price
    for pattern in [r'(\d+[,.]\d{2})\s*(?:zł|PLN|€|\$|zł)',
                    r'"price"\s*:\s*(\d+[.,]\d+)',
                    r'"originalPrice"\s*:\s*(\d+[.,]\d+)']:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            fields.append({
                "name": "price", "value": m.group(1),
                "source": "html", "business_value": 5, "priority": "high",
            })
            break

    # 3. JSON-LD
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.DOTALL
    ):
        try:
            raw = m.group(1).strip()
            if raw.startswith("//"): continue
            data = json.loads(raw)
            if isinstance(data, list):
                data = data[0] if data else {}
            if isinstance(data, dict):
                for key in ["name", "description", "sku", "brand",
                            "offers", "aggregateRating", "image",
                            "category"]:
                    val = data.get(key)
                    if val:
                        if isinstance(val, dict):
                            for sub_k, sub_v in val.items():
                                if isinstance(sub_v, (str, int, float)):
                                    fields.append({
                                        "name": f"jsonld_{key}_{sub_k}",
                                        "value": str(sub_v)[:200],
                                        "source": "json-ld",
                                        "business_value": 3,
                                        "priority": "medium",
                                    })
                        else:
                            fields.append({
                                "name": f"jsonld_{key}",
                                "value": str(val)[:200],
                                "source": "json-ld",
                                "business_value": 4,
                                "priority": "high",
                            })
        except Exception:
            pass

    # 4. 图片
    for m in re.finditer(
        r'(?:src|content)=["\'](https?://[^"\']+\.(?:jpg|png|webp))["\']',
        html, re.IGNORECASE
    ):
        img = m.group(1)
        if "/cover/" in img or "/product/" in img or "/image/" in img:
            fields.append({
                "name": "image", "value": img,
                "source": "html", "business_value": 3, "priority": "medium",
            })
            break

    # 5. 描述
    for m in re.finditer(r'<meta[^>]*name="description"[^>]*content="([^"]+)"',
                         html, re.IGNORECASE):
        fields.append({
            "name": "description", "value": m.group(1)[:300],
            "source": "html", "business_value": 3, "priority": "medium",
        })
        break

    return fields
