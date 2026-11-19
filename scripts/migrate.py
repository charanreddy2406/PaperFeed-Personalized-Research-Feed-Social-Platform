from pathlib import Path
from paperfeed import db

def main():
    db.open_pool()
    try:
        with db.transaction() as c:
            c.execute('SELECT pg_advisory_xact_lock(810321)')
            c.execute('CREATE TABLE IF NOT EXISTS schema_migrations(name text PRIMARY KEY)')
            for path in sorted(Path('db/migrations').glob('*.sql')):
                if not c.execute('SELECT name FROM schema_migrations WHERE name=%s',(path.name,)).fetchone():
                    c.execute(path.read_text()); c.execute('INSERT INTO schema_migrations VALUES(%s)',(path.name,))
    finally: db.close_pool()
if __name__=='__main__': main()
