from schemas.book import Book
from pydantic import BaseModel
from datetime import datetime

class BaseRequest(BaseModel):
    user_id: str
    book_id: str 

class AddToFavoritesRequest(BaseModel):
    user_id: str
    book: Book

class RemoveFavoriteRequest(BaseRequest):
    is_favorite: bool

class RemoveFromLibRequest(BaseRequest):
    pass

class AddToLibRequest(BaseModel):
    user_id: str
    book: Book

class UpdateBookProgress(BaseRequest):
    page: int