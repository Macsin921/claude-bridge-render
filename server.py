
from flask import Flask, request, jsonify
import psycopg2
import os
from datetime import datetime

app = Flask(__name__)

DB_URL = os.environ.get("DATABASE_URL")
BRIDGE_KEY = os.environ.get("BRIDGE_KEY", "claude2025")

def get_db():
    return psycopg2.connect(DB_URL)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            cmd TEXT NOT NULL,
            result TEXT,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS secrets (
            key VARCHAR(100) PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

@app.route("/ping")
def ping():
    return jsonify({"status": "ok", "bridge": "render", "time": str(datetime.now())})

@app.route("/queue/task", methods=["POST"])
def create_task():
    data = request.json
    if data.get("key") != BRIDGE_KEY:
        return jsonify({"error": "invalid key"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO tasks (cmd) VALUES (%s) RETURNING id", (data.get("cmd"),))
    task_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True, "task_id": task_id})

@app.route("/queue/tasks")
def get_tasks():
    key = request.args.get("key")
    if key != BRIDGE_KEY:
        return jsonify({"error": "invalid key"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, cmd FROM tasks WHERE status = 'pending' ORDER BY id")
    tasks = [{"id": r[0], "cmd": r[1]} for r in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify({"tasks": tasks})

@app.route("/queue/result", methods=["POST"])
def submit_result():
    data = request.json
    if data.get("key") != BRIDGE_KEY:
        return jsonify({"error": "invalid key"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET result = %s, status = 'done' WHERE id = %s",
                (data.get("result"), data.get("task_id")))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True})

@app.route("/queue/result/<int:task_id>")
def get_result(task_id):
    key = request.args.get("key")
    if key != BRIDGE_KEY:
        return jsonify({"error": "invalid key"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, cmd, result, status, created_at FROM tasks WHERE id = %s", (task_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify({"id": row[0], "cmd": row[1], "result": row[2], "status": row[3], "created_at": str(row[4])})

# Secrets management
@app.route("/secrets", methods=["GET"])
def list_secrets():
    key = request.args.get("key")
    if key != BRIDGE_KEY:
        return jsonify({"error": "invalid key"}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT key FROM secrets")
    keys = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify({"secrets": keys})

@app.route("/secrets/<secret_key>", methods=["GET", "PUT", "DELETE"])
def manage_secret(secret_key):
    auth = request.args.get("key")
    if auth != BRIDGE_KEY:
        return jsonify({"error": "invalid key"}), 401
    conn = get_db()
    cur = conn.cursor()
    if request.method == "GET":
        cur.execute("SELECT value FROM secrets WHERE key = %s", (secret_key,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": "not found"}), 404
        return jsonify({"key": secret_key, "value": row[0]})
    elif request.method == "PUT":
        value = request.json.get("value")
        cur.execute("""
            INSERT INTO secrets (key, value) VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = CURRENT_TIMESTAMP
        """, (secret_key, value, value))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"ok": True})
    elif request.method == "DELETE":
        cur.execute("DELETE FROM secrets WHERE key = %s", (secret_key,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"ok": True})

with app.app_context():
    try:
        init_db()
    except:
        pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
