from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import logging

class DBClient:
    _instance = None
    
    def __init__(self, uri: str = "uri", db_name: str = "db_name"):
        if DBClient._instance is not None:
            raise Exception("this is a singleton clasee")

        self.client = MongoClient(uri, tls=True, tlsAllowInvalidCertificates=True,server_api=ServerApi('1') )
        try:
            self.client.admin.command('ping')
            logging.info("Pinged your deployment. You successfully connected to MongoDB!")
        except Exception as e:
            print(e)

        self.db = self.client[db_name]
        DBClient._instance = self
    
    @staticmethod
    def get_instance(uri: str = "uri", db_name: str = "db_name"):
        if DBClient._instance is None:
            DBClient(uri, db_name)  
        return DBClient._instance
    
    def close(self):
        logging.info("closing db connection")
        self.client.close()
        DBClient._instance = None
