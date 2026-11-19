from paperfeed.posts import RELATIONSHIP_SQL
from paperfeed.config import settings
from paperfeed.ranking import merge_candidates
from pathlib import Path


def test_relationship_statements_are_static():
    assert set(RELATIONSHIP_SQL) == {(table, enabled) for table in ('likes', 'bookmarks') for enabled in (True, False)}
    assert all(sql.count('%s') == 2 for sql in RELATIONSHIP_SQL.values())


def test_candidate_priority():
    assert merge_candidates([[{'id': 1, 'source': 'follow'}], [{'id': 1, 'source': 'recent'}]]) == [{'id': 1, 'source': 'follow'}]


def test_migration_has_snapshot_expiry():
    sql = Path('db/migrations/002_hardening.sql').read_text()
    assert 'expires_at timestamptz NOT NULL' in sql
    assert settings.ttl == 180
