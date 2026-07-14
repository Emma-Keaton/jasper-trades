import sqlite3
conn = sqlite3.connect('data/sqlite/jasper_trades.db')
cursor = conn.execute('PRAGMA table_info(device_settings)')
cols = [row[1] for row in cursor.fetchall()]
print('Columns in device_settings:', len(cols))
print('universal_paper_trading_config exists:', 'universal_paper_trading_config' in cols)
if 'universal_paper_trading_config' in cols:
    print('✅ SUCCESS: Universal paper trading is ready!')
else:
    print('Column list:', cols)
conn.close()