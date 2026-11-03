import os
from dotenv import load_dotenv
from pymongo import AsyncMongoClient

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "e-wastesetu")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is missing. Check backend/.env")

client = AsyncMongoClient(MONGODB_URI)
database = client[DATABASE_NAME]


async def connect_db():
    await client.admin.command("ping")

    # Unique indexes only apply to documents having a string email/phone.
    await database.users.create_index(
        "email",
        unique=True,
        partialFilterExpression={"email": {"$type": "string"}}
    )

    await database.users.create_index(
        "phone",
        unique=True,
        partialFilterExpression={"phone": {"$type": "string"}}
    )

    await database.lots.create_index([("portal", 1), ("lot_id", 1)], unique=True)
    await database.lots.create_index([("portal", 1), ("created_at", -1)])
    await database.invoices.create_index("invoice_id", unique=True)

    print(f"MongoDB connected successfully: {DATABASE_NAME}")


async def close_db():
    await client.close()