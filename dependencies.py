from crud.crud import MongoCRUD
from lib.mongo import DBClient

def get_crud_service() -> MongoCRUD:
    client = DBClient.get_instance()
    return MongoCRUD(client, "books")

