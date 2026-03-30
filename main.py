# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import databases
import sqlalchemy
from datetime import datetime
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "").replace(
    "postgresql://", "postgresql+asyncpg://"
)

DATABASE_URL = "postgresql+asyncpg://user:password@localhost/dbname"

database = databases.Database(DATABASE_URL)

metadata = sqlalchemy.MetaData()

tracks = sqlalchemy.Table(
    "TRACKS",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.BigInteger, primary_key=True),
    sqlalchemy.Column("title", sqlalchemy.Text),
    sqlalchemy.Column("prompt", sqlalchemy.Text),
    sqlalchemy.Column("mp3_url", sqlalchemy.Text),
    sqlalchemy.Column("base64_data", sqlalchemy.Text),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime(timezone=True)),
    sqlalchemy.Column("status", sqlalchemy.Text, nullable=False),
    sqlalchemy.Column("failure_reason", sqlalchemy.Text),
    sqlalchemy.Column("blob_url", sqlalchemy.Text),
)

app = FastAPI()


# --- Schemas ---

class TrackCreate(BaseModel):
    title: Optional[str] = None
    prompt: Optional[str] = None
    mp3_url: Optional[str] = None
    base64_data: Optional[str] = None
    status: str
    failure_reason: Optional[str] = None
    blob_url: Optional[str] = None


class TrackUpdate(BaseModel):
    title: Optional[str] = None
    prompt: Optional[str] = None
    mp3_url: Optional[str] = None
    base64_data: Optional[str] = None
    status: Optional[str] = None
    failure_reason: Optional[str] = None
    blob_url: Optional[str] = None


class TrackOut(TrackCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Lifecycle ---

@app.on_event("startup")
async def startup():
    await database.connect()


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


# --- Routes ---

@app.get("/tracks", response_model=list[TrackOut])
async def get_tracks():
    query = tracks.select().order_by(tracks.c.created_at.desc())
    return await database.fetch_all(query)


@app.get("/tracks/{track_id}", response_model=TrackOut)
async def get_track(track_id: int):
    query = tracks.select().where(tracks.c.id == track_id)
    row = await database.fetch_one(query)
    if not row:
        raise HTTPException(status_code=404, detail="Track not found")
    return row


@app.post("/tracks", response_model=TrackOut, status_code=201)
async def create_track(track: TrackCreate):
    query = tracks.insert().values(**track.model_dump())
    track_id = await database.execute(query)
    return await database.fetch_one(
        tracks.select().where(tracks.c.id == track_id)
    )


@app.patch("/tracks/{track_id}", response_model=TrackOut)
async def update_track(track_id: int, track: TrackUpdate):
    existing = await database.fetch_one(
        tracks.select().where(tracks.c.id == track_id)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Track not found")

    updates = {k: v for k, v in track.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    await database.execute(
        tracks.update().where(tracks.c.id == track_id).values(**updates)
    )
    return await database.fetch_one(
        tracks.select().where(tracks.c.id == track_id)
    )


@app.delete("/tracks/{track_id}", status_code=204)
async def delete_track(track_id: int):
    existing = await database.fetch_one(
        tracks.select().where(tracks.c.id == track_id)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Track not found")
    await database.execute(
        tracks.delete().where(tracks.c.id == track_id)
    )