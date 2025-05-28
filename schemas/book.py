from pydantic import BaseModel
from datetime import datetime

class ISBN(BaseModel):
    identifier: str
    type: str

class ReadingProgess(BaseModel):
    page_bookmark: int = 0
    is_finished: bool = False


class Book(BaseModel):
    id: str
    title: str
    description: str | None = None
    page_count: int | None = None
    average_rating: float | int | None = None
    language: str | None = None
    authors: list[str] | None = None
    isbn: list[ISBN] | None = None
    genre: list[str] | None = None
    cover_img: list[str] | None = None
    is_favorite: bool = False
    reading_progress: ReadingProgess | None = None
