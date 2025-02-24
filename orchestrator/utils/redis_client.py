import redis.asyncio
import redis.client
import redis.exceptions
from pydantic import RedisDsn
from redis import Redis
from redis.asyncio import Redis as AIORedis
from redis.asyncio.retry import Retry as AIORetry
from redis.backoff import EqualJitterBackoff
from redis.retry import Retry

from orchestrator.settings import app_settings

REDIS_RETRY_ON_ERROR = [redis.exceptions.ConnectionError]
REDIS_RETRY_ON_TIMEOUT = True
REDIS_RETRY_BACKOFF = EqualJitterBackoff(base=0.05)


def create_redis_client(redis_url: str | RedisDsn) -> redis.client.Redis:
    """Create sync Redis client for the given Redis DSN with retry handling for connection errors and timeouts."""
    return Redis.from_url(
        str(redis_url),
        retry_on_error=REDIS_RETRY_ON_ERROR,  # type: ignore[arg-type]
        retry_on_timeout=REDIS_RETRY_ON_TIMEOUT,
        retry=Retry(REDIS_RETRY_BACKOFF, app_settings.REDIS_RETRY_COUNT),
    )


def create_redis_asyncio_client(redis_url: str | RedisDsn) -> redis.asyncio.client.Redis:
    """Create async Redis client for the given Redis DSN with retry handling for connection errors and timeouts."""
    return AIORedis.from_url(
        str(redis_url),
        retry_on_error=REDIS_RETRY_ON_ERROR,  # type: ignore[arg-type]
        retry_on_timeout=REDIS_RETRY_ON_TIMEOUT,
        retry=AIORetry(REDIS_RETRY_BACKOFF, app_settings.REDIS_RETRY_COUNT),
    )
