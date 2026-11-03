
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from dotenv import load_dotenv
load_dotenv()

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from pydantic import BaseModel, Field, ConfigDict

from app.database import database

router = APIRouter(prefix="/api/domestic", tags=["Domestic Dashboard"])

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is missing in backend/.env")

JWT_ALGORITHM = "HS256"
security = HTTPBearer()

# ---------------- AUTHENTICATION ----------------

async def get_current_domestic_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )
        user_id = payload.get("sub")
        portal = payload.get("portal")
        role = payload.get("role")

        if not user_id or portal != "domestic" or role not in {"household", "administration"}:
            raise HTTPException(
                status_code=403,
                detail="Domestic household or administration access required."
            )

        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=401, detail="Invalid user token.")

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token."
        )

    user = await database.users.find_one({
        "_id": ObjectId(user_id),
        "portal": "domestic",
        "role": role,
        "is_active": True
    })

    if not user:
        raise HTTPException(status_code=401, detail="User account not found.")

    return user


# ---------------- LOT REQUEST MODEL ----------------

class LotCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lotTitle: str = Field(min_length=2, max_length=120)
    wasteCategory: str
    material: str = Field(min_length=2, max_length=500)
    estimatedWeight: float = Field(gt=0)
    itemCount: Optional[int] = Field(default=None, ge=1)
    wasteCondition: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=2000)

    pickupAddress: str = Field(min_length=3, max_length=500)
    city: str = Field(min_length=2, max_length=100)
    preferredDate: Optional[str] = None
    preferredTime: Optional[str] = None


ALLOWED_CATEGORIES = {
    "Plastic",
    "Paper",
    "Metal",
    "E-waste",
    "Battery",
    "Rubber & Tyre",
    "Organic",
    "Oil & Chemical",
    "Mixed"
}


def serialize_lot(lot):
    lot["_id"] = str(lot["_id"])
    lot["client_id"] = str(lot["client_id"])
    return lot


# ---------------- CREATE LOT ----------------

@router.post("/lots", status_code=status.HTTP_201_CREATED)
async def create_lot(
    payload: LotCreateRequest,
    current_user: dict = Depends(get_current_domestic_user)
):
    if payload.wasteCategory not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail="Invalid waste category."
        )

    now = datetime.now(timezone.utc)

    lot_data = payload.model_dump()

    lot_data.update({
        "lot_id": "WS-" + uuid4().hex[:10].upper(),
        "client_id": current_user["_id"],
        "client_name": (
            current_user.get("organisationName")
            or current_user.get("contactPerson")
            or current_user.get("fullName")
        ),
        "client_email": current_user.get("email"),
        "portal": "domestic",
        "status": "Created",
        "collector_id": None,
        "pickup_schedule": None,
        "verified_weight": None,
        "payment_status": "Pending",
        "invoice_id": None,
        "created_at": now,
        "updated_at": now,
        "passport_history": [
            {
                "event": "Lot created",
                "status": "Created",
                "timestamp": now
            }
        ],
        "photos": []
    })

    result = await database.lots.insert_one(lot_data)

    saved_lot = await database.lots.find_one({
        "_id": result.inserted_id
    })

    return {
        "message": "Waste lot created successfully.",
        "lot": serialize_lot(saved_lot)
    }


# ---------------- VIEW MY LOTS ----------------

@router.get("/lots")
async def get_my_lots(
    current_user: dict = Depends(get_current_domestic_user)
):
    cursor = database.lots.find({
        "client_id": current_user["_id"],
        "portal": "domestic"
    }).sort("created_at", -1)

    lots = []

    async for lot in cursor:
        lots.append(serialize_lot(lot))

    return {
        "total": len(lots),
        "lots": lots
    }


# ---------------- VIEW LOT PASSPORT ----------------

@router.get("/lots/{lot_id}/passport")
async def get_lot_passport(
    lot_id: str,
    current_user: dict = Depends(get_current_domestic_user)
):
    lot = await database.lots.find_one({
        "lot_id": lot_id,
        "client_id": current_user["_id"],
        "portal": "domestic"
    })

    if not lot:
        raise HTTPException(
            status_code=404,
            detail="Lot passport not found."
        )

    return {
        "passport": serialize_lot(lot)
    }
