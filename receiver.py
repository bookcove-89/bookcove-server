print("RECEIVER SCRIPT STARTED ----- TOP OF FILE") 

import pika, os, redis, json, time, sys

print("RECEIVER SCRIPT IMPORTS DONE")

redis_client: redis.Redis = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=6379, 
    db=0,
    decode_responses=True
)

print("RECEIVER SCRIPT REDIS CLIENT INITIALIZED (or attempted)") 

RABBITMQ_CONNECT_HOST = os.getenv("RABBITMQ_HOST", "localhost")
print(f"RECEIVER SCRIPT RABBITMQ_HOST: {RABBITMQ_CONNECT_HOST}")

def main():
    print("RECEIVER SCRIPT MAIN FUNCTION STARTED")
    connection, channel = None, None
    retry_interval = 5
    max_retries = 12 
    attempt = 0

    print(f" [CONSUMER] Using RABBITMQ_HOST: {RABBITMQ_CONNECT_HOST}")

    while attempt < max_retries:
        try:
            print(f" [CONSUMER] Attempting to connect to RabbitMQ at {RABBITMQ_CONNECT_HOST} (Attempt {attempt + 1}/{max_retries})...")
            connection_params = pika.ConnectionParameters(
                host=RABBITMQ_CONNECT_HOST,
                heartbeat=60, 
                blocked_connection_timeout=3
            )

            connection = pika.BlockingConnection(connection_params)
            channel = connection.channel()
            print(f" [CONSUMER] Successfully connected to RabbitMQ at {RABBITMQ_CONNECT_HOST}")


            channel.queue_declare(queue='book-favorites-queue', durable=True)
            print(" [CONSUMER] Queue 'book-favorites-queue' declared.")

            channel.queue_declare(queue='book-lib-queue', durable=True)
            print(" [CONSUMER] Queue 'book-lib-queue' declared.")
            break
        except pika.exceptions.AMQPConnectionError as e:
            print(f" [CONSUMER] RabbitMQ connection failed: {e}.")
            attempt += 1
            if attempt >= max_retries:
                print(" [CONSUMER] Max retries reached. Could not connect to RabbitMQ. Exiting.")
                sys.exit(1) 

            print(f" [CONSUMER] Retrying in {retry_interval} seconds...")
            time.sleep(retry_interval)

        except Exception as e_generic:
            print(f" [CONSUMER] An unexpected error occurred during RabbitMQ setup: {e_generic}")
            sys.exit(1)

    # Should have exited if connection failed after retries
    if not channel: 
        print(" [CONSUMER] Failed to establish RabbitMQ channel. Exiting.")
        return

    def fav_callback(ch, method, properties, body):
        print(f"[x] Received(fav): {body}")
        json_data = body.decode('utf-8')
        data = json.loads(json_data)
        cache_key = f"user_{data['user_id']}_books"

        if data['action'] ==  "added_favorite":
            # push new book to cache
            print("adding book to fav cache")
            redis_client.lpush(cache_key, json.dumps(data['book']))
        elif data['action'] == "remove_favorite":
            # remove from cache
            print("removing book from fav cache")
            redis_client.lrem(cache_key, 0, json.dumps(data['book']))
        print("[x] Done processing message(fav). ")
    
    def lib_callback(ch, method, properties, body):
        print(f"[x] Received(lib): {body}")
        json_data = body.decode('utf-8')
        data = json.loads(json_data)
        cache_key = f"user_{data['user_id']}_books"

        if data['action'] ==  "added_to_library":
            # push new book to cache
            print("adding book to lib cache")
            redis_client.lpush(cache_key, json.dumps(data['book']))
        elif data['action'] == "remove_from_library":
            # remove from cache
            print("removing book from lib cache")
            redis_client.lrem(cache_key, 0, json.dumps(data['book']))
        print("[x] Done processing message(lib). ")

    channel.basic_consume(queue='book-favorites-queue', on_message_callback=fav_callback, auto_ack=True)
    channel.basic_consume(queue='book-lib-queue', on_message_callback=lib_callback, auto_ack=True)

    print(f' [*] Waiting for messages on host {RABBITMQ_CONNECT_HOST}. To exit press CTRL+C')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print(" [CONSUMER] Shutting down...")
    except Exception as e:
        print(f" [CONSUMER] An error occurred during consumption: {e}")
    finally:
        if connection and not connection.is_closed:
            print(" [CONSUMER] Closing RabbitMQ connection.")
            connection.close()

if __name__ == '__main__':
    main()