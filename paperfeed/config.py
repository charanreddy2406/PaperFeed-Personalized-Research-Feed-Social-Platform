import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv('DATABASE_URL','postgresql://paperfeed:paperfeed@localhost:5432/paperfeed')
    redis_url: str = os.getenv('REDIS_URL','redis://localhost:6379/0')
    bucket: str = os.getenv('S3_BUCKET','paperfeed')
    endpoint: str | None = os.getenv('S3_ENDPOINT')
    public_endpoint: str | None = os.getenv('S3_PUBLIC_ENDPOINT')
    secure_cookie: bool = os.getenv('SECURE_COOKIE','true').lower() == 'true'
    origin: str = os.getenv('APP_ORIGIN','http://localhost:8080')
    kafka: str = os.getenv('KAFKA_BOOTSTRAP','kafka:9092')
    ttl: int = 180

settings = Settings()
