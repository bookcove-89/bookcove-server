from fastapi import APIRouter, HTTPException
import httpx, os, json

from lib.redis import redis_client
from schemas.book import Book, ReadingProgess
from schemas.search import SearchItem

s_api = APIRouter()

BASE_URL = os.getenv("BASE_URL") 
API_KEY = os.getenv("BOOK_API")

@s_api.get("/search")
async def search(bookname: str, max_results: int = 15, start_index: int = 0):
    # Check if the search term is empty
    if not bookname.strip():
        raise HTTPException(status_code=400, detail="Search item cannot be empty.")

    url = f"{BASE_URL}?q={bookname}&maxResults={max_results}&startIndex={start_index}&key={API_KEY}&printType=books&langRestrict=en"
    cache_key = f"books_{bookname}_{max_results}_{start_index}"
    cached_res = redis_client.get(cache_key)

    if cached_res:
        return {"book query": bookname, "cached": True, "data": json.loads(cached_res)}

    try:
        # Make an asynchronous request to the Google Books API
        async with httpx.AsyncClient() as client:
            response = await client.get(url)

            # If the response status code is not 200 (OK), raise an error
            response.raise_for_status()

            # Parse the JSON response
            data = response.json()

            # If no books are found, return an error message
            if "items" not in data:
                raise HTTPException(status_code=404, detail="No books found.")

            books = []
            for item in data.get('items', []):
                # Second API call to get higher res cover images 
                imgs_url = f"{BASE_URL}/{item.get('id')}"
                res = await client.get(imgs_url)
                res.raise_for_status()
                d = res.json()

                volume_info = item.get("volumeInfo", {})

                # Get the links to the cover
                cover_img_list = list(d['volumeInfo'].get("imageLinks", {}).values())

                # Get the ISBN's to the book
                isbn_list = list(volume_info.get("industryIdentifiers", []))

                # Description
                desc = d['volumeInfo'].get("description")

                # Create Book object
                book_data = Book(
                    id=item.get("id"),
                    title=volume_info.get("title", "Unknown Title"),
                    description=desc,
                    page_count=volume_info.get("pageCount"),
                    average_rating=volume_info.get("averageRating"),
                    language=volume_info.get("language"),
                    authors=volume_info.get("authors", []),
                    genre=volume_info.get("categories", []),
                    cover_img=cover_img_list,
                    isbn=isbn_list,
                    reading_progress=ReadingProgess()
                )
                if book_data.description is None:
                    continue
                books.append(book_data)
        redis_client.setex(cache_key, 600, json.dumps([book.dict() for book in books]))

        return {"book query": bookname, "cached": False, "data": books}

    except httpx.RequestError as e:
        # Handle errors that occur during the HTTP request
        raise HTTPException(status_code=500, detail=f"An error occurred while requesting the Google Books API: {e}")

    except httpx.HTTPStatusError as e:
        # Handle HTTP errors (e.g., 4xx, 5xx responses)
        raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error: {e.response.status_code}")


@s_api.post("/recent-searches")
def post_recent_searches(item: SearchItem):
    cache_key = "recent_searches"
    max_len = 5             # Max searches stored
    ttl_seconds = 86400 * 2     # 2 day (expiration time)

    # Check if the search term is empty
    if not item.search_item.strip():
        raise HTTPException(status_code=400, detail="Search item cannot be empty.")

    # Check if the search item is in the cache
    # if so, remove it and then it will be added to the front of the cache
    if item.search_item in redis_client.lrange(cache_key, 0, -1):
        redis_client.lrem(cache_key, 0, item.search_item)

    redis_client.lpush(cache_key, item.search_item) # Push to the front of list
    redis_client.ltrim(cache_key, 0, max_len - 1)   # Make sure only 10 items are kept
    redis_client.expire(cache_key, ttl_seconds)     # Set expiration 

    recent_searches = redis_client.lrange(cache_key, 0, -1)     # Get list of all items
    
    return {"recent_searches": recent_searches, "len" : len(recent_searches)}


@s_api.get("/recent-searches")
def get_recent_searches():
    cache_key = "recent_searches"
    max_len = 5            # Max searches stored

    redis_client.ltrim(cache_key, 0, max_len - 1)   # Make sure only 10 items are kept
    recent_searches = redis_client.lrange(cache_key, 0, -1)     # Get list of all items

    return {"recent_searches": recent_searches, "len" : len(recent_searches)}