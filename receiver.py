import pika, os, redis, json

redis_client: redis.Redis = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=6379, 
    db=0,
    decode_responses=True
)

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.getenv("RABBITMQ_HOST", "localhost")))
    channel = connection.channel()
    print("channel opened succesfully")
    channel.queue_declare(queue='book-favorites-queue', durable=True)

    def callback(ch, method, properties, body):
        print(f"[x] Received: {body}")
        json_data = body.decode('utf-8')
        data = json.loads(json_data)
        cache_key = f"user_{data['user_id']}_books"

        if data['action'] ==  "added_favorite":
            # push new book to cache
            print("adding book to cache")
            redis_client.lpush(cache_key, json.dumps(data['book']))
        elif data['action'] == "remove_favorite":
            # remove from cache
            print("removing book from cache")
            redis_client.lrem(cache_key, 0, json.dumps(data['book']))
        print("[x] Done")

    channel.basic_consume(queue='book-favorites-queue', on_message_callback=callback, auto_ack=True)

    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()

if __name__ == '__main__':
    main()