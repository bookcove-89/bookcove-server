from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
import os

from routers.search_api import s_api
from routers.book_api import b_api
from lib.mongo import DBClient

load_dotenv()



DB_NAME = os.getenv("DB_NAME")
MONGO_URI = os.getenv("MONGO_URI")

mongo = DBClient.get_instance(uri=MONGO_URI, db_name=DB_NAME)

@asynccontextmanager
async def lifespan(fapp: FastAPI):
    yield
    mongo.close()

app = FastAPI(lifespan=lifespan)


app.include_router(s_api)
app.include_router(b_api, prefix="/book")
