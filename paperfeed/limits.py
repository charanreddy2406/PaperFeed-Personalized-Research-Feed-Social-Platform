import hashlib
from fastapi import HTTPException
from redis import Redis
from redis.exceptions import RedisError
from paperfeed.config import settings

SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return count
"""


def enforce(scope: str, identity: str, limit: int, seconds: int) -> None:
    key = f"limit:{scope}:{hashlib.sha256(identity.encode()).hexdigest()}"
    try:
        with Redis.from_url(settings.redis_url, socket_timeout=0.5, socket_connect_timeout=0.5) as client:
            count = client.eval(SCRIPT, 1, key, seconds)
    except RedisError as exc:
        raise HTTPException(503, 'Rate limiter unavailable') from exc
    if count > limit:
        raise HTTPException(429, 'Too many requests', headers={'Retry-After': str(seconds)})
