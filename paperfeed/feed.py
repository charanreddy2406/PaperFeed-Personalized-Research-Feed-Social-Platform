import logging,uuid
from datetime import datetime,timezone
from paperfeed.db import transaction
from paperfeed.ranking import Features,score,merge_candidates,diversify
from paperfeed.embeddings import embed
from paperfeed.cache import FeedCache
from paperfeed.config import settings
from fastapi import HTTPException

log=logging.getLogger(__name__)
BASE='''SELECT p.*, (SELECT count(*) FROM likes l WHERE l.post_id=p.id)+(SELECT count(*) FROM comments c WHERE c.post_id=p.id) AS engagement FROM posts p'''
def retrieve(conn,user,vector,interests=()):
    followed=conn.execute(BASE+' WHERE EXISTS(SELECT 1 FROM follows f WHERE f.follower_id=%s AND f.followee_id=p.author_id) ORDER BY p.created_at DESC,p.id DESC LIMIT 50',(user,)).fetchall()
    semantic=[]
    if vector is not None:
        semantic=conn.execute(BASE+' WHERE embedding IS NOT NULL ORDER BY embedding <=> %s::vector,p.id LIMIT 100',(str(vector),)).fetchall()
    if vector is None and interests:
        semantic=conn.execute(BASE+' WHERE tags && %s::text[] ORDER BY p.created_at DESC,p.id DESC LIMIT 100',(list(interests),)).fetchall()
    recent=conn.execute(BASE+' ORDER BY p.created_at DESC,p.id DESC LIMIT 30').fetchall()
    trending=conn.execute(BASE+' ORDER BY engagement DESC,p.id DESC LIMIT 20').fetchall()
    return merge_candidates([followed,semantic,recent,trending])

def rank_for(user):
    interests=set(user['interests']); vector=None
    if interests:
        try: vector=embed(' '.join(sorted(interests)))
        except Exception: log.exception('Embedding unavailable; using topic retrieval')
    with transaction() as conn:
        posts=retrieve(conn,user['id'],vector,interests)
        follows={r['followee_id'] for r in conn.execute('SELECT followee_id FROM follows WHERE follower_id=%s',(user['id'],))}
        history = {r['topic']: r['weight'] for r in conn.execute("""SELECT topic, sum(weight) AS weight FROM (
            SELECT unnest(p.tags) AS topic, 1 AS weight FROM likes l JOIN posts p ON p.id=l.post_id WHERE l.user_id=%s
            UNION ALL SELECT unnest(p.tags), 2 FROM bookmarks b JOIN posts p ON p.id=b.post_id WHERE b.user_id=%s
            UNION ALL SELECT unnest(p.tags), 2 FROM comments c JOIN posts p ON p.id=c.post_id WHERE c.user_id=%s
            ) signals GROUP BY topic""", (user['id'],)*3)}
        similarities = {}
        if vector is not None and posts:
            similarities = {row['id']: row['similarity'] or 0 for row in conn.execute('SELECT id, 1 - (embedding <=> %s::vector) AS similarity FROM posts WHERE id=ANY(%s) AND embedding IS NOT NULL', (str(vector), [p['id'] for p in posts]))}
        for p in posts:
            tags=set(p['tags'])
            similarity = similarities.get(p['id'], 0)
            p['score']=score(Features(similarity,len(tags&interests)/max(1,len(interests)),(datetime.now(timezone.utc)-p['created_at']).total_seconds()/3600,p['author_id'] in follows,p['engagement'],min(1,sum(history.get(t,0) for t in tags)/10)))
    posts.sort(key=lambda p:(p['score'],p['id']),reverse=True)
    return [p['id'] for p in diversify(posts)]

def get_feed(user, limit, cursor):
    cache = FeedCache()
    uid = user['id']
    generation = user['feed_version']
    prefix = f'feed:{uid}:{generation}'
    start = 0
    if cursor:
        try:
            snapshot, offset = cursor.split(':')
            uuid.UUID(snapshot)
            start = int(offset)
            if not 0 <= start <= 200:
                raise ValueError()
        except ValueError:
            raise HTTPException(400, 'Invalid cursor')
        ids = cache.get(f'{prefix}:{snapshot}')
        if ids is None:
            with transaction() as conn:
                row = conn.execute('SELECT post_ids FROM feed_snapshots WHERE id=%s AND user_id=%s AND generation=%s AND expires_at>now()', (snapshot, uid, generation)).fetchone()
            if row is None:
                raise HTTPException(410, 'FEED_EXPIRED')
            ids = row['post_ids']
    else:
        snapshot = cache.get(f'{prefix}:active')
        ids = cache.get(f'{prefix}:{snapshot}') if snapshot else None
        if ids is None:
            with transaction() as conn:
                row = conn.execute('SELECT id,post_ids FROM feed_snapshots WHERE user_id=%s AND generation=%s AND expires_at>now() ORDER BY expires_at DESC LIMIT 1', (uid, generation)).fetchone()
            if row:
                snapshot, ids = str(row['id']), row['post_ids']
            else:
                snapshot, ids = str(uuid.uuid4()), rank_for(user)
                with transaction() as conn:
                    conn.execute("INSERT INTO feed_snapshots VALUES(%s,%s,%s,%s,now()+%s*interval '1 second')", (snapshot,uid,generation,ids,settings.ttl))
                cache.put(f'{prefix}:{snapshot}', ids)
                cache.put(f'{prefix}:active', snapshot)
    from paperfeed.posts import hydrate
    items = hydrate(ids[start:start+limit], uid)
    return {'items': items, 'next_cursor': f'{snapshot}:{start+limit}' if start+limit<len(ids) else None}
