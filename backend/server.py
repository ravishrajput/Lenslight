from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import FastAPI, APIRouter, Response, Request, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field

from auth_utils import hash_password, verify_password, create_access_token, get_current_user
from mock_data import splunk_mock, bigquery_mock, build_artifacts
from llm_service import analyze
from pdf_service import build_report_pdf

# ----- Mongo -----
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="InsightLens API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("insightlens")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _set_jwt_cookie(resp: Response, token: str):
    resp.set_cookie("access_token", token, httponly=True, secure=True, samesite="none", max_age=7 * 24 * 3600, path="/")


def _set_session_cookie(resp: Response, token: str):
    resp.set_cookie("session_token", token, httponly=True, secure=True, samesite="none", max_age=7 * 24 * 3600, path="/")


async def current_user(request: Request):
    return await get_current_user(request, db)


# ---------- Pydantic ----------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ChatCreateIn(BaseModel):
    title: Optional[str] = None


class ChatRenameIn(BaseModel):
    title: str


class SendMessageIn(BaseModel):
    content: str
    sources: list[str] = Field(default_factory=lambda: ["splunk", "bigquery"])


# ---------- Auth ----------
@api.post("/auth/register")
async def register(payload: RegisterIn, response: Response):
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    doc = {
        "user_id": user_id,
        "email": email,
        "name": payload.name,
        "picture": None,
        "password_hash": hash_password(payload.password),
        "provider": "password",
        "created_at": _now().isoformat(),
    }
    await db.users.insert_one(doc)
    token = create_access_token(user_id, email)
    _set_jwt_cookie(response, token)
    return {"user_id": user_id, "email": email, "name": payload.name, "picture": None, "token": token}


@api.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    email = payload.email.lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not user.get("password_hash") or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user["user_id"], email)
    _set_jwt_cookie(response, token)
    return {"user_id": user["user_id"], "email": email, "name": user["name"], "picture": user.get("picture"), "token": token}


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(user=Depends(current_user)):
    return {"user_id": user["user_id"], "email": user["email"], "name": user["name"], "picture": user.get("picture")}


@api.post("/auth/google/session")
async def google_session(request: Request, response: Response):
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
        session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")
    async with httpx.AsyncClient(timeout=15.0) as http:
        r = await http.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session")
    data = r.json()
    email = (data.get("email") or "").lower()
    name = data.get("name") or email
    picture = data.get("picture")
    session_token = data["session_token"]

    user = await db.users.find_one({"email": email}, {"_id": 0})
    if user is None:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "provider": "google",
            "created_at": _now().isoformat(),
        })
    else:
        user_id = user["user_id"]
        await db.users.update_one({"user_id": user_id}, {"$set": {"name": name, "picture": picture}})

    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": (_now() + timedelta(days=7)).isoformat(),
        "created_at": _now().isoformat(),
    })
    _set_session_cookie(response, session_token)
    return {"user_id": user_id, "email": email, "name": name, "picture": picture}


# ---------- Connections ----------
@api.get("/connections")
async def list_connections(user=Depends(current_user)):
    return {
        "connections": [
            {"id": "splunk", "name": "Splunk Enterprise", "status": "connected", "mode": "mock",
             "accent": "#F24E1E", "endpoint": "https://splunk.internal:8089",
             "description": "Operational log analytics & SIEM. Query via SPL."},
            {"id": "bigquery", "name": "Google BigQuery", "status": "connected", "mode": "mock",
             "accent": "#007AFF", "endpoint": "bigquery.googleapis.com",
             "description": "Serverless warehouse for analytical SQL."},
        ]
    }


# ---------- Chats ----------
def _chat_doc_to_out(doc):
    return {
        "chat_id": doc["chat_id"],
        "title": doc["title"],
        "created_at": doc["created_at"],
        "updated_at": doc.get("updated_at", doc["created_at"]),
    }


@api.get("/chats")
async def list_chats(user=Depends(current_user)):
    cursor = db.chats.find({"user_id": user["user_id"]}, {"_id": 0}).sort("updated_at", -1)
    chats = [_chat_doc_to_out(c) async for c in cursor]
    return {"chats": chats}


@api.post("/chats")
async def create_chat(payload: ChatCreateIn, user=Depends(current_user)):
    chat_id = f"chat_{uuid.uuid4().hex[:12]}"
    now = _now().isoformat()
    doc = {
        "chat_id": chat_id,
        "user_id": user["user_id"],
        "title": payload.title or "New analysis",
        "created_at": now,
        "updated_at": now,
    }
    await db.chats.insert_one(doc)
    doc.pop("_id", None)
    return _chat_doc_to_out(doc)


@api.patch("/chats/{chat_id}")
async def rename_chat(chat_id: str, payload: ChatRenameIn, user=Depends(current_user)):
    r = await db.chats.update_one(
        {"chat_id": chat_id, "user_id": user["user_id"]},
        {"$set": {"title": payload.title, "updated_at": _now().isoformat()}},
    )
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"ok": True}


@api.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, user=Depends(current_user)):
    await db.chats.delete_one({"chat_id": chat_id, "user_id": user["user_id"]})
    await db.messages.delete_many({"chat_id": chat_id, "user_id": user["user_id"]})
    return {"ok": True}


@api.get("/chats/{chat_id}/messages")
async def get_messages(chat_id: str, user=Depends(current_user)):
    chat = await db.chats.find_one({"chat_id": chat_id, "user_id": user["user_id"]}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    cursor = db.messages.find({"chat_id": chat_id, "user_id": user["user_id"]}, {"_id": 0}).sort("created_at", 1)
    msgs = [m async for m in cursor]
    return {"chat": _chat_doc_to_out(chat), "messages": msgs}


# ---------- Chat send ----------
@api.post("/chats/{chat_id}/messages")
async def send_message(chat_id: str, payload: SendMessageIn, user=Depends(current_user)):
    chat = await db.chats.find_one({"chat_id": chat_id, "user_id": user["user_id"]}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Store user message
    user_msg = {
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "chat_id": chat_id,
        "user_id": user["user_id"],
        "role": "user",
        "content": payload.content,
        "sources": payload.sources,
        "artifacts": [],
        "created_at": _now().isoformat(),
    }
    await db.messages.insert_one(user_msg)
    user_msg.pop("_id", None)

    # Query mock data sources
    sources_data = []
    if "splunk" in payload.sources:
        sources_data.append(splunk_mock(payload.content))
    if "bigquery" in payload.sources:
        sources_data.append(bigquery_mock(payload.content))

    artifacts = build_artifacts(sources_data)

    # Call LLM
    markdown = await analyze(payload.content, sources_data, session_id=chat_id)

    assistant_msg = {
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "chat_id": chat_id,
        "user_id": user["user_id"],
        "role": "assistant",
        "content": markdown,
        "sources": payload.sources,
        "artifacts": artifacts,
        "created_at": _now().isoformat(),
    }
    await db.messages.insert_one(assistant_msg)
    assistant_msg.pop("_id", None)

    # Auto-title chat from first user message
    update = {"updated_at": _now().isoformat()}
    if chat["title"] == "New analysis":
        update["title"] = payload.content[:60] + ("…" if len(payload.content) > 60 else "")
    await db.chats.update_one({"chat_id": chat_id}, {"$set": update})

    return {"user_message": user_msg, "assistant_message": assistant_msg}


# ---------- PDF export ----------
@api.get("/messages/{message_id}/pdf")
async def message_pdf(message_id: str, user=Depends(current_user)):
    msg = await db.messages.find_one({"message_id": message_id, "user_id": user["user_id"]}, {"_id": 0})
    if not msg or msg["role"] != "assistant":
        raise HTTPException(status_code=404, detail="Report not found")
    # Fetch the preceding user question
    chat_msgs = await db.messages.find(
        {"chat_id": msg["chat_id"], "user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", 1).to_list(1000)
    question = "User query"
    for i, m in enumerate(chat_msgs):
        if m["message_id"] == message_id and i > 0 and chat_msgs[i - 1]["role"] == "user":
            question = chat_msgs[i - 1]["content"]
            break

    pdf = build_report_pdf(question, msg["content"], msg.get("artifacts", []))
    filename = f"insightlens-report-{msg['message_id']}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Health ----------
@api.get("/")
async def root():
    return {"service": "InsightLens API", "status": "ok"}


app.include_router(api)

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.chats.create_index([("user_id", 1), ("updated_at", -1)])
    await db.messages.create_index([("chat_id", 1), ("created_at", 1)])
    await db.user_sessions.create_index("session_token", unique=True)

    # Idempotent demo user seed — guarantees login works with .env creds
    demo_email = os.environ.get("DEMO_EMAIL", "").lower()
    demo_password = os.environ.get("DEMO_PASSWORD", "")
    if demo_email and demo_password:
        existing = await db.users.find_one({"email": demo_email})
        if existing is None:
            await db.users.insert_one({
                "user_id": f"user_{uuid.uuid4().hex[:12]}",
                "email": demo_email,
                "name": "Demo",
                "picture": None,
                "password_hash": hash_password(demo_password),
                "provider": "password",
                "created_at": _now().isoformat(),
            })
            log.info(f"Demo user seeded: {demo_email}")
        elif not verify_password(demo_password, existing.get("password_hash", "")):
            await db.users.update_one(
                {"email": demo_email},
                {"$set": {"password_hash": hash_password(demo_password)}},
            )
            log.info(f"Demo user password refreshed: {demo_email}")

    log.info("InsightLens API started.")


@app.on_event("shutdown")
async def shutdown():
    client.close()
