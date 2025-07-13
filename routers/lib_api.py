from fastapi import APIRouter, HTTPException, status, Depends
from pymongo.errors import PyMongoError
from redis.exceptions import RedisError
from lib.mongo import DBClient
from lib.redis import redis_client
from lib.rabbit import init_rabbit_mq
from schemas.requests import *
from schemas.book import Book
from utils.utils import send_msg
from crud.crud import MongoCRUD
from dependencies import get_crud_service
import json, logging, constants

l_api = APIRouter()

RABBIT_QUEUE = constants.RABBIT_QUEUE_LIB

@l_api.post("/add-book", status_code=status.HTTP_201_CREATED)
async def add_book(request: AddToLibRequest, crud_service: MongoCRUD = Depends(get_crud_service)):
    try:
        if await crud_service.doc_exists({ "user_id": request.user_id, "book.id": request.book.id }):
            logging.info(f"INFO: User '{request.user_id}' attempted to add book (ID: '{request.book.id}') which is already in library.")
            return send_msg(msg="Book is already in your library")

        channel, connection = init_rabbit_mq()
        channel.queue_declare(queue=RABBIT_QUEUE, durable=True)

        # Create & insert document
        res = await crud_service.create_document
        (
            {   "user_id": request.user_id, 
                "book": request.book.model_dump()
            }
        )

        # RabbitMQ: send message
        mq_msg_data = {
            "user_id": request.user_id, 
            "book": request.book.model_dump(),
            "action": constants.ADD_LIB 
        }
            
        channel.basic_publish(exchange='', routing_key=RABBIT_QUEUE, body=json.dumps(mq_msg_data))
        
        return send_msg(msg="success", inserted_id=res)
    
    except PyMongoError as mongo_err:
        print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
        raise HTTPException(status_code=500, detail="Database error. Please try again later.")
    except Exception as mq_err:
        print(f"Error publishing to RabbitMQ (non-critical): {mq_err}")
    finally:
        if connection and connection.is_open:
            connection.close()


@l_api.get("/my-books", status_code=status.HTTP_200_OK)
async def my_books(uid: str, crud_service: MongoCRUD = Depends(get_crud_service)):
    cache_key = constants.LIB_CACHE_KEY(uid)
    try:
        # check if the users books in library are cached
        cached_books = redis_client.lrange(cache_key, 0, -1)
        if cached_books:
            cached_response = [Book(**json.loads(book_json_str)) for book_json_str in cached_books]
            return send_msg(msg="success", cache=True, books=cached_response)

        books = []
        for book_doc in await crud_service.read_documents({ "user_id" : uid}):
            bk = Book(**book_doc['book'])
            books.append(bk)

            # add to cache
            redis_client.lpush(cache_key, json.dumps(book_doc['book']))
            redis_client.expire(cache_key, 86400)     # Set expiration 
        if not books:
            print(f"No books found for user_id: {uid}")
            raise HTTPException(status_code=400, detail="No books found")
        
        return send_msg(msg="success", book=books)

    except PyMongoError as mongo_err:
        print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
        logging.error(f"MongoDB error: {mongo_err}")
        raise HTTPException(status_code=500, detail="Database error. Please try again later.")
    except RedisError as redis_err:
        print(f"Redis error: {redis_err}")  # Log Redis-specific error
        logging.error(f"Redis error: {redis_err}")
        raise HTTPException(status_code=500, detail="Redis error. Please try again later.") 


@l_api.delete("/remove-my-book", status_code=status.HTTP_200_OK)
async def remove_my_book(request: RemoveFromLibRequest, crud_service: MongoCRUD = Depends(get_crud_service)):
    try:
        channel, connection = init_rabbit_mq()
        channel.queue_declare(queue=RABBIT_QUEUE, durable=True)

        query_filter = { "user_id" : request.user_id, "book.id" : request.book_id}

        book = await crud_service.read_document(query_filter)
        res = await crud_service.delete_document(query_filter)

        if res == 0:
            raise HTTPException(status_code=404, detail="Book not in users library.")
        
        if book:
            # RabbitMQ: send message
            mq_msg_data = {
                "user_id": request.user_id,
                "book": book['book'],
                "action": constants.RM_LIB 
            }

            channel.basic_publish(exchange='', routing_key=RABBIT_QUEUE, body=json.dumps(mq_msg_data))
        
        return send_msg(msg="Book removed from library", book_id=request.book_id) 
    except PyMongoError as mongo_err:
            print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
            logging.error(f"MongoDB error: {mongo_err}")
            raise HTTPException(status_code=500, detail="Database error. Please try again later.")
    except Exception as mq_err:
        print(f"Error publishing to RabbitMQ (non-critical): {mq_err}")
        logging.error(f"Error publishing to RabbitMQ (non-critical): {mq_err}")
    finally:
        if connection and connection.is_open:
            connection.close()


@l_api.patch("/update-book-progress", status_code=status.HTTP_200_OK)
async def update_book_progress(request: UpdateBookProgress, crud_service: MongoCRUD = Depends(get_crud_service)):
    try:
        channel, connection = init_rabbit_mq()
        channel.queue_declare(queue=RABBIT_QUEUE, durable=True)
        
        query_filter = { "user_id" : request.user_id, "book.id" : request.book_id}
        is_finished, is_reading = False, True 

        book = await crud_service.read_document(query_filter)
        old_book_payload = book['book']

        if book:
            total_page_count = book['book']['page_count']
            # check the client page request num is within range of the book page count
            if request.page < 1 or request.page > total_page_count:
                raise HTTPException(status_code=400, detail="Page is out of range.")
            
            # if the client page request num is the same as the number of pages in book
            # mark the book as finished
            if request.page == total_page_count:
                is_finished = True
                is_reading = False

        update_data = { 
            "book.reading_progress.page_bookmark": request.page,
            "book.reading_progress.is_finished": is_finished,
            "book.reading_progress.is_reading": is_reading,
        }

        # res = collection.update_one(query_filter, update_data)
        res = await crud_service.update_document(query_filter, update_data)

        if res == 0:
            raise HTTPException(status_code=404, detail="Book not in users library.")
        
        updated_book = await crud_service.read_document(query_filter)

        if book:
            # RabbitMQ: send message
            mq_msg_data = {
                "user_id": request.user_id,
                "old_book": old_book_payload,
                "book": updated_book['book'],
                "action": constants.UPDATE_LIB
            }
            
            channel.basic_publish(exchange='', routing_key=RABBIT_QUEUE, body=json.dumps(mq_msg_data))
  
        return send_msg(msg="Book progress updated.", book_id=request.book_id)
        
    except PyMongoError as mongo_err:
        print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
        logging.error(f"MongoDB error: {mongo_err}")
        raise HTTPException(status_code=500, detail="Database error. Please try again later.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=e)
    except Exception as mq_err:
        print(f"Error publishing to RabbitMQ (non-critical): {mq_err}")
        logging.error(f"Error publishing to RabbitMQ (non-critical): {mq_err}")
    finally:
        if connection and connection.is_open:
            connection.close()


# TODO: add caching to methods below
@l_api.get("/completed-books", status_code=status.HTTP_200_OK)
async def completed_books(uid: str, crud_service: MongoCRUD = Depends(get_crud_service)):
    # cache_key = f"user_{uid}_books_in_lib"

    # # check if the users books in library are cached
    # cached_books = redis_client.lrange(cache_key, 0, -1)
    # if cached_books:
    #     cached_response = [Book(**json.loads(book_json_str)) for book_json_str in cached_books]
    #     return send_msg(msg="success", cache=True, books=cached_response)

    try:
        books = []
        for book_doc in await crud_service.read_documents({ "user_id" : uid }):
            if book_doc['book']['reading_progress'] and book_doc['book']['reading_progress']['is_finished']:
                bk = Book(**book_doc['book'])
                books.append(bk)

            # add to cache
            # redis_client.lpush(cache_key, json.dumps(book_doc['book']))
            # redis_client.expire(cache_key, 86400)     # Set expiration 

        if not books:
            print(f"No completed books found for user_id: {uid}")
            raise HTTPException(status_code=400, detail="No finished books found")
        
        return send_msg(msg="success", books=books)
        
    except PyMongoError as mongo_err:
            print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
            logging.error(f"MongoDB error: {mongo_err}")
            raise HTTPException(status_code=500, detail="Database error. Please try again later.")


@l_api.get("/in-progress-books", status_code=status.HTTP_200_OK)
async def in_progress_books(uid: str, crud_service: MongoCRUD = Depends(get_crud_service)):
    # cache_key = f"user_{uid}_books_in_lib"

    # # check if the users books in library are cached
    # cached_books = redis_client.lrange(cache_key, 0, -1)
    # if cached_books:
    #     cached_response = [Book(**json.loads(book_json_str)) for book_json_str in cached_books]
    #     return send_msg(msg="success", cache=True, books=cached_response)

    try:
        client = DBClient.get_instance()
        collection = client.db['books']
        
        books = []
        for book_doc in await crud_service.read_documents({ "user_id" : uid }):
            if book_doc['book']['reading_progress'] and book_doc['book']['reading_progress']['is_reading']:
                bk = Book(**book_doc['book'])
                books.append(bk)

            # add to cache
            # redis_client.lpush(cache_key, json.dumps(book_doc['book']))
            # redis_client.expire(cache_key, 86400)     # Set expiration 
        if not books:
            print(f"No books in progress found for user_id: {uid}")
            raise HTTPException(status_code=400, detail="No finished books found")
            
        return send_msg(msg="success", books=books)
    except PyMongoError as mongo_err:
            print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
            logging.error(f"MongoDB error: {mongo_err}")
            raise HTTPException(status_code=500, detail="Database error. Please try again later.")