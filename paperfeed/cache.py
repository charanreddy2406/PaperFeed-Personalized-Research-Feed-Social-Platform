import json
from paperfeed.config import settings

class FeedCache:
    def __init__(self):
        from redis import Redis
        self.client = Redis.from_url(settings.redis_url,decode_responses=True,socket_timeout=.5,socket_connect_timeout=.5)
    def get(self,key):
        from redis.exceptions import RedisError
        try:
            value=self.client.get(key)
            return json.loads(value) if value else None
        except (RedisError,ValueError): return None
    def put(self,key,value):
        from redis.exceptions import RedisError
        try:
            self.client.set(key,json.dumps(value),ex=settings.ttl)
            return True
        except RedisError: return False
    def invalidate(self,user):
        from redis.exceptions import RedisError
        try:
            for key in self.client.scan_iter(f'feed:{user}:*'): self.client.delete(key)
        except RedisError: pass
