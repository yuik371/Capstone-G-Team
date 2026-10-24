import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("환경변수 설정 필요")




client = AsyncIOMotorClient(MONGO_URI, tls=True)
db = client["emergency_system"]

users_collection = db["users"]
hospitals_collection = db["hospitals"]
patients_collection = db["patients"]
amb_collection = db["amb"]


