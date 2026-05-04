import sqlite3
conn = sqlite3.connect('data/plugin_data/agent_system/agent.db')
# Check schema of agent_tasks
schema = conn.execute("PRAGMA table_info(agent_tasks)").fetchall()
cols = [c[1] for c in schema]

# Get latest task
row = conn.execute("SELECT * FROM agent_tasks WHERE name = 'HITL链路验证-v3'").fetchone()
if row:
    for c, v in zip(cols, row):
        print(f"  {c}: {v}")

# Also check if there are any error entries
print("\n=== Tasks with errors ===")
err_rows = conn.execute("SELECT id, name, error, status FROM agent_tasks WHERE error IS NOT NULL AND error != ''").fetchall()
for r in err_rows:
    print(f"  {r[0]}: {r[1]} -> error={r[2][:100]}")

conn.close()
