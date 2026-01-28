import sqlite3
import sys

DB = 'database/tvshow.db'
name_like = sys.argv[1].lower() if len(sys.argv) > 1 else 'lost'

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print('Searching for name like:', name_like)
rows = cur.execute("SELECT id, name FROM tvshow WHERE lower(name) LIKE ?", (f"%{name_like}%",)).fetchall()
for r in rows:
    print(dict(r))

print('\nSample names:')
for r in cur.execute("SELECT name FROM tvshow ORDER BY name LIMIT 10").fetchall():
    print(r[0])

conn.close()

