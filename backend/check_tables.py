import sqlite3

con = sqlite3.connect("supplychain.db")
cur = con.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]

print(tables)

con.close()
