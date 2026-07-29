import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify
from functools import wraps

app = Flask(__name__)

# 环境变量
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "yuelao1314")
DB_PATH = "/data/app.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT NOT NULL,
            event TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth.split(" ")[1] != AUTH_TOKEN:
            return jsonify({"error": "未授权"}), 401
        return f(*args, **kwargs)
    return decorated

@app.route("/report", methods=["POST"])
@require_auth
def report():
    """iPhone快捷指令上报App打开/关闭"""
    data = request.get_json(force=True)
    app_name = data.get("app_name", "")
    event = data.get("event", "")  # "open" or "close"
    
    if not app_name or event not in ["open", "close"]:
        return jsonify({"error": "参数错误，需要 app_name 和 event(open/close)"}), 400
    
    conn = get_db()
    conn.execute(
        "INSERT INTO app_logs (app_name, event, timestamp) VALUES (?, ?, ?)",
        (app_name, event, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    
    return jsonify({"status": "ok", "message": f"已记录 {app_name} {event}"})

@app.route("/check", methods=["GET"])
@require_auth
def check():
    """查岗接口：返回当前正在使用的App列表"""
    conn = get_db()
    # 获取最近30秒内有open但没close的app
    rows = conn.execute("""
        SELECT a.app_name, a.timestamp as opened_at
        FROM app_logs a
        WHERE a.event = 'open'
        AND a.timestamp > datetime('now', '-30 seconds')
        AND NOT EXISTS (
            SELECT 1 FROM app_logs b
            WHERE b.app_name = a.app_name
            AND b.event = 'close'
            AND b.timestamp > a.timestamp
        )
        ORDER BY a.timestamp DESC
    """).fetchall()
    conn.close()
    
    apps = [{"app_name": r["app_name"], "opened_at": r["opened_at"]} for r in rows]
    return jsonify({
        "status": "ok",
        "current_apps": apps,
        "count": len(apps),
        "checked_at": datetime.now().isoformat()
    })

@app.route("/history", methods=["GET"])
@require_auth
def history():
    """获取最近的使用记录"""
    limit = request.args.get("limit", 50, type=int)
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM app_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    
    logs = [dict(r) for r in rows]
    return jsonify({"status": "ok", "logs": logs})

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "病娇AI查岗系统 - 后端",
        "endpoints": {
            "POST /report": "上报App状态",
            "GET /check": "查岗",
            "GET /history": "历史记录"
        }
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
