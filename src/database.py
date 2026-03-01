import motor.motor_asyncio
from pymongo.errors import DuplicateKeyError

from config import settings

class DatabaseClient:
    """Lazily initialized singleton wrapper for MongoDB access."""

    _instance: "DatabaseClient | None" = None

    def __new__(cls) -> "DatabaseClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "db"):
            return
        connection_string = settings.mongo_uri.get_secret_value()
        self.client = motor.motor_asyncio.AsyncIOMotorClient(connection_string)
        self.db = self.client[settings.mercari_db_name]


db_client = DatabaseClient()


async def insert_links(item: dict) -> bool:
    """Insert a listing document and return whether it was new."""
    collection = db_client.db[settings.mercari_collection_name]

    try:
        await collection.insert_one(item)
        return True
    except DuplicateKeyError:
        return False
