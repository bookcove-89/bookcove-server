import redis, os

# NOTE: redis stores data as bytes so use 'json.dumps()' when storing and 'json.loads()' when retrieving
# default to 'redis' if 'localhost' doesn't work in docker container
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=6379, 
    db=0,
    decode_responses=True
)
