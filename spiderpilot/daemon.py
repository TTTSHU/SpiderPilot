#!/usr/bin/env python3
"""SpiderPilot AI 守护进程 — 自动处理待办任务。

启动后持续监控 /api/pending，发现有新任务自动分析。
"""

import json
import os
import sys
import time


def main():
    server = os.environ.get("SPIDER_HOST", "http://127.0.0.1:8000")
    print(f"[守护进程] 启动, 监控 {server}")

    while True:
        try:
            import requests
            resp = requests.get(f"{server}/api/pending", timeout=5)
            tasks = resp.json()
        except Exception as e:
            print(f"[守护进程] 连接失败: {e}, 3秒后重试...")
            time.sleep(3)
            continue

        if not tasks:
            time.sleep(3)
            continue

        for task in tasks:
            task_id = task["task_id"]
            url = task["url"]
            print(f"\n[守护进程] 发现待处理任务: {task_id} ({url})")

            # 更新状态为 probing
            try:
                requests.post(f"{server}/task/{task_id}/probe", timeout=5)
            except Exception:
                pass

            # 写入思考流
            _think(server, task_id, f"🧠 自动开始分析任务 {task_id}...")
            _think(server, task_id, f"📡 目标URL: {url}")

            # 调用 CodeWhale CLI 处理（如果存在）
            result = _run_analysis(server, task_id, url)

            if result:
                _think(server, task_id, f"✅ 分析完成!")
            else:
                _think(server, task_id, "⚠️ 自动分析失败，请手动触发 CodeWhale")

        time.sleep(5)


def _think(server: str, task_id: str, text: str):
    try:
        import requests
        requests.post(
            f"{server}/task/{task_id}/think",
            json={"text": text},
            timeout=5,
        )
    except Exception:
        pass


def _run_analysis(server, task_id, url):
    """尝试用内部逻辑分析页面。返回 True/False。"""
    try:
        import requests
        from curl_cffi import requests as cr

        _think(server, task_id, "🔍 检测反爬...")
        try:
            r = requests.get(url, timeout=10, headers={
                "User-Agent": "SpiderPilot/0.1"
            })
            status = r.status_code
            if status == 403:
                _think(server, task_id, "🛡️ 检测到 403，可能是 Cloudflare/反爬")
            else:
                _think(server, task_id, f"✅ HTTP {status}, 无反爬")
        except Exception as e:
            _think(server, task_id, f"⚠️ 请求失败: {e}")

        _think(server, task_id, "📡 使用 curl_cffi 获取页面...")
        session = cr.Session(impersonate="chrome120", verify=False)
        r = session.get(url, timeout=15)
        html = r.text

        _think(server, task_id, f"✅ 获取到 HTML ({len(html)} 字节)")

        # 保存 raw HTML
        try:
            requests.post(
                f"{server}/task/{task_id}/raw",
                json={"html": html[:50000], "log": "页面探测完成"},
                timeout=5,
            )
        except Exception:
            pass

        # 分析字段
        _think(server, task_id, "🔬 分析页面字段...")
        fields = _extract_fields(html, url)

        # 写入分析结果
        analysis = {
            "page_type": "product_detail",
            "fields": fields,
            "antibot": {"status": "clear", "vendor": None},
            "log": f"自动分析完成, 找到 {len(fields)} 个字段",
        }
        requests.post(
            f"{server}/task/{task_id}/analysis",
            json=analysis,
            timeout=10,
        )
        _think(server, task_id, f"✅ 找到 {len(fields)} 个字段!")

        return True
    except Exception as e:
        _think(server, task_id, f"❌ 分析失败: {e}")
        return False


def _extract_fields(html: str, url: str) -> list:
    """从 HTML 中提取字段。"""
    fields = []
    import re

    # 提取 title
    for pattern in [r'<title>(.*?)</title>', r'<h1[^>]*>(.*?)</h1>',
                    r'name["\s:]+([^"]+)"']:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            val = m.group(1).strip()[:100]
            if val and len(val) > 3:
                fields.append({
                    "name": "title", "value": val, "type": "str",
                    "source": "html", "business_value": 5, "priority": "high",
                })
                break

    # 提取价格
    for pattern in [r'(\d+[,.]\d{2})\s*(?:zł|PLN|€|\$)', r'price["\s]*[:=]\s*["\']?(\d+[.,]\d+)']:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            fields.append({
                "name": "price", "value": m.group(1), "type": "float",
                "source": "html", "business_value": 5, "priority": "high",
            })
            break

    # 提取 JSON-LD
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
            if isinstance(data, dict):
                for key in ["name", "description", "sku", "brand"]:
                    if key in data and data[key]:
                        fields.append({
                            "name": key, "value": str(data[key])[:100],
                            "type": "str", "source": "json-ld",
                            "business_value": 4, "priority": "high",
                        })
        except Exception:
            pass

    return fields


if __name__ == "__main__":
    main()
