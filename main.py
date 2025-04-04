from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
import os, httpx, redis, json

from schemas.book import Book

load_dotenv()

app = FastAPI()

# NOTE: redis stores data as bytes so use 'json.dumps()' when storing and 'json.loads()' when retrieving
# default to 'redis' if 'localhost' doesn't work in docker container
redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379, db=0, decode_responses=True)

BASE_URL = os.getenv("BASE_URL") 
API_KEY = os.getenv("BOOK_API")

@app.get("/search")
async def search(bookname: str, max_results: int = 10, start_index: int = 0):
    url = f"{BASE_URL}?q={bookname}&maxResults={max_results}&startIndex={start_index}&key={API_KEY}"
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
            volume_info = item.get("volumeInfo", {})

            # Get the links to the cover
            cover_img_list = list(volume_info.get("imageLinks", {}).values())
            isbn_list = list(volume_info.get("industryIdentifiers", []))

            # Create Book object
            book_data = Book(
                id=item.get("id"),
                title=volume_info.get("title", "Unknown Title"),
                description=volume_info.get("description"),
                page_count=volume_info.get("pageCount"),
                average_rating=volume_info.get("averageRating"),
                language=volume_info.get("language"),
                authors=volume_info.get("authors", []),
                genre=volume_info.get("categories", []),
                cover_img=cover_img_list,
                isbn=isbn_list
            )
            books.append(book_data)
        redis_client.setex(cache_key, 600, json.dumps([book.dict() for book in books]))

        return {"book query": bookname, "cached": False, "data": books}

    except httpx.RequestError as e:
        # Handle errors that occur during the HTTP request
        raise HTTPException(status_code=500, detail=f"An error occurred while requesting the Google Books API: {e}")

    except httpx.HTTPStatusError as e:
        # Handle HTTP errors (e.g., 4xx, 5xx responses)
        raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error: {e.response.status_code}")
