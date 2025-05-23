from fastapi import APIRouter, HTTPException
from pymongo.errors import PyMongoError

from lib.mongo import DBClient
from lib.redis import redis_client
from schemas.requests import AddToFavoritesRequest
from schemas.requests import RemoveFavoriteRequest
from schemas.book import Book

b_api = APIRouter()

@b_api.post("/add-to-favorite")
async def add_to_favorites(request: AddToFavoritesRequest):
    try:
        client = DBClient.get_instance()
        collection = client.db['books']
        request.book.is_favorite = True
        
        # Create document
        doc = { 
            "user_id": request.user_id, 
            "book": request.book.model_dump()
        }

        # Insert into MongoDB
        res = collection.insert_one(doc)
        
        return { "msg" : "success", "inserted_id": str(res.inserted_id) }
    
    except PyMongoError as mongo_err:
        print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
        raise HTTPException(status_code=500, detail="Database error. Please try again later.")

    except Exception as e:
        status = e.status_code if e else 500
        raise HTTPException(status_code=status, detail=f"{e.detail if e else "Internal server error"}")

@b_api.patch("/remove-favorite")
async def remove_favorite(request: RemoveFavoriteRequest):
    try:
        client = DBClient.get_instance()
        collection = client.db['books'] 

        query_filter = { "user_id": request.user_id, "book.id": request.book_id }
        update_data = { "$set": { "book.is_favorite" : request.is_favorite }}

        res = collection.update_one(query_filter, update_data)

        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Favorite entry not found for this user and book.")
        
        if res.modified_count == 0 and res.matched_count > 0:
            # document was found, but the is_favorite status was already set to the requested value
            return {"msg": "Favorite status was already up to date.", "book_id": request.book_id, "is_favorite": request.is_favorite}

        # successfull update
        return {"msg": "Favorite status updated successfully.", "book_id": request.book_id, "is_favorite": request.is_favorite}
    
    except PyMongoError as mongo_err:
        print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
        raise HTTPException(status_code=500, detail="Database error. Please try again later.")

    except Exception as e:
        status = e.status_code if e else 500
        raise HTTPException(status_code=status, detail=f"{e.detail if e else "Internal server error"}")

@b_api.get("/get-favorites", response_model=list[Book])
async def get_favorites(uid: str):
    cache_key = f"user_{uid}_books"
    try:
        client = DBClient.get_instance()
        collection = client.db['books']

        books = []
        for book_doc in collection.find({ "user_id" : uid, "book.is_favorite": True }):
            books.append(Book(**book_doc['book']))

        if not books:
            print(f"No books found for user_id: {uid}")
            raise HTTPException(status_code=400, detail="No books found")

        return books 
    except PyMongoError as mongo_err:
            print(f"MongoDB error: {mongo_err}")  # Log MongoDB-specific error
            raise HTTPException(status_code=500, detail="Database error. Please try again later.")
    except Exception as e:
        status = e.status_code if e else 500
        raise HTTPException(status_code=status, detail=f"{e.detail if e else "Internal server error"}")