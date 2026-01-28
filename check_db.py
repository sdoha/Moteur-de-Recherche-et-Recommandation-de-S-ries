import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'tvshow.db')
DB_PATH = os.path.abspath(DB_PATH)

print('DB path:', DB_PATH, 'exists:', os.path.exists(DB_PATH))
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
for t in ['tvshow', 'tvshow_term', 'ratings', 'mylist']:
    try:
        c = cur.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        print(f'{t}:', c)
    except Exception as e:
        print(f'{t}: ERROR', e)
conn.close()

