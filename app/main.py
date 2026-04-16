import asyncio
import atexit
import os
import threading
from dataclasses import dataclass
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError


PORT = int(os.getenv("PORT", "3000"))
HOST = os.getenv("HOST", "0.0.0.0")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", f"http://localhost:{PORT}")
SESSION_DIR = os.getenv("SESSION_DIR", "sessions")

os.makedirs(SESSION_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")


@dataclass
class UserbotState:
    client: TelegramClient
    phone: str
    auto_reply_enabled: bool = False
    auto_reply_text: str = "I am currently away."


pending_clients: dict[str, TelegramClient] = {}
active_bots: dict[str, UserbotState] = {}


def session_path(phone: str) -> str:
    safe_phone = phone.replace("+", "")
    return os.path.join(SESSION_DIR, safe_phone)


bot_loop = asyncio.new_event_loop()


def _loop_worker() -> None:
    asyncio.set_event_loop(bot_loop)
    bot_loop.run_forever()


threading.Thread(target=_loop_worker, daemon=True).start()


def run_async(coro: Any) -> Any:
    future = asyncio.run_coroutine_threadsafe(coro, bot_loop)
    return future.result()


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
        await event.respond(f"✅ Auto-reply enabled. Message: {state.auto_reply_text}")

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


@app.get("/")
def index() -> str:
    with open("app/templates/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    return html.replace("{{PUBLIC_BASE_URL}}", PUBLIC_BASE_URL)


@app.get("/static/<path:path>")
def static_files(path: str) -> Any:
    return send_from_directory("app/static", path)


@app.get("/health")
def health() -> Any:
    return jsonify(
        {
            "status": "ok",
            "public_base_url": PUBLIC_BASE_URL,
            "active_sessions": len(active_bots),
        }
    )


@app.post("/api/v1/auth/start")
def auth_start() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        api_id = int(payload.get("api_id", 0))
    except (TypeError, ValueError):
        return jsonify({"detail": "api_id must be a number"}), 400

    api_hash = str(payload.get("api_hash", "")).strip()
    phone = str(payload.get("phone", "")).strip()

    if api_id < 1 or not api_hash or not phone:
        return jsonify({"detail": "api_id, api_hash, and phone are required"}), 400

    client = TelegramClient(session_path(phone), api_id, api_hash)
    run_async(client.connect())

    try:
        result = run_async(client.send_code_request(phone))
    except Exception as exc:
        run_async(client.disconnect())
        return jsonify({"detail": str(exc)}), 400

    pending_clients[phone] = client
    return jsonify(
        {
            "status": "code_sent",
            "phone": phone,
            "phone_code_hash": result.phone_code_hash,
        }
    )


@app.post("/api/v1/auth/verify-code")
def auth_verify_code() -> Any:
    payload = request.get_json(silent=True) or {}
    phone = str(payload.get("phone", "")).strip()
    code = str(payload.get("code", "")).strip()

    client = pending_clients.get(phone)
    if not client:
        return jsonify({"detail": "No pending auth for this phone"}), 404

    try:
        run_async(client.sign_in(phone=phone, code=code))
        run_async(start_userbot(client, phone))
        pending_clients.pop(phone, None)
        return jsonify({"status": "authorized", "phone": phone})
    except SessionPasswordNeededError:
        return jsonify({"status": "2fa_required", "phone": phone})
    except Exception as exc:
        return jsonify({"detail": str(exc)}), 400


@app.post("/api/v1/auth/verify-password")
def auth_verify_password() -> Any:
    payload = request.get_json(silent=True) or {}
    phone = str(payload.get("phone", "")).strip()
    password = str(payload.get("password", ""))

    client = pending_clients.get(phone)
    if not client:
        return jsonify({"detail": "No pending auth for this phone"}), 404

    try:
        run_async(client.sign_in(password=password))
        run_async(start_userbot(client, phone))
        pending_clients.pop(phone, None)
        return jsonify({"status": "authorized", "phone": phone})
    except Exception as exc:
        return jsonify({"detail": str(exc)}), 400


@atexit.register
def shutdown() -> None:
    for state in list(active_bots.values()):
        try:
            run_async(state.client.disconnect())
        except Exception:
            pass
    for client in list(pending_clients.values()):
        try:
            run_async(client.disconnect())
        except Exception:
            pass
    bot_loop.call_soon_threadsafe(bot_loop.stop)


if __name__ == "__main__":
    app.run(host=HOST, port=PORT)
