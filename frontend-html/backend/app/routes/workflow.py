from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional, Literal
import os

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from pydantic import BaseModel, Field
from app.database import database

router = APIRouter(prefix="/api/workflow", tags=["Portal workflow"])
security = HTTPBearer()
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"

# A lot can only be viewed or acted on inside its own portal.
SOURCE_ROLES = {
    "ewaste": {"producer", "manufacturer", "refurbisher"},
    "battery": {"producer", "refurbisher"},
    "plastic": {"pibo", "pwp", "ulb", "simp"},
    "rubber-tyre": {"producer", "retreader"},
    "metal": set(),
    "paper": {"ulb", "manufacturer"},
    "organic": {"waste-aggregator", "biogas-facility", "bio-cng-facility"},
    "oil-chemical": {"imported-used-oil", "producer"},
}
COLLECTOR_ROLES = {
    "ewaste": {"collector"},
    "battery": {"collector"},
    "plastic": {"collector"},
    "rubber-tyre": {"collector"},
    "metal": {"metal-collector", "non-metal-collector"},
    "paper": {"collector"},
    "organic": {"collector"},
    "oil-chemical": {"collector"},
}
RECYCLER_ROLES = {
    "ewaste": {"recycler"},
    "battery": {"recycler"},
    "plastic": {"recycler"},
    "rubber-tyre": {"recycler"},
    "metal": {"metal-recycler", "non-metal-recycler"},
    "paper": {"recycler"},
    "organic": {"biogas-facility", "bio-cng-facility"},
    "oil-chemical": {"recycler"},
}
PORTALS = set(SOURCE_ROLES)

async def current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        uid, portal, role = payload.get("sub"), payload.get("portal"), payload.get("role")
        if not uid or not ObjectId.is_valid(uid) or portal not in PORTALS:
            raise HTTPException(status_code=401, detail="Invalid workflow account.")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired access token.")
    user = await database.users.find_one({
        "_id": ObjectId(uid), "portal": portal, "role": role, "is_active": True
    })
    if not user:
        raise HTTPException(status_code=401, detail="User account not found or disabled.")
    user["_portal"] = portal
    user["_role"] = role
    return user

def _clean(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value

def public_lot(lot):
    return _clean(lot)


def display_name(user):
    return user.get("organisationName") or user.get("contactPerson") or user.get("fullName") or user.get("email")

class LotCreate(BaseModel):
    lotTitle: str = Field(min_length=2, max_length=120)
    wasteCategory: str = Field(min_length=2, max_length=100)
    material: str = Field(min_length=2, max_length=500)
    estimatedWeight: float = Field(gt=0)
    itemCount: Optional[int] = Field(default=None, ge=1)
    wasteCondition: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=2000)
    pickupAddress: str = Field(min_length=3, max_length=500)
    city: str = Field(min_length=2, max_length=100)
    preferredDate: Optional[str] = None
    preferredTime: Optional[str] = None
    expectedPrice: float = Field(gt=0)
    photos: list[str] = Field(default_factory=list, max_length=8)

class OfferRequest(BaseModel):
    amount: float = Field(gt=0)
    message: Optional[str] = Field(default=None, max_length=1000)

class ActionRequest(BaseModel):
    message: Optional[str] = Field(default=None, max_length=1000)
    recyclerId: Optional[str] = None

def same_portal(user, lot):
    if lot.get("portal") != user["_portal"]:
        raise HTTPException(status_code=404, detail="Lot not found in this portal.")

async def get_lot(lot_id, user):
    lot = await database.lots.find_one({"lot_id": lot_id, "portal": user["_portal"]})
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found in this portal.")
    return lot

@router.post("/lots", status_code=201)
async def create_lot(payload: LotCreate, user=Depends(current_user)):
    portal, role = user["_portal"], user["_role"]
    if role not in SOURCE_ROLES.get(portal, set()):
        raise HTTPException(status_code=403, detail="Only registered waste providers can create lots in this portal.")
    now = datetime.now(timezone.utc)
    lot = payload.model_dump()
    lot.update({
        "lot_id": "WS-" + uuid4().hex[:10].upper(),
        "portal": portal, "client_id": user["_id"], "client_role": role,
        "client_name": display_name(user), "client_email": user.get("email"),
        "status": "Created", "collector_id": None, "collector_name": None,
        "recycler_id": None, "recycler_name": None, "agreed_price": None,
        "collector_requests": [], "recycler_requests": [], "offers": [],
        "verified_weight": None, "payment_status": "Pending", "invoice_id": None,
        "created_at": now, "updated_at": now,
        "passport_history": [{"event": "Lot created", "status": "Created", "timestamp": now}],
    })
    result = await database.lots.insert_one(lot)
    return {"message": "Lot saved successfully.", "lot": public_lot(lot)}

@router.get("/lots/mine")
async def my_lots(user=Depends(current_user)):
    q = {"portal": user["_portal"], "$or": [{"client_id": user["_id"]}, {"collector_id": user["_id"]}, {"recycler_id": user["_id"]}, {"collector_requests.collector_id": user["_id"]}, {"recycler_requests.recycler_id": user["_id"]}]}
    cursor = database.lots.find(q).sort("created_at", -1)
    return {"lots": [public_lot(x) async for x in cursor]}

@router.get("/lots/available")
async def available_lots(user=Depends(current_user)):
    portal, role = user["_portal"], user["_role"]
    if role in COLLECTOR_ROLES.get(portal, set()):
        q = {"portal": portal, "status": {"$in": ["Created", "Collector Requested"]}, "collector_id": None}
    elif role in RECYCLER_ROLES.get(portal, set()):
        q = {"portal": portal, "collector_id": {"$ne": None}, "recycler_id": None, "recycler_requests.recycler_id": user["_id"]}
    else:
        raise HTTPException(status_code=403, detail="Available lots are for collectors and recyclers.")
    cursor = database.lots.find(q).sort("created_at", -1)
    return {"lots": [public_lot(x) async for x in cursor]}

@router.post("/lots/{lot_id}/collector-request")
async def collector_request(lot_id: str, body: ActionRequest, user=Depends(current_user)):
    portal, role = user["_portal"], user["_role"]
    if role not in COLLECTOR_ROLES.get(portal, set()):
        raise HTTPException(status_code=403, detail="Collector account required.")
    lot = await get_lot(lot_id, user)
    if lot.get("collector_id"):
        raise HTTPException(status_code=409, detail="A collector has already been accepted.")
    now = datetime.now(timezone.utc)
    await database.lots.update_one(
        {"_id": lot["_id"], "portal": portal, "collector_id": None},
        {"$addToSet": {"collector_requests": {"collector_id": user["_id"], "name": display_name(user), "role": role, "message": body.message, "requested_at": now}}, "$set": {"status": "Collector Requested", "updated_at": now}}
    )
    return {"message": "Request sent to the lot owner."}

@router.post("/lots/{lot_id}/collector-accept/{collector_id}")
async def accept_collector(lot_id: str, collector_id: str, user=Depends(current_user)):
    lot = await get_lot(lot_id, user)
    if lot["client_id"] != user["_id"]:
        raise HTTPException(status_code=403, detail="Only the lot owner can accept a collector.")
    if not ObjectId.is_valid(collector_id):
        raise HTTPException(status_code=400, detail="Invalid collector.")
    req = next((r for r in lot.get("collector_requests", []) if str(r.get("collector_id")) == collector_id), None)
    if not req:
        raise HTTPException(status_code=404, detail="Collector request not found.")
    now = datetime.now(timezone.utc)
    await database.lots.update_one({"_id": lot["_id"]}, {"$set": {
        "collector_id": ObjectId(collector_id), "collector_name": req["name"],
        "status": "Collector Accepted", "updated_at": now
    }, "$push": {"passport_history": {"event": "Collector accepted", "status": "Collector Accepted", "timestamp": now}}})
    return {"message": "Collector accepted."}

@router.get("/collectors/recyclers")
async def connected_recyclers(user=Depends(current_user)):
    if user["_role"] not in COLLECTOR_ROLES.get(user["_portal"], set()):
        raise HTTPException(status_code=403, detail="Collector account required.")
    roles = list(RECYCLER_ROLES.get(user["_portal"], set()))
    if not roles:
        return {"recyclers": []}
    cursor = database.users.find({"portal": user["_portal"], "role": {"$in": roles}, "is_active": True}, {"password_hash": 0})
    return {"recyclers": [{"id": str(x["_id"]), "name": display_name(x), "role": x["role"], "city": x.get("city")} async for x in cursor]}

@router.post("/lots/{lot_id}/recycler-request")
async def recycler_request(lot_id: str, body: ActionRequest, user=Depends(current_user)):
    if user["_role"] not in COLLECTOR_ROLES.get(user["_portal"], set()):
        raise HTTPException(status_code=403, detail="Collector account required.")
    lot = await get_lot(lot_id, user)
    if lot.get("collector_id") != user["_id"]:
        raise HTTPException(status_code=403, detail="Only the assigned collector can contact recyclers for this lot.")
    if not body.recyclerId or not ObjectId.is_valid(body.recyclerId):
        raise HTTPException(status_code=400, detail="Choose a valid recycler from this portal.")
    recycler = await database.users.find_one({"_id": ObjectId(body.recyclerId), "portal": user["_portal"], "role": {"$in": list(RECYCLER_ROLES.get(user["_portal"], set()))}, "is_active": True})
    if not recycler:
        raise HTTPException(status_code=404, detail="Recycler is not registered in this portal.")
    now = datetime.now(timezone.utc)
    await database.lots.update_one({"_id": lot["_id"]}, {"$set": {"status": "Recycler Requested", "updated_at": now},
        "$addToSet": {"recycler_requests": {"collector_id": user["_id"], "collector_name": display_name(user), "recycler_id": recycler["_id"], "recycler_name": display_name(recycler), "message": body.message, "requested_at": now}}})
    return {"message": "Recycler request recorded for this portal."}

@router.post("/lots/{lot_id}/recycler-accept")
async def accept_recycler(lot_id: str, user=Depends(current_user)):
    if user["_role"] not in RECYCLER_ROLES.get(user["_portal"], set()):
        raise HTTPException(status_code=403, detail="Recycler account required.")
    lot = await get_lot(lot_id, user)
    if not lot.get("collector_id") or lot.get("recycler_id"):
        raise HTTPException(status_code=409, detail="Lot is not available for recycler acceptance.")
    if not any(r.get("recycler_id") == user["_id"] for r in lot.get("recycler_requests", [])):
        raise HTTPException(status_code=403, detail="This lot was not requested from your recycler account.")
    now = datetime.now(timezone.utc)
    await database.lots.update_one({"_id": lot["_id"]}, {"$set": {
        "recycler_id": user["_id"], "recycler_name": display_name(user),
        "status": "Recycler Accepted", "updated_at": now
    }, "$push": {"passport_history": {"event": "Recycler accepted", "status": "Recycler Accepted", "timestamp": now}}})
    return {"message": "Lot accepted by recycler."}

@router.post("/lots/{lot_id}/offers")
async def create_offer(lot_id: str, payload: OfferRequest, user=Depends(current_user)):
    lot = await get_lot(lot_id, user)
    allowed = user["_id"] == lot.get("client_id") or user["_id"] == lot.get("collector_id") or user["_id"] == lot.get("recycler_id")
    if not allowed:
        raise HTTPException(status_code=403, detail="Only parties connected to this lot can negotiate.")
    now = datetime.now(timezone.utc)
    offer = {"offer_id": uuid4().hex[:12], "user_id": user["_id"], "name": display_name(user),
             "role": user["_role"], "amount": payload.amount, "message": payload.message,
             "status": "Pending", "created_at": now}
    await database.lots.update_one({"_id": lot["_id"]}, {"$push": {"offers": offer}, "$set": {"updated_at": now}})
    return {"message": "Price offer sent.", "offer_id": offer["offer_id"]}

@router.post("/lots/{lot_id}/offers/{offer_id}/accept")
async def accept_offer(lot_id: str, offer_id: str, user=Depends(current_user)):
    lot = await get_lot(lot_id, user)
    if user["_id"] not in [lot.get("client_id"), lot.get("collector_id"), lot.get("recycler_id")]:
        raise HTTPException(status_code=403, detail="Only parties connected to this lot can accept an offer.")
    offer = next((o for o in lot.get("offers", []) if o["offer_id"] == offer_id), None)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found.")
    if offer.get("user_id") == user["_id"]:
        raise HTTPException(status_code=400, detail="You cannot accept your own offer.")
    if lot.get("invoice_id"):
        raise HTTPException(status_code=409, detail="Negotiation is closed because an invoice has been generated.")
    now = datetime.now(timezone.utc)
    await database.lots.update_one({"_id": lot["_id"]}, {"$set": {
        "agreed_price": offer["amount"], "status": "Price Agreed", "updated_at": now,
        "offers.$[o].status": "Accepted"
    }, "$setOnInsert": {}, "$push": {"passport_history": {"event": "Price offer accepted", "status": "Price Agreed", "timestamp": now}},
       }, array_filters=[{"o.offer_id": offer_id}])
    await database.lots.update_one({"_id": lot["_id"]}, {"$set": {"offers.$[pending].status": "Closed"}}, array_filters=[{"pending.status": "Pending", "pending.offer_id": {"$ne": offer_id}}])
    return {"message": "Offer accepted.", "agreed_price": offer["amount"]}

@router.get("/transactions")
async def transactions(user=Depends(current_user)):
    cursor = database.invoices.find({"portal": user["_portal"], "$or": [
        {"client_id": user["_id"]}, {"collector_id": user["_id"]}, {"recycler_id": user["_id"]}
    ]}).sort("created_at", -1)
    return {"transactions": [public_lot(x) async for x in cursor]}

@router.post("/lots/{lot_id}/invoice")
async def create_invoice(lot_id: str, user=Depends(current_user)):
    lot = await get_lot(lot_id, user)
    if user["_id"] not in [lot.get("client_id"), lot.get("collector_id"), lot.get("recycler_id")]:
        raise HTTPException(status_code=403, detail="Only connected parties can create an invoice.")
    if not lot.get("agreed_price"):
        raise HTTPException(status_code=409, detail="Agree on a price before creating an invoice.")
    if lot.get("invoice_id"):
        existing = await database.invoices.find_one({"invoice_id": lot["invoice_id"], "portal": user["_portal"]})
        return {"invoice": public_lot(existing)} if existing else {"message": "Invoice already exists."}
    now = datetime.now(timezone.utc)
    invoice = {"invoice_id": "INV-" + uuid4().hex[:10].upper(), "lot_id": lot_id,
        "portal": user["_portal"], "client_id": lot["client_id"], "collector_id": lot.get("collector_id"),
        "recycler_id": lot.get("recycler_id"), "amount": lot["agreed_price"], "currency": "INR",
        "status": "Generated", "created_at": now}
    await database.invoices.insert_one(invoice)
    await database.lots.update_one({"_id": lot["_id"]}, {"$set": {"invoice_id": invoice["invoice_id"], "updated_at": now},
        "$push": {"passport_history": {"event": "Invoice generated", "status": "Invoice Generated", "timestamp": now}}})
    return {"invoice": public_lot(invoice)}

@router.get("/dashboard")
async def dashboard(user=Depends(current_user)):
    portal = user["_portal"]
    base = {"portal": portal}
    owned = await database.lots.count_documents({**base, "client_id": user["_id"]})
    involved = await database.lots.count_documents({**base, "$or": [{"collector_id": user["_id"]}, {"recycler_id": user["_id"]}, {"collector_requests.collector_id": user["_id"]}, {"recycler_requests.recycler_id": user["_id"]}]})
    invoices = await database.invoices.count_documents({**base, "$or": [{"client_id": user["_id"]}, {"collector_id": user["_id"]}, {"recycler_id": user["_id"]}, {"collector_requests.collector_id": user["_id"]}, {"recycler_requests.recycler_id": user["_id"]}]})
    return {"portal": portal, "role": user["_role"], "my_lots": owned + involved, "invoices": invoices}
