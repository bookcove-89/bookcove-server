from fastapi import APIRouter, HTTPException
from pymongo.errors import PyMongoError

from schemas.book import Book
from lib.mongo import DBClient

b_api = APIRouter()

@b_api.post("/add-to-favorite")
async def add_to_favorites(user_id: str, book: Book):
    try:
        client = DBClient.get_instance()
        
        # Create document
        doc = { 
            "user_id": user_id, 
            "book": book.model_dump()
        }
        
        # Insert into MongoDB
        collection = client.db['books']
        res = collection.insert_one(doc)
        
        return { "inserted_id": str(res.inserted_id) }
    
    except PyMongoError as mongo_err:
        raise HTTPException(status_code=500, detail="Database error. Please try again later.")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error.")
