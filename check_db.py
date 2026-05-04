import sqlite3
import os

# List all databases
data_dir = 'data'
for f in os.listdir(data_dir):
    if f.endswith('.db'):
        print(f"Database: {f}")
        conn = sqlite3.connect(os.path.join(data_dir, f))
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"  Tables: {[t[0] for t in tables]}")
        
        # Check for task-related tables
        if 'agent_tasks' in [t[0] for t in tables]:
            rows = conn.execute("SELECT id, title, thread_id, status FROM agent_tasks WHERE title LIKE ?", ('%HITL%',)).fetchall()
            print(f"  agent_tasks matches: {len(rows)}")
            for row in rows:
                print(f"    id={row[0]}, title={row[1]}, thread_id={row[2]}, status={row[3]}")
        
        if 'execution_logs' in [t[0] for t in tables]:
            logs_count = conn.execute("SELECT COUNT(*) FROM execution_logs").fetchone()[0]
            print(f"  execution_logs count: {logs_count}")
            # Get most recent
            recent = conn.execute("SELECT id, task_id, log_message FROM execution_logs ORDER BY created_at DESC LIMIT 10").fetchall()
            for r in recent:
                print(f"    id={r[0]}, task_id={r[1]}, msg={r[2][:80]}")
        
        conn.close()
        print()
