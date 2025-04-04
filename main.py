from annotated_types import IsNan
from fastapi import FastAPI, HTTPException
import httpx
from dotenv import load_dotenv
import os
from schemas.book import Book, ISBN

load_dotenv()

app = FastAPI()
BASE_URL = "https://www.googleapis.com/books/v1/volumes"
API_KEY = os.getenv("BOOK_API")

@app.get("/search")
async def search(bookname: str, max_results: int = 10, start_index: int = 0):
    url = f"{BASE_URL}?q={bookname}&maxResults={max_results}&startIndex={start_index}&key={API_KEY}"

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
        # TODO: parse and clean the response to return ONLY the important details
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
        return books

    except httpx.RequestError as e:
        # Handle errors that occur during the HTTP request
        raise HTTPException(status_code=500, detail=f"An error occurred while requesting the Google Books API: {e}")

    except httpx.HTTPStatusError as e:
        # Handle HTTP errors (e.g., 4xx, 5xx responses)
        raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error: {e.response.status_code}")
