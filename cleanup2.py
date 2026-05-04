import sqlite3
conn = sqlite3.connect('data/plugin_data/agent_system/agent.db')
conn.execute("UPDATE agent_tasks SET status='failed', error='Server restarted', updated_at=datetime('now') WHERE status='running'")
conn.commit()
print(f'Updated {conn.total_changes} tasks')
conn.close()
