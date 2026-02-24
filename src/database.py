import motor.motor_asyncio
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from config import settings

# TODO: Need to change db hierarchy for other sites, just mainly a db naming thing.

class GetDatabase:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'db'): 
            connection_string = settings.mongo_uri.get_secret_value()
            self.client = motor.motor_asyncio.AsyncIOMotorClient(connection_string)
            self.db = self.client["mercari"]

db_singleton = GetDatabase()

async def insert_links(item) -> bool:
    collection = db_singleton.db["links"]

    try:
        await collection.insert_one(item)
        # print("Success: Item added.")
        return True
    except DuplicateKeyError:
        # print("Item in DB (Skipped)")
        return False
