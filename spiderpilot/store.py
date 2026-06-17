"""
SpiderPilot 任务存储层。

纯函数接口，不暴露实现细节。
当前使用 SQLite，切换存储只需改 import。
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


DB_PATH = Path("workspace/spiderpilot.db")


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            url         TEXT NOT NULL,
            platform    TEXT DEFAULT '',
            agent       TEXT DEFAULT '',
            status      TEXT DEFAULT 'created',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS task_data (
            task_id     TEXT PRIMARY KEY,
            spec        TEXT DEFAULT '{}',
            analysis    TEXT DEFAULT '{}',
            spider_code TEXT DEFAULT '',
            plan        TEXT DEFAULT '',
            raw_html    TEXT DEFAULT '',
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );

        CREATE TABLE IF NOT EXISTS think_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id     TEXT NOT NULL,
            time        TEXT NOT NULL,
            text        TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );

        CREATE TABLE IF NOT EXISTS operation_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id     TEXT NOT NULL,
            time        TEXT NOT NULL,
            message     TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_think_task ON think_log(task_id);
        CREATE INDEX IF NOT EXISTS idx_log_task ON operation_log(task_id);
    """)


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ═══════════════════════════════════════════
# 任务 CRUD
# ═══════════════════════════════════════════

def create_task(task_id: str, name: str, url: str, platform: str = "",
                agent: str = "") -> dict:
    db = _get_db()
    now = _now()
    db.execute(
        "INSERT OR REPLACE INTO tasks (id,name,url,platform,agent,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
        (task_id, name, url, platform, agent, "created", now, now),
    )
    db.execute(
        "INSERT OR IGNORE INTO task_data (task_id) VALUES (?)", (task_id,)
    )
    db.commit()
    return get_task(task_id)


def get_task(task_id: str) -> dict | None:
    db = _get_db()
    row = db.execute(
        "SELECT t.*, d.spec, d.analysis, d.spider_code, d.plan, d.raw_html "
        "FROM tasks t LEFT JOIN task_data d ON t.id = d.task_id "
        "WHERE t.id = ?", (task_id,)
    ).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def list_tasks(status: str | None = None) -> list[dict]:
    db = _get_db()
    if status:
        rows = db.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY updated_at DESC",
            (status,)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM tasks ORDER BY updated_at DESC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_status(task_id: str, status: str):
    db = _get_db()
    db.execute(
        "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
        (status, _now(), task_id),
    )
    db.commit()


def delete_task(task_id: str):
    db = _get_db()
    db.execute("DELETE FROM think_log WHERE task_id = ?", (task_id,))
    db.execute("DELETE FROM operation_log WHERE task_id = ?", (task_id,))
    db.execute("DELETE FROM task_data WHERE task_id = ?", (task_id,))
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()


def update_spec(task_id: str, spec: dict):
    db = _get_db()
    db.execute(
        "UPDATE task_data SET spec = ? WHERE task_id = ?",
        (json.dumps(spec, ensure_ascii=False), task_id),
    )
    url = spec.get("url", "")
    agent = spec.get("agent", "")
    db.execute(
        "UPDATE tasks SET url = ?, agent = ?, updated_at = ? WHERE id = ?",
        (url, agent, _now(), task_id),
    )
    db.commit()


# ═══════════════════════════════════════════
# 分析数据
# ═══════════════════════════════════════════

def save_analysis(task_id: str, analysis: dict):
    db = _get_db()
    db.execute(
        "UPDATE task_data SET analysis = ? WHERE task_id = ?",
        (json.dumps(analysis, ensure_ascii=False), task_id),
    )
    update_status(task_id, "analyzed")
    if analysis.get("log"):
        append_log(task_id, analysis["log"])


def save_spider_code(task_id: str, code: str, plan: dict | None = None):
    db = _get_db()
    db.execute(
        "UPDATE task_data SET spider_code = ?, plan = ? WHERE task_id = ?",
        (code, json.dumps(plan, ensure_ascii=False) if plan else "{}", task_id),
    )
    update_status(task_id, "generated")


def save_raw_html(task_id: str, html: str):
    db = _get_db()
    db.execute(
        "UPDATE task_data SET raw_html = ? WHERE task_id = ?",
        (html, task_id),
    )


# ═══════════════════════════════════════════
# 思考流
# ═══════════════════════════════════════════

def append_think(task_id: str, text: str):
    db = _get_db()
    db.execute(
        "INSERT INTO think_log (task_id, time, text) VALUES (?, ?, ?)",
        (task_id, _now(), text),
    )
    db.commit()


def get_think_stream(task_id: str) -> list[dict]:
    db = _get_db()
    rows = db.execute(
        "SELECT time, text FROM think_log WHERE task_id = ? ORDER BY id",
        (task_id,)
    ).fetchall()
    return [{"time": r["time"], "text": r["text"]} for r in rows]


# ═══════════════════════════════════════════
# 日志
# ═══════════════════════════════════════════

def append_log(task_id: str, message: str):
    db = _get_db()
    db.execute(
        "INSERT INTO operation_log (task_id, time, message) VALUES (?, ?, ?)",
        (task_id, _now(), message),
    )
    db.commit()


def get_log(task_id: str) -> list[str]:
    db = _get_db()
    rows = db.execute(
        "SELECT time, message FROM operation_log WHERE task_id = ? ORDER BY id",
        (task_id,)
    ).fetchall()
    return [f"[{r['time']}] {r['message']}" for r in rows]


# ═══════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════

def _row_to_dict(row) -> dict:
    d = dict(row)
    for key in ("spec", "analysis", "plan"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except Exception:
                d[key] = {}
    return d
