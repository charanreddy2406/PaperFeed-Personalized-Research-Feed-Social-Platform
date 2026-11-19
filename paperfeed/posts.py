import uuid
from fastapi import HTTPException
from paperfeed.db import transaction
from paperfeed.media import read_url

def event(c,user,post,kind):
    c.execute('INSERT INTO outbox(id,user_id,post_id,event_type) VALUES(%s,%s,%s,%s)',(uuid.uuid4(),user,post,kind))
def hydrate(ids,user):
    if not ids: return []
    with transaction() as c:
        rows=c.execute('''SELECT p.id,p.author_id,p.title,p.content,p.tags,p.created_at,u.display_name AS author,pa.source_url,pa.title AS paper_title,
        (SELECT count(*) FROM likes WHERE post_id=p.id) AS like_count,
        (SELECT count(*) FROM comments WHERE post_id=p.id) AS comment_count,
        EXISTS(SELECT 1 FROM likes WHERE post_id=p.id AND user_id=%s) AS liked_by_me,
        EXISTS(SELECT 1 FROM bookmarks WHERE post_id=p.id AND user_id=%s) AS saved_by_me
        FROM posts p JOIN users u ON u.id=p.author_id JOIN papers pa ON pa.id=p.paper_id WHERE p.id=ANY(%s)''',(user,user,ids)).fetchall()
        media=c.execute("SELECT post_id,object_key,content_type FROM media WHERE post_id=ANY(%s) AND state='attached'",(ids,)).fetchall()
    by_id={r['id']:dict(r,media=[]) for r in rows}
    for m in media:
        if m['post_id'] in by_id:
            by_id[m['post_id']]['media'].append({'url':read_url(m['object_key']),'content_type':m['content_type']})
    return [by_id[i] for i in ids if i in by_id]
def create(user,data):
    with transaction() as c:
        paper=c.execute('INSERT INTO papers(source_url,title,abstract) VALUES(%s,%s,%s) ON CONFLICT(source_url) DO UPDATE SET source_url=EXCLUDED.source_url RETURNING id',(str(data.paper_url),data.paper_title,data.abstract)).fetchone()['id']
        post=c.execute('INSERT INTO posts(author_id,paper_id,title,content,tags) VALUES(%s,%s,%s,%s,%s) RETURNING id',(user,paper,data.title,data.content,data.tags)).fetchone()['id']
        for mid in data.media_ids:
            row=c.execute("UPDATE media SET post_id=%s,state='attached' WHERE id=%s AND owner_id=%s AND state='uploaded' RETURNING id",(post,mid,user)).fetchone()
            if not row: raise HTTPException(422,'Invalid attachment')
        event(c,user,post,'embed')
    return {'post_id':post,'paper_id':paper}
RELATIONSHIP_SQL = {
    ('likes', True): 'INSERT INTO likes(user_id,post_id) VALUES(%s,%s) ON CONFLICT DO NOTHING RETURNING post_id',
    ('likes', False): 'DELETE FROM likes WHERE user_id=%s AND post_id=%s RETURNING post_id',
    ('bookmarks', True): 'INSERT INTO bookmarks(user_id,post_id) VALUES(%s,%s) ON CONFLICT DO NOTHING RETURNING post_id',
    ('bookmarks', False): 'DELETE FROM bookmarks WHERE user_id=%s AND post_id=%s RETURNING post_id',
}


def relationship(user, post, table, enabled):
    statement = RELATIONSHIP_SQL[(table, enabled)]
    with transaction() as c:
        if not c.execute('SELECT id FROM posts WHERE id=%s FOR KEY SHARE', (post,)).fetchone():
            raise HTTPException(404, 'Post not found')
        changed = c.execute(statement, (user, post)).fetchone()
        if changed:
            kind = 'like' if table == 'likes' else 'bookmark'
            event(c, user, post, kind if enabled else kind + '_removed')
    return {'active': enabled}
