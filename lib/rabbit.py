import pika, os

# RabbitMQ connection parameters
# RABBITMQ_HOST = 'localhost' # Default if running RabbitMQ locally
# RABBITMQ_PORT = 5672 # Default port, usually not needed in ConnectionParameters unless non-default
# RABBITMQ_USER = 'guest' # Default user
# RABBITMQ_PASS = 'guest' # Default password
# RABBITMQ_VHOST = '/' # Default virtual host

def init_rabbit_mq():
    host = os.getenv("RABBITMQ_HOST", "localhost")
    try:
        connection_params = pika.ConnectionParameters(host=host)
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()
        
        print("channel opened sucessfully")
        return channel, connection
        
    except pika.exceptions.AMQPConnectionError as e:
        print(f"Error: Failed to connect to RabbitMQ at {host}.")
        print(f"Details: {e}")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred during RabbitMQ initialization: {e}")
        return None, None