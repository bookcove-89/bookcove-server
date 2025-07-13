from lib.mongo import DBClient

class MongoCRUD:
    def __init__(self, client: DBClient, collection_name: str):
        self.client = client
        self.collection = self.client.db[collection_name]
    
    async def create_document(self, query: dict[str, any]) -> str:
        """
        Creates a new document in the collection.
        Returns the ID of the newly created document.
        """
        try:
            res = self.collection.insert_one(query)
            return str(res.inserted_id)
        except Exception as e:
            print(f"Error creating document: {e}")
            return None

    
    async def update_document(self, query: dict[str, any], update_data: dict[str, any]) -> int:
        """
        Updates one or more documents in the collection based on the query.
        Returns the number of modified documents.
        """
        try:
            res = self.collection.update_many(query, {"$set": update_data})
            return res.modified_count
        except Exception as e:
            print(f"Error updating document: {e}")
            return 0
    
    async def read_document(self, query: dict[str, any]) -> dict[str, any] | None:
        """
        Reads a single document from the collection based on the query.
        Returns the document if found, otherwise None.
        """
        try:
            doc = self.collection.find_one(query)
            return doc
        except Exception as e:
            print(f"Error reading document: {e}")
            return None

    async def read_documents(self, query: dict[str, any], limit: int = 0) -> list[dict[str, any]]:
        """
        Reads multiple documents from the collection based on the query.
        Returns a list of documents.
        """
        try:
            cursor = self.collection.find(query)
            if limit > 0:
                cursor = cursor.limit(limit)
            return list(cursor)
        except Exception as e:
            print(f"Error reading documents: {e}")
            return []  
    
    async def delete_document(self, query: dict[str, any]) -> int:
        """
        Deletes one or more documents from the collection based on the query.
        Returns the number of deleted documents.
        """
        try:
            result = self.collection.delete_many(query)
            return result.deleted_count
        except Exception as e:
            print(f"Error deleting document: {e}")
            return 0

    async def doc_exists(self, query: dict[str, any]) -> bool:
        """
        Checks if a document exists in the collection based on the query.
        """
        return await self.read_document(query) is not None