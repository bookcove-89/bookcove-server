from fastapi import APIRouter, HTTPException, status, Depends
from pymongo.errors import PyMongoError
from redis.exceptions import RedisError
from lib.mongo import DBClient
from lib.redis import redis_client
from lib.rabbit import init_rabbit_mq
from schemas.requests import *
from schemas.book import Book
from utils.utils import datetime_serializer, send_msg
from crud.crud import MongoCRUD
from dependencies import get_crud_service 
import json, logging, constants

b_api = APIRouter()

RABBIT_QUEUE = constants.RABBIT_QUEUE_FAV

@b_api.post("/add-to-favorite", status_code=status.HTTP_201_CREATED)
async def add_to_favorites(request: AddToFavoritesRequest, crud_service: MongoCRUD = Depends(get_crud_service), ):
    try:
        request.book.is_favorite = True
        query = { "user_id" : request.user_id, "book.id" : request.book.id }
        fav_query = {**query, "book.is_favorite" : True}

        # Book is already marked as favorite
        existing_fav = await crud_service.read_document(fav_query)
        if existing_fav:
            logging.info(f"INFO: User '{request.user_id}' attempted to add book (ID: '{request.book.id}') which is already marked as a favorite.")
            return send_msg(msg="Book is already in favorites", is_favorite=True)

        channel, connection = init_rabbit_mq()
        channel.queue_declare(queue=RABBIT_QUEUE, durable=True)

        # Book is already in user library but not in favorites
        book_in_lib = await crud_service.read_document(query)
        if book_in_lib:
            print(f"im here and this is the book: {book_in_lib}")
            update_data = { "book.is_favorite" : True }
            modified_count = await crud_service.update_document(query, update_data)

            # Error updating favorite status
            if modified_count == 0:
                logging.info(f"INFO: User '{request.user_id}' attempted to add book (ID: '{request.book.id}') which is not found & can't be added to favorites.")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found and can't be added as favorite")
            
            new_book = await crud_service.read_document(query) 
            # want to update the 'favorite' status in cache
            mq_msg_data = {
                "user_id" : request.user_id,
                "old_book" : book_in_lib,
                "new_book" : new_book['book'],
                "action" : constants.UPDATED_FAV
            }

            channel.basic_publish(exchange='', routing_key=RABBIT_QUEUE, body=json.dumps(mq_msg_data, default=datetime_serializer))
            return send_msg(msg="success", detail="Book in library successfully updated to favorite.")
            
        # Book not in lib or in favorites
        else: 
            # Create document
            doc = { 
                "user_id": request.user_id, 
                "book": request.book.model_dump()
            }

            # Insert into MongoDB
            inserted_id = await crud_service.create_document(doc)

            # Check if doc creation failed
            if inserted_id is None:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add book to favorites.")

            # RabbitMQ: send message
            mq_msg_data = {
                "user_id": request.user_id, 
                "book": request.book.model_dump(),
                "action": constants.ADD_FAV 
            }

            channel.basic_publish(exchange='', routing_key=RABBIT_QUEUE, body=json.dumps(mq_msg_data, default=datetime_serializer))

            return send_msg(msg="success") 
    
    except PyMongoError as mongo_err:
        print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
        raise HTTPException(status_code=500, detail="Database error. Please try again later.")
    except Exception as mq_err:
        print(f"Error publishing to RabbitMQ (non-critical): {mq_err}")
    finally:
        if connection and connection.is_open:
            connection.close()


@b_api.patch("/remove-favorite", status_code=status.HTTP_200_OK)
async def remove_favorite(request: RemoveFavoriteRequest, crud_service: MongoCRUD = Depends(get_crud_service)):
    try:
        channel, connection = init_rabbit_mq()
        channel.queue_declare(queue=RABBIT_QUEUE, durable=True)
        client = DBClient.get_instance()
        collection = client.db['books'] 

        query_filter = { "user_id": request.user_id, "book.id": request.book_id }
        update_data = { "$set": { "book.is_favorite" : request.is_favorite }}

        book = await crud_service.read_document(query_filter)

        res = collection.update_one(query_filter, update_data)

        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Favorite entry not found for this user and book.")
        
        if res.modified_count == 0 and res.matched_count > 0:
            # document was found, but the is_favorite status was already set to the requested value
            return send_msg(msg="Favorite status already up to date.", book_id=request.book_id, is_favorite=request.is_favorite)

        if book:
            # RabbitMQ: send message
            mq_msg_data = {
                "user_id": request.user_id,
                "book": book['book'],
                "action": constants.RM_FAV
            }
    
        channel.basic_publish(exchange='', routing_key=RABBIT_QUEUE, body=json.dumps(mq_msg_data, default=datetime_serializer))

        # successfull update
        return send_msg(msg="Book added to favorites.", book_id=request.book_id, is_favorite=request.is_favorite)
    
    except PyMongoError as mongo_err:
        print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
        raise HTTPException(status_code=500, detail="Database error. Please try again later.")
    except Exception as mq_err:
        print(f"Error publishing to RabbitMQ (non-critical): {mq_err}")
        logging.error(f"Error publishing to RabbitMQ (non-critical): {mq_err}")
    finally:
        if connection and connection.is_open:
            connection.close()


@b_api.get("/get-favorites", status_code=status.HTTP_200_OK)
async def get_favorites(uid: str, crud_service: MongoCRUD = Depends(get_crud_service)):
    cache_key = constants.FAV_CACHE_KEY(uid)

    try:
        # Check if the users favorite books are cached
        cached_favorites = redis_client.lrange(cache_key, 0, -1)
        if cached_favorites:
            cached_response = [Book(**json.loads(book_json_str)) for book_json_str in cached_favorites]
            return send_msg(msg="success", cache=True, books=cached_response)

        books = []

        for book_doc in await crud_service.read_documents({ "user_id" : uid, "book.is_favorite": True }):
            bk = Book(**book_doc['book'])
            books.append(bk)

            # add to cache
            redis_client.lpush(cache_key, json.dumps(book_doc['book']))

        redis_client.expire(cache_key, 86400)     # Set expiration 

        if not books:
            print(f"No favorite books found for user_id: {uid}")
            raise HTTPException(status_code=404, detail="No books found")

        return send_msg(msg="success", book=books)
        
    except PyMongoError as mongo_err:
        print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
        logging.error(f"MongoDB error: {mongo_err}")
        raise HTTPException(status_code=500, detail="Database error. Please try again later.")
    except RedisError as redis_err:
        print(f"Redis error: {redis_err}")  # Log Redis-specific error
        logging.error(f"Redis error: {redis_err}")
        raise HTTPException(status_code=500, detail="Redis error. Please try again later.") 

