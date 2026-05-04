import sqlite3

conn = sqlite3.connect('data/plugin_data/agent_system/agent.db')

# Check schema
print("=== agent_tasks schema ===")
schema = conn.execute("PRAGMA table_info(agent_tasks)").fetchall()
for col in schema:
    print(f"  {col[1]} ({col[2]})")

# Check all agent_tasks
print("\n=== All agent_tasks ===")
rows = conn.execute("SELECT * FROM agent_tasks ORDER BY created_at DESC LIMIT 10").fetchall()
cols = [c[1] for c in schema]
print(f"  Columns: {cols}")
for row in rows:
    for i, val in enumerate(row):
        if val is not None and isinstance(val, str) and len(val) > 60:
            val = val[:60] + "..."
        print(f"    {cols[i]}: {val}")
    print()

# Check execution_logs schema
print("=== execution_logs schema ===")
schema2 = conn.execute("PRAGMA table_info(execution_logs)").fetchall()
for col in schema2:
    print(f"  {col[1]} ({col[2]})")

# Get recent execution logs
print("\n=== Recent execution_logs ===")
logs = conn.execute("SELECT * FROM execution_logs ORDER BY created_at DESC LIMIT 10").fetchall()
cols2 = [c[1] for c in schema2]
for row in logs:
    for i, val in enumerate(row):
        if val is not None and isinstance(val, str) and len(val) > 80:
            val = val[:80] + "..."
        print(f"  {cols2[i]}: {val}")
    print()

conn.close()
