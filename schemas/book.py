from pydantic import BaseModel

class ISBN(BaseModel):
    identifier: str
    type: str


class Book(BaseModel):
    id: str
    title: str
    description: str
    page_count: int | None = None
    average_rating: float | None = None
    language: str | None = None
    authors: list[str]
    isbn: list[ISBN] | None = None
    genre: list[str]
    cover_img: list[str] | None = None
