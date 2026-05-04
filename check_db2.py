import sqlite3
import json

conn = sqlite3.connect('data/plugin_data/agent_system/agent.db')

# Find all tables
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"Tables: {[t[0] for t in tables]}")

# Check agent_tasks for the new task
rows = conn.execute("SELECT id, title, thread_id, status FROM agent_tasks WHERE title LIKE ?", ('%HITL%',)).fetchall()
print(f"\n=== agent_tasks (HITL) ===")
for row in rows:
    print(f"id={row[0]}, title={row[1]}, thread_id={row[2]}, status={row[3]}")

# Check execution_logs for the HITL tasks
task_ids = [r[0] for r in rows]
for tid in task_ids:
    print(f"\n=== execution_logs for {tid} ===")
    logs = conn.execute("SELECT id, task_id, log_message, log_meta, created_at FROM execution_logs WHERE task_id = ? ORDER BY created_at", (tid,)).fetchall()
    for log in logs:
        print(f"  log_id={log[0]}, msg={log[2]}, meta={log[3][:100] if log[3] else None}, time={log[4]}")

# Check the most recent task
print("\n=== Most recent tasks ===")
recent = conn.execute("SELECT id, title, thread_id, status FROM agent_tasks ORDER BY created_at DESC LIMIT 5").fetchall()
for r in recent:
    print(f"id={r[0]}, title={r[1]}, thread_id={r[2]}, status={r[3]}")

# Also check if there's a "task_f8afe7e0bfae" entry
row = conn.execute("SELECT * FROM agent_tasks WHERE id = ?", ('task_f8afe7e0bfae',)).fetchone()
if row:
    cols = [d[0] for d in conn.execute("PRAGMA table_info(agent_tasks)").fetchall()]
    print(f"\n=== task_f8afe7e0bfae ===")
    for i, col in enumerate(cols):
        print(f"  {col}: {row[i]}")

conn.close()
