from contextlib import contextmanager
from paperfeed.config import settings

_pool = None

def open_pool():
    global _pool
    from psycopg_pool import ConnectionPool
    from psycopg.rows import dict_row
    _pool = ConnectionPool(settings.database_url, min_size=1,max_size=8,kwargs={'row_factory':dict_row, 'options':'-c statement_timeout=15000 -c lock_timeout=5000'},open=False)
    _pool.open(wait=True)

def close_pool():
    if _pool: _pool.close()

@contextmanager
def transaction():
    with _pool.connection() as conn:
        yield conn
