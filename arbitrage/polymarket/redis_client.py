import redis
from config import settings

def get_redis_client():
    """
    获取 Redis 客户端实例
    """
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password if settings.redis_password else None,
        decode_responses=True
    )
