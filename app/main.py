import asyncio
import os
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError


PORT = int(os.getenv("PORT", "3000"))
HOST = os.getenv("HOST", "0.0.0.0")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", f"http://localhost:{PORT}")
STATIC_API_KEY = os.getenv("STATIC_API_KEY", "cypherus-v1")
SESSION_DIR = os.getenv("SESSION_DIR", "sessions")

os.makedirs(SESSION_DIR, exist_ok=True)

app = FastAPI(title="Cypherus Userbot")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@dataclass
class UserbotState:
    client: TelegramClient
    phone: str
    auto_reply_enabled: bool = False
    auto_reply_text: str = "I am currently away."


pending_clients: dict[str, TelegramClient] = {}
active_bots: dict[str, UserbotState] = {}


class StartAuthRequest(BaseModel):
    api_id: int = Field(..., ge=1)
    api_hash: str
    phone: str


class VerifyCodeRequest(BaseModel):
    phone: str
    code: str


class VerifyPasswordRequest(BaseModel):
    phone: str
    password: str


def session_path(phone: str) -> str:
    safe_phone = phone.replace("+", "")
    return os.path.join(SESSION_DIR, safe_phone)


async def start_userbot(client: TelegramClient, phone: str) -> None:
    if phone in active_bots:
        return

    state = UserbotState(client=client, phone=phone)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.ping$"))
    async def ping_handler(event: events.NewMessage.Event) -> None:
        await event.respond("🏓 Pong")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.autoreply on(?:\s+(.+))?$"))
    async def autoreply_on(event: events.NewMessage.Event) -> None:
        reply_text = event.pattern_match.group(1)
        state.auto_reply_enabled = True
        if reply_text:
            state.auto_reply_text = reply_text
        await event.respond(
            f"✅ Auto-reply enabled. Message: {state.auto_reply_text}"
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.autoreply off$"))
    async def autoreply_off(event: events.NewMessage.Event) -> None:
        state.auto_reply_enabled = False
        await event.respond("⛔ Auto-reply disabled")

    @client.on(events.NewMessage(incoming=True))
    async def incoming_autoreply(event: events.NewMessage.Event) -> None:
        if state.auto_reply_enabled and not event.is_private:
            return
        if state.auto_reply_enabled and not event.out:
            await event.respond(state.auto_reply_text)

    active_bots[phone] = state


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    html = (open("app/templates/index.html", "r", encoding="utf-8")).read()
    html = html.replace("{{PUBLIC_BASE_URL}}", PUBLIC_BASE_URL)
    html = html.replace("{{STATIC_API_KEY}}", STATIC_API_KEY)
    return HTMLResponse(html)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "public_base_url": PUBLIC_BASE_URL,
        "static_api_key": STATIC_API_KEY,
        "active_sessions": len(active_bots),
    }


@app.post(f"/api/v1/{STATIC_API_KEY}/auth/start")
async def auth_start(payload: StartAuthRequest) -> dict[str, Any]:
    phone = payload.phone.strip()
    client = TelegramClient(session_path(phone), payload.api_id, payload.api_hash)
    await client.connect()

    try:
        result = await client.send_code_request(phone)
    except Exception as exc:
        await client.disconnect()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pending_clients[phone] = client
    return {
        "status": "code_sent",
        "phone": phone,
        "phone_code_hash": result.phone_code_hash,
    }


@app.post(f"/api/v1/{STATIC_API_KEY}/auth/verify-code")
async def auth_verify_code(payload: VerifyCodeRequest) -> dict[str, Any]:
    phone = payload.phone.strip()
    client = pending_clients.get(phone)
    if not client:
        raise HTTPException(status_code=404, detail="No pending auth for this phone")

    try:
        await client.sign_in(phone=phone, code=payload.code.strip())
        await start_userbot(client, phone)
        pending_clients.pop(phone, None)
        return {"status": "authorized", "phone": phone}
    except SessionPasswordNeededError:
        return {"status": "2fa_required", "phone": phone}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(f"/api/v1/{STATIC_API_KEY}/auth/verify-password")
async def auth_verify_password(payload: VerifyPasswordRequest) -> dict[str, Any]:
    phone = payload.phone.strip()
    client = pending_clients.get(phone)
    if not client:
        raise HTTPException(status_code=404, detail="No pending auth for this phone")

    try:
        await client.sign_in(password=payload.password)
        await start_userbot(client, phone)
        pending_clients.pop(phone, None)
        return {"status": "authorized", "phone": phone}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.on_event("shutdown")
async def shutdown() -> None:
    tasks = [state.client.disconnect() for state in active_bots.values()]
    tasks.extend(client.disconnect() for client in pending_clients.values())
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
