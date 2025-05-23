from schemas.book import Book
from pydantic import BaseModel

class AddToFavoritesRequest(BaseModel):
    user_id: str
    book: Book

class RemoveFavoriteRequest(BaseModel):
    user_id: str
    book_id: str
    is_favorite: bool
    