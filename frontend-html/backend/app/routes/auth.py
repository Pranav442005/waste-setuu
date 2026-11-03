import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from passlib.context import CryptContext
from jose import jwt
from pymongo.errors import DuplicateKeyError

from app.database import database

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is missing. Add it to backend/.env")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24

PORTAL_ROLES = {
    "domestic": {"household", "administration"},
    "ewaste": {"producer", "manufacturer", "collector", "recycler", "refurbisher"},
    "battery": {"producer", "recycler", "refurbisher"},
    "plastic": {"pibo", "pwp", "ulb", "simp", "collector"},
    "rubber-tyre": {"producer", "collector", "recycler", "retreader"},
    "metal": {"metal-collector", "metal-recycler", "non-metal-collector", "non-metal-recycler"},
    "paper": {"ulb", "collector", "manufacturer", "recycler"},
    "organic": {"waste-aggregator", "collector", "biogas-facility", "bio-cng-facility"},
    "oil-chemical": {"imported-used-oil", "collector", "producer", "recycler"},
}

PORTAL_ALIASES = {
    "e-waste": "ewaste", "e_waste": "ewaste", "e waste": "ewaste",
    "rubber": "rubber-tyre", "rubber-tyres": "rubber-tyre", "tyres": "rubber-tyre",
    "oil": "oil-chemical", "oil-chemicals": "oil-chemical",
}
ROLE_ALIASES = {
    "nonmetal-collector": "non-metal-collector",
    "nonmetal-recycler": "non-metal-recycler",
    "biogas": "biogas-facility", "bio-cng": "bio-cng-facility",
    "wasteaggregator": "waste-aggregator", "imported-usedoil": "imported-used-oil",
}


def canonical_portal(value: str) -> str:
    value = (value or "").strip().lower()
    return PORTAL_ALIASES.get(value, value)


def canonical_role(value: str) -> str:
    value = (value or "").strip().lower().replace("_", "-").replace(" ", "-")
    while "--" in value:
        value = value.replace("--", "-")
    return ROLE_ALIASES.get(value, value)


def normalize_account(portal: str, role: str):
    portal = canonical_portal(portal)
    role = canonical_role(role)
    if portal not in PORTAL_ROLES or role not in PORTAL_ROLES[portal]:
        raise HTTPException(status_code=400, detail="Unsupported portal or account role. Check the selected portal and account type.")
    return portal, role


def validate_bcrypt_password(value: str) -> str:
    # bcrypt processes at most 72 UTF-8 bytes; checking bytes avoids runtime 500 errors.
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must be no more than 72 UTF-8 bytes. Please choose a shorter password.")
    return value


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fullName: Optional[str] = None
    organisationType: Optional[str] = None
    organisationName: Optional[str] = None
    contactPerson: Optional[str] = None
    email: EmailStr
    phone: str = Field(min_length=10, max_length=10, pattern=r"^[0-9]{10}$")
    password: str = Field(min_length=8, max_length=128)
    houseNumber: Optional[str] = None
    buildingName: Optional[str] = None
    street: str
    city: str
    district: str
    state: str
    pincode: str = Field(pattern=r"^[0-9]{6}$")
    gstNumber: Optional[str] = None
    registrationNumber: Optional[str] = None
    cpcbAuthorizationNumber: Optional[str] = None
    activityDetails: Optional[str] = None
    processingCapacity: Optional[str] = None
    serviceArea: Optional[str] = None
    portal: str = "domestic"
    role: str

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, value):
        return validate_bcrypt_password(value)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    portal: str = "domestic"
    role: str

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, value):
        return validate_bcrypt_password(value)


def create_access_token(user_id: str, portal: str, role: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "portal": portal, "role": role, "exp": expires}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest):
    portal, role = normalize_account(payload.portal, payload.role)
    email = str(payload.email).strip().lower()

    if portal == "domestic" and role == "household" and not payload.fullName:
        raise HTTPException(status_code=422, detail="Full name is required for household registration.")
    if portal == "domestic" and role == "administration":
        if not all([payload.organisationType, payload.organisationName, payload.contactPerson]):
            raise HTTPException(status_code=422, detail="Organisation type, organisation name and contact person are required.")
    if portal != "domestic":
        required = [payload.organisationType, payload.organisationName, payload.contactPerson,
                    payload.registrationNumber, payload.activityDetails]
        if not all(required):
            raise HTTPException(status_code=422, detail="Organisation type, organisation name, contact person, registration number and activity details are required.")

    existing = await database.users.find_one({"$or": [{"email": email}, {"phone": payload.phone}]})
    if existing:
        if existing.get("email") == email:
            existing_portal = canonical_portal(existing.get("portal", ""))
            existing_role = canonical_role(existing.get("role", ""))
            if existing_portal == portal and existing_role == role:
                raise HTTPException(status_code=409, detail="This account already exists. Please use Login.")
            raise HTTPException(status_code=409, detail=f"This email is already registered as {existing_portal}/{existing_role}. Use that account's login page or a different email.")
        raise HTTPException(status_code=409, detail="This mobile number is already registered.")

    user_data = payload.model_dump(exclude={"password"})
    user_data["email"] = email
    user_data["portal"] = portal
    user_data["role"] = role
    user_data["password_hash"] = pwd_context.hash(payload.password)
    user_data["created_at"] = datetime.now(timezone.utc)
    user_data["is_active"] = True
    try:
        result = await database.users.insert_one(user_data)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="This email address or mobile number is already registered.")
    return {"message": "Account created successfully. Please log in.", "user_id": str(result.inserted_id)}


@router.post("/login")
async def login(payload: LoginRequest):
    portal, role = normalize_account(payload.portal, payload.role)
    email = str(payload.email).strip().lower()

    # Verify credentials first, then explain a portal/role mismatch without exposing account data to strangers.
    user = await database.users.find_one({"email": email})
    password_hash = user.get("password_hash") if user else None
    try:
        password_ok = bool(password_hash) and pwd_context.verify(payload.password, password_hash)
    except (ValueError, TypeError):
        password_ok = False
    if not user or not password_ok:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    stored_portal = canonical_portal(user.get("portal", ""))
    stored_role = canonical_role(user.get("role", ""))
    if stored_portal != portal or stored_role != role:
        raise HTTPException(
            status_code=403,
            detail=f"This account is registered as {stored_portal}/{stored_role}. Open the matching portal and account-type login page."
        )
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="This account is disabled. Contact the administrator.")

    # Normalize legacy aliases once, so all subsequent JWT and workflow lookups use canonical values.
    if user.get("portal") != portal or user.get("role") != role:
        await database.users.update_one({"_id": user["_id"]}, {"$set": {"portal": portal, "role": role}})

    token = create_access_token(str(user["_id"]), portal, role)
    return {
        "message": "Login successful.",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user["_id"]), "email": user["email"], "role": role,
            "portal": portal,
            "name": user.get("fullName") or user.get("organisationName") or user.get("contactPerson"),
        },
    }
