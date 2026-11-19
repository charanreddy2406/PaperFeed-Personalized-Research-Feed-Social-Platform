import logging,time,sys,json
from paperfeed import db
from paperfeed.config import settings
from paperfeed.embeddings import embed
from paperfeed.media import client
log=logging.getLogger(__name__)
def process(c,event):
    if not c.execute('INSERT INTO processed_events VALUES(%s) ON CONFLICT DO NOTHING RETURNING id',(event['id'],)).fetchone(): return
    post=c.execute('SELECT * FROM posts WHERE id=%s',(event['post_id'],)).fetchone()
    if not post: return
    if event['event_type']=='embed':
        vector=embed(post['title']+' '+post['content'])
        c.execute('UPDATE posts SET embedding=%s::vector WHERE id=%s AND updated_at=%s',(str(vector),post['id'],post['updated_at']))
def tick():
    row = None
    try:
        with db.transaction() as c:
            row = c.execute('SELECT * FROM outbox WHERE processed_at IS NULL AND failed_at IS NULL AND next_attempt_at<=now() ORDER BY created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED').fetchone()
            if not row:
                return False
            process(c, row)
            c.execute('UPDATE outbox SET processed_at=now() WHERE id=%s', (row['id'],))
    except Exception as exc:
        if row is None:
            raise
        with db.transaction() as c:
            c.execute("UPDATE outbox SET attempts=attempts+1, next_attempt_at=now()+least(300, power(2, attempts+1))*interval '1 second', failed_at=CASE WHEN attempts+1>=8 THEN now() ELSE NULL END, last_error=%s WHERE id=%s AND processed_at IS NULL", (type(exc).__name__, row['id']))
        log.exception('Event processing failed: %s', row['id'])
    return True

def cleanup():
    with db.transaction() as c:
        c.execute("DELETE FROM sessions WHERE expires_at<=now()")
        c.execute("DELETE FROM feed_snapshots WHERE expires_at<=now()")
        rows=c.execute("SELECT id,owner_id,object_key FROM media WHERE post_id IS NULL AND state!='deleted' AND created_at<now()-interval '24 hours' LIMIT 20 FOR UPDATE SKIP LOCKED").fetchall()
        for row in rows:
            client().delete_object(Bucket=settings.bucket,Key=f"staging/{row['owner_id']}/{row['id']}"); client().delete_object(Bucket=settings.bucket,Key=row['object_key']); c.execute("UPDATE media SET state='deleted' WHERE id=%s",(row['id'],))
def relay():
    from kafka import KafkaProducer
    producer=KafkaProducer(bootstrap_servers=settings.kafka,acks='all',retries=3)
    while True:
        try:
            with db.transaction() as c:
                row=c.execute('SELECT id FROM outbox WHERE published_at IS NULL AND processed_at IS NULL AND failed_at IS NULL ORDER BY created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED').fetchone()
                if row:
                    producer.send('paperfeed.events',str(row['id']).encode()).get(timeout=10)
                    c.execute('UPDATE outbox SET published_at=now() WHERE id=%s',(row['id'],))
            if not row: time.sleep(1)
        except Exception: log.exception('Relay failed'); time.sleep(5)
def consume():
    from kafka import KafkaConsumer
    consumer=KafkaConsumer('paperfeed.events',bootstrap_servers=settings.kafka,group_id='paperfeed',enable_auto_commit=False,auto_offset_reset='earliest')
    for msg in consumer:
        with db.transaction() as c:
            row=c.execute('SELECT * FROM outbox WHERE id=%s FOR UPDATE',(msg.value.decode(),)).fetchone()
            if row: process(c,row); c.execute('UPDATE outbox SET processed_at=now() WHERE id=%s',(row['id'],))
        consumer.commit()
def main():
    logging.basicConfig(level=logging.INFO); db.open_pool()
    mode=sys.argv[1] if len(sys.argv)>1 else 'worker'
    if mode=='relay': relay()
    elif mode=='consumer': consume()
    else:
        while True:
            try:
                if not tick(): cleanup(); time.sleep(2)
            except Exception: log.exception('Worker retry'); time.sleep(5)
if __name__=='__main__': main()
