from fastapi import APIRouter, HTTPException, status
from pymongo.errors import PyMongoError

from lib.mongo import DBClient
from lib.redis import redis_client
from lib.rabbit import init_rabbit_mq
from schemas.requests import *
from schemas.book import Book
import json, logging
from utils.utils import datetime_serializer, send_msg

l_api = APIRouter()

RABBIT_QUEUE = "book-lib-queue"

@l_api.post("/add-book", status_code=status.HTTP_201_CREATED)
async def lib_add_book(request: AddToLibRequest):
    try:
        client = DBClient.get_instance()
        collection = client.db['books']
        
        if collection.find_one({ "user_id": request.user_id, "book.id": request.book.id }):
            logging.info(f"INFO: User '{request.user_id}' attempted to add book (ID: '{request.book.id}') which is already in library.")
            return send_msg(msg="Book is already in your library")

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
            "action": "added_to_library"
        }

        try:
            channel, connection = init_rabbit_mq()
            channel.queue_declare(queue=RABBIT_QUEUE, durable=True)
            channel.basic_publish(exchange='', routing_key=RABBIT_QUEUE, body=json.dumps(mq_msg_data))
        except Exception as mq_err:
            print(f"Error publishing to RabbitMQ (non-critical): {mq_err}")
        finally:
            if connection and connection.is_open:
                connection.close()
        
        return send_msg(msg="success", inserted_id=str(res.inserted_id))
    
    except PyMongoError as mongo_err:
        print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
        raise HTTPException(status_code=500, detail="Database error. Please try again later.")


@l_api.get("/my-books", status_code=status.HTTP_200_OK)
async def lib_my_books(uid: str):
    cache_key = f"user_{uid}_books_in_lib"

    # check if the users books in library are cached
    cached_books = redis_client.lrange(cache_key, 0, -1)
    if cached_books:
        cached_response = [Book(**json.loads(book_json_str)) for book_json_str in cached_books]
        return send_msg(msg="success", cache=True, books=cached_response)

    try:
        client = DBClient.get_instance()
        collection = client.db['books']
        
        books = []
        for book_doc in collection.find({ "user_id" : uid }):
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



@l_api.delete("/remove-my-book", status_code=status.HTTP_200_OK)
async def lib_remove_my_book(request: RemoveFromLibRequest):
    try:
        client = DBClient.get_instance()
        collection = client.db['books']
        
        query_filter = { "user_id" : request.user_id, "book.id" : request.book_id}
        book = collection.find_one(query_filter)
        res = collection.delete_one(query_filter)

        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Book not in users library.")
        
        if book:
            try:
                # RabbitMQ: send message
                mq_msg_data = {
                    "user_id": request.user_id,
                    "book": book['book'],
                    "action": "remove_from_library"
                }
                channel, connection = init_rabbit_mq()
                channel.queue_declare(queue=RABBIT_QUEUE, durable=True)
                channel.basic_publish(exchange='', routing_key=RABBIT_QUEUE, body=json.dumps(mq_msg_data))

                connection.close()
            except Exception as mq_err:
                print(f"Error publishing to RabbitMQ (non-critical): {mq_err}")
                logging.error(f"Error publishing to RabbitMQ (non-critical): {mq_err}")
            finally:
                if connection and connection.is_open:
                    connection.close()
        
        return send_msg(msg="Book removed from library", book_id=request.book_id) 
    except PyMongoError as mongo_err:
            print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
            logging.error(f"MongoDB error: {mongo_err}")
            raise HTTPException(status_code=500, detail="Database error. Please try again later.")


@l_api.patch("/update-book-progress", status_code=status.HTTP_200_OK)
async def lib_update_book_progress(request: UpdateBookProgress):
    try:
        client = DBClient.get_instance()
        collection = client.db['books']
        
        query_filter = { "user_id" : request.user_id, "book.id" : request.book_id}
        is_finished = False
        book = collection.find_one(query_filter)
        old_book_payload = book['book']

        if book:
            total_page_count = book['book']['page_count']
            print(total_page_count, request.page)
            # check the client page request num is within range of the book page count
            if request.page < 1 or request.page > total_page_count:
                raise HTTPException(status_code=400, detail="Page is out of range.")
            
            # if the client page request num is the same as the number of pages in book
            # mark the book as finished
            if request.page == total_page_count:
                is_finished = True

        update_data = { 
            "$set": { 
                "book.reading_progress.page_bookmark": request.page,
                "book.reading_progress.is_finished": is_finished,
            }
        }
        res = collection.update_one(query_filter, update_data)

        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Book not in users library.")
        
        if res.modified_count == 0 and res.matched_count > 0:
            return send_msg(msg="Book reading progress up to date.", book_id=request.book_id)

        updated_book = collection.find_one(query_filter)

        if book:
            try:
                # RabbitMQ: send message
                mq_msg_data = {
                    "user_id": request.user_id,
                    "old_book": old_book_payload,
                    "book": updated_book['book'],
                    "action": "update_book_from_library"
                }
                channel, connection = init_rabbit_mq()
                channel.queue_declare(queue=RABBIT_QUEUE, durable=True)
                channel.basic_publish(exchange='', routing_key=RABBIT_QUEUE, body=json.dumps(mq_msg_data))

                connection.close()
            except Exception as mq_err:
                print(f"Error publishing to RabbitMQ (non-critical): {mq_err}")
                logging.error(f"Error publishing to RabbitMQ (non-critical): {mq_err}")
            finally:
                if connection and connection.is_open:
                    connection.close()
        return send_msg(msg="Book progress updated.", book_id=request.book_id)
        
    except PyMongoError as mongo_err:
            print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
            logging.error(f"MongoDB error: {mongo_err}")
            raise HTTPException(status_code=500, detail="Database error. Please try again later.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=e)