from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from config import settings

# TODO: Use prisma instead of pymongo

def get_database() -> Database:
    CONNECTION_STRING = settings.mongo_uri.get_secret_value()
    client = MongoClient(CONNECTION_STRING)
    return client["mercari"]

dbname = get_database()

def insert_links(item) -> bool:
    collection = dbname["links"]

    try:
        collection.insert_one(item)
        print("Success: Item added.")
        return True
    except DuplicateKeyError:
        print("Item in DB (Skipped)")
        return False
