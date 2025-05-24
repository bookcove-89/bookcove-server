from fastapi import APIRouter, HTTPException
from pymongo.errors import PyMongoError

from lib.mongo import DBClient
from lib.redis import redis_client
from lib.rabbit import init_rabbit_mq
from schemas.requests import AddToFavoritesRequest
from schemas.requests import RemoveFavoriteRequest
from schemas.book import Book
import json, logging

b_api = APIRouter()

@b_api.post("/add-to-favorite")
async def add_to_favorites(request: AddToFavoritesRequest):
    try:
        client = DBClient.get_instance()
        collection = client.db['books']
        request.book.is_favorite = True
        
        if collection.find_one({ "user_id": request.user_id, "book.id": request.book.id, "book.is_favorite": True}):
            warning_message = (
                f"INFO: User '{request.user_id}' attempted to add book "
                f"(ID: '{request.book.id}') which is already marked as a favorite."
            )
            logging.info(warning_message)
            return {
                "msg": "Book is already in your favorites.",
                "is_favorite": True # Reflecting the existing state
            }

        # Create document
        doc = { 
            "user_id": request.user_id, 
            "book": request.book.model_dump()
        }

        # Insert into MongoDB
        res = collection.insert_one(doc)

        # RabbitMQ: send message
        mq_msg_data = {
            "user_id": request.user_id, 
            "book": request.book.model_dump(),
            "action": "added_favorite"
        }

        try:
            channel, connection = init_rabbit_mq()
            channel.queue_declare(queue="book-favorites-queue", durable=True)
            channel.basic_publish(exchange='', routing_key="book-favorites-queue", body=json.dumps(mq_msg_data))
        except Exception as mq_err:
            print(f"Error publishing to RabbitMQ (non-critical): {mq_err}")
        finally:
            if connection and connection.is_open:
                connection.close()
        
        return { "msg" : "success", "inserted_id": str(res.inserted_id) }
    
    except PyMongoError as mongo_err:
        print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
        raise HTTPException(status_code=500, detail="Database error. Please try again later.")

    except Exception as e:
        status = e.status_code if e else 500
        raise HTTPException(status_code=status, detail="Internal server error")

@b_api.patch("/remove-favorite")
async def remove_favorite(request: RemoveFavoriteRequest):
    try:
        client = DBClient.get_instance()
        collection = client.db['books'] 

        query_filter = { "user_id": request.user_id, "book.id": request.book_id }
        update_data = { "$set": { "book.is_favorite" : request.is_favorite }}
        book = collection.find_one(query_filter)

        res = collection.update_one(query_filter, update_data)

        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Favorite entry not found for this user and book.")
        
        if res.modified_count == 0 and res.matched_count > 0:
            # document was found, but the is_favorite status was already set to the requested value
            return {"msg": "Favorite status was already up to date.", "book_id": request.book_id, "is_favorite": request.is_favorite}
        if book:
            # RabbitMQ: send message
            mq_msg_data = {
                "user_id": request.user_id,
                "book": book['book'],
                "action": "remove_favorite"
            }
        try:
            channel, connection = init_rabbit_mq()
            channel.queue_declare(queue="book-favorites-queue", durable=True)
            channel.basic_publish(exchange='', routing_key="book-favorites-queue", body=json.dumps(mq_msg_data))

            connection.close()
        except Exception as mq_err:
            print(f"Error publishing to RabbitMQ (non-critical): {mq_err}")
            logging.error(f"Error publishing to RabbitMQ (non-critical): {mq_err}")
        finally:
            if connection and connection.is_open:
                connection.close()
            

        # successfull update
        return {"msg": "Favorite status updated successfully.", "book_id": request.book_id, "is_favorite": request.is_favorite}
    
    except PyMongoError as mongo_err:
        print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
        raise HTTPException(status_code=500, detail="Database error. Please try again later.")

    except Exception as e:
        status = e.status_code if e else 500
        raise HTTPException(status_code=status, detail="Internal server error")

@b_api.get("/get-favorites", response_model=list[Book])
async def get_favorites(uid: str):
    cache_key = f"user_{uid}_books"

    # Check if the users favorite books are cached
    cached_favorites = redis_client.lrange(cache_key, 0, -1)
    if cached_favorites:
        cached_response = [Book(**json.loads(book_json_str)) for book_json_str in cached_favorites]
        return cached_response

    try:
        client = DBClient.get_instance()
        collection = client.db['books']

        books = []
        for book_doc in collection.find({ "user_id" : uid, "book.is_favorite": True }):
            bk = Book(**book_doc['book'])
            books.append(bk)

            # add to cache
            redis_client.lpush(cache_key, json.dumps(book_doc['book']))

        if not books:
            print(f"No books found for user_id: {uid}")
            raise HTTPException(status_code=400, detail="No books found")

        return books 
    except PyMongoError as mongo_err:
            print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
            logging.error(f"MongoDB error: {mongo_err}")
            raise HTTPException(status_code=500, detail="Database error. Please try again later.")
    except Exception as e:
        status = e.status_code if e else 500
        raise HTTPException(status_code=status, detail="Internal server error")