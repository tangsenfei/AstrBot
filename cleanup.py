import sqlite3
conn = sqlite3.connect('data/plugin_data/agent_system/agent.db')
# Mark all running tasks as failed
conn.execute("UPDATE agent_tasks SET status = 'failed', error = 'Server restarted', updated_at = datetime('now') WHERE status = 'running'")
conn.commit()
count = conn.total_changes
print(f"Updated {count} running tasks to failed")
conn.close()
