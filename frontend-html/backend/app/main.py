from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import connect_db, close_db
from app.routes.auth import router as auth_router
from app.routes.auth2 import router as domestic_router
from app.routes.translate import router as translate_router
from app.routes.workflow import router as workflow_router
from app.routes.assistant import router as assistant_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    try:
        yield
    finally:
        await close_db()


app = FastAPI(
    title="Waste Setu API",
    description="Waste Management and Recycling Platform",
    version="1.2.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://waste-setuu-1.onrender.com",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0.0.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



app.include_router(auth_router)
app.include_router(domestic_router)
app.include_router(translate_router)
app.include_router(workflow_router)
app.include_router(assistant_router)


@app.get("/")
async def home():
    return {"message": "Welcome to Waste Setu Backend", "status": "Running successfully"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
