from pydantic import BaseModel

class SearchItem(BaseModel):
    search_item: str
    uid: str | None = None