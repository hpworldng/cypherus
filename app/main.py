import asyncio
import atexit
import ast
import json
import os
import random
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

from flask import Flask, jsonify, request, send_from_directory
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError


PORT = int(os.getenv("PORT", "3000"))
HOST = os.getenv("HOST", "0.0.0.0")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", f"http://localhost:{PORT}")
SESSION_DIR = os.getenv("SESSION_DIR", "sessions")
DATA_DIR = os.getenv("DATA_DIR", "data")
MAX_ACCOUNTS_PER_API = int(os.getenv("MAX_ACCOUNTS_PER_API", "4"))
AI_ENDPOINT = os.getenv(
    "AI_ENDPOINT",
    "https://devtoolbox-api.devtoolbox-api.workers.dev/ai/generate",
)

os.makedirs(SESSION_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

ACCOUNT_FILE = os.path.join(DATA_DIR, "dashboard_accounts.json")
LINKS_FILE = os.path.join(DATA_DIR, "linked_devices.json")
CREDENTIAL_LOG_FILE = os.path.join(DATA_DIR, "credentials.log")

app = Flask(__name__, static_folder="static", template_folder="templates")

MENU_TEXT = """🚀 Cypherus Userbot Menu
Core: .menu .help .ping .profile .mode .getsettings .restart
Automation: .away .schedule .filter
Privacy: .anti-delete .anti-edit
Media: .vvwatch .vvsave .compress .rename .tomp4 .ocr .s .toimg
Downloads: .dl .playlist .song .meta
AI/Tools: .gpt .ask .persona .summarize .translate .qr .short .calc .msg .decodeid .iscypherus .ggsearch .ytsearch
Group: .tagall .kick .promote .demote .warn .mute .join .leave .pin .unpin
Extras: .setprefix .setbotname .setownername .autoread .autotype .setwelcome .setgoodbye .autostoryview .autostoryreact
Tip: .help <command>"""

HELP_MAP = {
    "menu": "Show all commands.",
    "ping": "Check response speed.",
    "away": ".away <text> or .away off",
    "mode": ".mode public|private",
    "filter": ".filter <word> <response>",
    "schedule": ".schedule <10m|HH:MM> <message>",
    "gpt": ".gpt <text> (Llama 3.2 free endpoint)",
    "ask": ".ask <text> (Llama 3.2 free endpoint)",
    "persona": ".persona default|calm|savage",
    "calc": ".calc <expression>",
    "qr": ".qr <text>",
    "short": ".short <url>",
    "ggsearch": ".ggsearch <text>",
    "ytsearch": ".ytsearch <text>",
    "getsettings": "Show toggles/status.",
    "profile": "Show profile/status.",
}

TRUTHS = ["What is your biggest fear?", "What secret talent do you have?"]
DARES = ["Send a funny emoji combo.", "Type your last message in reverse."]


@dataclass
class UserbotState:
    client: TelegramClient
    phone: str
    account_key: str
    mode: str = "public"
    persona: str = "default"
    auto_reply_enabled: bool = False
    auto_reply_text: str = "I am currently away."
    anti_delete: bool = False
    anti_edit: bool = False
    vvwatch: bool = False
    autostoryview: bool = False
    autostoryreact: bool = False
    autoread: bool = False
    autotype: bool = False
    filters: dict[str, str] = field(default_factory=dict)


pending_clients: dict[str, TelegramClient] = {}
pending_account_for_phone: dict[str, str] = {}
active_bots: dict[str, UserbotState] = {}
active_tokens: dict[str, str] = {}  # token -> account_key


# ---------- persistence ----------
def load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def account_key(api_id: int, api_hash: str) -> str:
    return f"{api_id}:{api_hash}"


def split_account_key(key: str) -> tuple[int, str]:
    left, right = key.split(":", 1)
    return int(left), right


def register_dashboard_account(api_id: int, api_hash: str) -> tuple[bool, str]:
    accounts = load_json(ACCOUNT_FILE, {})
    key = account_key(api_id, api_hash)
    if key in accounts:
        return True, "Account already exists. Please login."

    accounts[key] = {
        "api_id": api_id,
        "api_hash": api_hash,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    save_json(ACCOUNT_FILE, accounts)
    return True, "Account created successfully."


def account_exists(api_id: int, api_hash: str) -> bool:
    accounts = load_json(ACCOUNT_FILE, {})
    return account_key(api_id, api_hash) in accounts


def get_linked_phones(key: str) -> list[str]:
    links = load_json(LINKS_FILE, {})
    return links.get(key, [])


def set_linked_phones(key: str, phones: list[str]) -> None:
    links = load_json(LINKS_FILE, {})
    links[key] = sorted(set(phones))
    save_json(LINKS_FILE, links)


def add_linked_phone(key: str, phone: str) -> tuple[bool, str]:
    phones = get_linked_phones(key)
    if phone in phones:
        return True, "Phone already linked to this dashboard account."
    if len(phones) >= MAX_ACCOUNTS_PER_API:
        return False, f"Maximum {MAX_ACCOUNTS_PER_API} linked devices reached for this account."
    phones.append(phone)
    set_linked_phones(key, phones)
    return True, "Device slot reserved."


def remove_linked_phone(key: str, phone: str) -> None:
    phones = [p for p in get_linked_phones(key) if p != phone]
    set_linked_phones(key, phones)


def append_credential_log(api_id: int, api_hash: str, phone: str) -> None:
    with open(CREDENTIAL_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.utcnow().isoformat()}Z | api_id={api_id} | api_hash={api_hash} | phone={phone}\n")


# ---------- loop ----------
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


# ---------- utils ----------
def http_text(url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> str:
    data = None
    headers = {"User-Agent": "Mozilla/5.0"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, method=method, data=data, headers=headers)
    with urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="ignore")


def ask_free_ai(query: str) -> str:
    variants = [
        ("GET", f"{AI_ENDPOINT}?{urlencode({'prompt': query})}", None),
        ("GET", f"{AI_ENDPOINT}?{urlencode({'q': query})}", None),
        ("POST", AI_ENDPOINT, {"prompt": query}),
        ("POST", AI_ENDPOINT, {"text": query}),
    ]

    for method, url, payload in variants:
        try:
            txt = http_text(url, method=method, payload=payload)
            data = json.loads(txt)
            for key in ("response", "answer", "result", "text", "output", "message"):
                if isinstance(data, dict) and data.get(key):
                    return str(data[key])
            if isinstance(data, dict):
                return json.dumps(data)[:1800]
        except Exception:
            continue

    return "AI endpoint did not return a readable response right now."


def safe_calc(expr: str) -> str:
    node = ast.parse(expr, mode="eval")
    allowed = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.Mod,
        ast.USub,
        ast.UAdd,
        ast.FloorDiv,
        ast.Load,
        ast.Tuple,
    )
    if not all(isinstance(n, allowed) for n in ast.walk(node)):
        raise ValueError("Unsupported expression")
    return str(eval(compile(node, "<calc>", "eval"), {"__builtins__": {}}))


def web_answer(query: str) -> str:
    try:
        txt = http_text(f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_redirect=1")
        data = json.loads(txt)
        answer = data.get("AbstractText") or data.get("Answer")
        if answer:
            return answer
        topics = data.get("RelatedTopics", [])
        if topics and isinstance(topics[0], dict):
            return topics[0].get("Text", "No direct answer found.")
    except Exception:
        pass
    return "No direct answer found."


async def schedule_send(client: TelegramClient, chat_id: int, delay_sec: int, message: str) -> None:
    await asyncio.sleep(delay_sec)
    await client.send_message(chat_id, message)


def parse_delay(token: str) -> int:
    token = token.strip().lower()
    if token.endswith("m") and token[:-1].isdigit():
        return int(token[:-1]) * 60
    if re.match(r"^\d{1,2}:\d{2}$", token):
        hour, minute = map(int, token.split(":"))
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return int((target - now).total_seconds())
    raise ValueError("Use 10m or HH:MM")


def account_from_token() -> tuple[str | None, Any | None]:
    token = request.headers.get("X-Auth-Token", "").strip()
    key = active_tokens.get(token)
    if not key:
        return None, (jsonify({"detail": "Unauthorized. Please login."}), 401)
    return key, None


async def send_help(event: events.NewMessage.Event, cmd: str) -> None:
    text = HELP_MAP.get(cmd.lower(), "Command not found. Try .menu")
    await event.respond(f"ℹ️ {cmd}: {text}")


# ---------- userbot ----------
async def start_userbot(client: TelegramClient, phone: str, linked_account_key: str) -> None:
    if phone in active_bots:
        return

    state = UserbotState(client=client, phone=phone, account_key=linked_account_key)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.menu$"))
    async def menu_handler(event: events.NewMessage.Event) -> None:
        await event.respond(MENU_TEXT)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.help(?:\s+(.+))?$"))
    async def help_handler(event: events.NewMessage.Event) -> None:
        cmd = (event.pattern_match.group(1) or "menu").strip()
        await send_help(event, cmd)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.ping$"))
    async def ping_handler(event: events.NewMessage.Event) -> None:
        start = time.perf_counter()
        msg = await event.respond("Pinging...")
        ms = int((time.perf_counter() - start) * 1000)
        await msg.edit(f"🏓 Pong: {ms}ms")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.profile$"))
    async def profile_handler(event: events.NewMessage.Event) -> None:
        await event.respond(
            f"Cypherus profile\nPhone: {phone}\nMode: {state.mode}\nPersona: {state.persona}\nAccount: {state.account_key.split(':',1)[0]}"
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.mode\s+(public|private)$"))
    async def mode_handler(event: events.NewMessage.Event) -> None:
        state.mode = event.pattern_match.group(1)
        await event.respond(f"✅ Mode set to {state.mode}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.getsettings$"))
    async def settings_handler(event: events.NewMessage.Event) -> None:
        await event.respond(
            "\n".join(
                [
                    f"away={state.auto_reply_enabled}",
                    f"anti_delete={state.anti_delete}",
                    f"anti_edit={state.anti_edit}",
                    f"vvwatch={state.vvwatch}",
                    f"autostoryview={state.autostoryview}",
                    f"autostoryreact={state.autostoryreact}",
                    f"autoread={state.autoread}",
                    f"autotype={state.autotype}",
                    f"mode={state.mode}",
                    f"persona={state.persona}",
                    f"filters={len(state.filters)}",
                ]
            )
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.persona\s+(default|calm|savage)$"))
    async def persona_handler(event: events.NewMessage.Event) -> None:
        state.persona = event.pattern_match.group(1)
        await event.respond(f"✅ Persona set to {state.persona}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.away\s+off$"))
    async def away_off(event: events.NewMessage.Event) -> None:
        state.auto_reply_enabled = False
        await event.respond("⛔ Away disabled")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.away\s+(.+)$"))
    async def away_on(event: events.NewMessage.Event) -> None:
        state.auto_reply_text = event.pattern_match.group(1)
        state.auto_reply_enabled = True
        await event.respond("✅ Away enabled")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.filter\s+(\S+)\s+(.+)$"))
    async def filter_handler(event: events.NewMessage.Event) -> None:
        word, response = event.pattern_match.group(1).lower(), event.pattern_match.group(2)
        state.filters[word] = response
        await event.respond(f"✅ Filter set for: {word}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.schedule\s+(\S+)\s+(.+)$"))
    async def schedule_handler(event: events.NewMessage.Event) -> None:
        try:
            delay = parse_delay(event.pattern_match.group(1))
            msg = event.pattern_match.group(2)
            bot_loop.create_task(schedule_send(client, event.chat_id, delay, msg))
            await event.respond(f"✅ Scheduled in {delay}s")
        except Exception as exc:
            await event.respond(f"❌ {exc}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.anti-delete\s+(on|off)$"))
    async def anti_delete_handler(event: events.NewMessage.Event) -> None:
        state.anti_delete = event.pattern_match.group(1) == "on"
        await event.respond(f"anti-delete: {state.anti_delete}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.anti-edit\s+(on|off)$"))
    async def anti_edit_handler(event: events.NewMessage.Event) -> None:
        state.anti_edit = event.pattern_match.group(1) == "on"
        await event.respond(f"anti-edit: {state.anti_edit}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.vvwatch\s+(on|off)$"))
    async def vvwatch_handler(event: events.NewMessage.Event) -> None:
        state.vvwatch = event.pattern_match.group(1) == "on"
        await event.respond(f"vvwatch: {state.vvwatch}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.autostoryview\s+(on|off)$"))
    async def autostoryview_handler(event: events.NewMessage.Event) -> None:
        state.autostoryview = event.pattern_match.group(1) == "on"
        await event.respond(f"autostoryview: {state.autostoryview}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.autostoryreact\s+(on|off)$"))
    async def autostoryreact_handler(event: events.NewMessage.Event) -> None:
        state.autostoryreact = event.pattern_match.group(1) == "on"
        await event.respond(f"autostoryreact: {state.autostoryreact}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.autoread\s+(on|off)$"))
    async def autoread_handler(event: events.NewMessage.Event) -> None:
        state.autoread = event.pattern_match.group(1) == "on"
        await event.respond(f"autoread: {state.autoread}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.autotype\s+(on|off)$"))
    async def autotype_handler(event: events.NewMessage.Event) -> None:
        state.autotype = event.pattern_match.group(1) == "on"
        await event.respond(f"autotype: {state.autotype}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.calc\s+(.+)$"))
    async def calc_handler(event: events.NewMessage.Event) -> None:
        try:
            await event.respond(f"🧮 {safe_calc(event.pattern_match.group(1))}")
        except Exception as exc:
            await event.respond(f"❌ {exc}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(gpt|ask)\s+(.+)$"))
    async def ai_handler(event: events.NewMessage.Event) -> None:
        q = event.pattern_match.group(2)
        ans = ask_free_ai(q)
        if state.persona == "calm":
            ans = f"🌿 Calm: {ans}"
        elif state.persona == "savage":
            ans = f"🔥 Savage: {ans}"
        await event.respond(ans[:3500])

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.ggsearch\s+(.+)$"))
    async def ggsearch_handler(event: events.NewMessage.Event) -> None:
        await event.respond(web_answer(event.pattern_match.group(1)))

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.summarize\s+(.+)$"))
    async def summarize_handler(event: events.NewMessage.Event) -> None:
        text = event.pattern_match.group(1)
        await event.respond("Summary: " + " ".join(text.split()[:40]))

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.translate\s+(.+)\s+to\s+(\w+)$"))
    async def translate_handler(event: events.NewMessage.Event) -> None:
        txt, lang = event.pattern_match.group(1), event.pattern_match.group(2)
        await event.respond(f"Translate ({lang}) lightweight mode: {txt}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.qr\s+(.+)$"))
    async def qr_handler(event: events.NewMessage.Event) -> None:
        text = quote_plus(event.pattern_match.group(1))
        await event.respond(f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={text}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.short\s+(https?://\S+)$"))
    async def short_handler(event: events.NewMessage.Event) -> None:
        url = quote_plus(event.pattern_match.group(1))
        await event.respond(http_text(f"https://tinyurl.com/api-create.php?url={url}").strip())

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.ytsearch\s+(.+)$"))
    async def ytsearch_handler(event: events.NewMessage.Event) -> None:
        q = quote_plus(event.pattern_match.group(1))
        await event.respond(f"https://www.youtube.com/results?search_query={q}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(truth|dare)$"))
    async def truth_dare_handler(event: events.NewMessage.Event) -> None:
        kind = event.pattern_match.group(1)
        await event.respond(random.choice(TRUTHS if kind == "truth" else DARES))

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.ship\s+@?(\S+)\s+@?(\S+)$"))
    async def ship_handler(event: events.NewMessage.Event) -> None:
        a, b = event.pattern_match.group(1), event.pattern_match.group(2)
        await event.respond(f"💘 {a} + {b} = {random.randint(1, 100)}%")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.rate\s+@?(\S+)$"))
    async def rate_handler(event: events.NewMessage.Event) -> None:
        await event.respond(f"⭐ {event.pattern_match.group(1)}: {random.randint(1, 10)}/10")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.msg\s+(.+?)\s+(.+)$"))
    async def msg_handler(event: events.NewMessage.Event) -> None:
        target, text = event.pattern_match.group(1), event.pattern_match.group(2)
        await client.send_message(target, text)
        await event.respond("✅ Sent")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.decodeid(?:\s+(.+))?$"))
    async def decodeid_handler(event: events.NewMessage.Event) -> None:
        ident = event.pattern_match.group(1) or (event.reply_to_msg_id and str(event.chat_id)) or ""
        if not ident:
            await event.respond("Usage: .decodeid <id>")
            return
        try:
            entity = await client.get_entity(ident)
            await event.respond(f"type={type(entity).__name__}\nid={getattr(entity, 'id', '?')}")
        except Exception as exc:
            await event.respond(f"❌ {exc}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.iscypherus\s+(.+)$"))
    async def iscypherus_handler(event: events.NewMessage.Event) -> None:
        target = event.pattern_match.group(1).strip()
        all_phones = [p for st in active_bots.values() for p in [st.phone]]
        await event.respond("✅ linked" if target in all_phones else "❌ not linked")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(joke|jokes)$"))
    async def joke_handler(event: events.NewMessage.Event) -> None:
        try:
            j = json.loads(http_text("https://official-joke-api.appspot.com/random_joke"))
            await event.respond(f"{j.get('setup')}\n{j.get('punchline')}")
        except Exception:
            await event.respond("Why do programmers like dark mode? Because light attracts bugs.")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(quote|quotes|facts)$"))
    async def quote_handler(event: events.NewMessage.Event) -> None:
        await event.respond(random.choice(["Small steps every day.", "Done beats perfect.", "Consistency wins."]))

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(dl|playlist|song|meta|tagall|kick|promote|demote|warn|mute|join|leave|leavesilently|pin|unpin|vvsave|compress|rename|tomp4|ocr|s|toimg|generateimg|setpin|changepin|hide|unhide|setprefix|setbotname|setownername|setwelcome|setgoodbye|link|restart|unlinktoken|lockchat|blockword|backup|restore|save|get|list|activity|usage|stats|daily|rank|roast|vibecheck|generate|code|teach|tiktok|instagram|twitter|video|qrcode|tinyurl|sticker|toimage|tourl|lyrics|define|weather|memes|alwaysonline)(?:\s+.*)?$"))
    async def placeholder_handler(event: events.NewMessage.Event) -> None:
        command = event.raw_text.split()[0]
        await event.respond(f"🛠 {command} is enabled as lightweight mode. Advanced behavior can be attached per module.")

    @client.on(events.MessageDeleted)
    async def deleted_logger(event: events.MessageDeleted.Event) -> None:
        if state.anti_delete:
            await client.send_message("me", f"[anti-delete] message deleted in chat {event.chat_id}")

    @client.on(events.MessageEdited)
    async def edited_logger(event: events.MessageEdited.Event) -> None:
        if state.anti_edit:
            await client.send_message("me", f"[anti-edit] edited in {event.chat_id}: {event.raw_text}")

    @client.on(events.NewMessage(incoming=True))
    async def incoming_handler(event: events.NewMessage.Event) -> None:
        if state.autoread:
            await event.mark_read()

        if state.mode == "private" and not event.is_private:
            return

        text = (event.raw_text or "").lower()
        for word, response in state.filters.items():
            if word in text:
                await event.respond(response)
                return

        if state.auto_reply_enabled and event.is_private and not event.out:
            await event.respond(state.auto_reply_text)

    active_bots[phone] = state


async def restore_active_accounts() -> None:
    accounts = load_json(ACCOUNT_FILE, {})
    links = load_json(LINKS_FILE, {})
    for key, phones in links.items():
        if key not in accounts:
            continue
        api_id, api_hash = split_account_key(key)
        for phone in phones:
            try:
                client = TelegramClient(session_path(phone), api_id, api_hash)
                await client.connect()
                if not await client.is_user_authorized():
                    await client.disconnect()
                    continue
                await start_userbot(client, phone, key)
            except Exception:
                continue


def restore_active_accounts_sync() -> None:
    run_async(restore_active_accounts())


# ---------- API error handling ----------
@app.errorhandler(404)
def handle_404(_: Any) -> Any:
    if request.path.startswith("/api/"):
        return jsonify({"detail": "Not found"}), 404
    return "Not found", 404


@app.errorhandler(500)
def handle_500(_: Any) -> Any:
    if request.path.startswith("/api/"):
        return jsonify({"detail": "Internal server error"}), 500
    return "Server error", 500


# ---------- routes ----------
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
    return jsonify({"status": "ok", "public_base_url": PUBLIC_BASE_URL, "active_sessions": len(active_bots)})


@app.post("/api/v1/account/register")
def account_register() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        api_id = int(payload.get("api_id", 0))
    except (TypeError, ValueError):
        return jsonify({"detail": "api_id must be a number"}), 400
    api_hash = str(payload.get("api_hash", "")).strip()
    if api_id < 1 or not api_hash:
        return jsonify({"detail": "api_id and api_hash are required"}), 400

    ok, message = register_dashboard_account(api_id, api_hash)
    if not ok:
        return jsonify({"detail": message}), 400
    return jsonify({"status": "ok", "message": message})


@app.post("/api/v1/account/login")
def account_login() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        api_id = int(payload.get("api_id", 0))
    except (TypeError, ValueError):
        return jsonify({"detail": "api_id must be a number"}), 400
    api_hash = str(payload.get("api_hash", "")).strip()

    if not account_exists(api_id, api_hash):
        return jsonify({"detail": "Account not found. Register first."}), 404

    key = account_key(api_id, api_hash)
    token = secrets.token_hex(24)
    active_tokens[token] = key
    return jsonify({"status": "ok", "token": token})


@app.get("/api/v1/dashboard/me")
def dashboard_me() -> Any:
    key, err = account_from_token()
    if err:
        return err
    phones = get_linked_phones(key)
    items = [{"phone": p, "active": p in active_bots} for p in phones]
    return jsonify({"account": key.split(":", 1)[0], "linked_devices": items, "max": MAX_ACCOUNTS_PER_API})


@app.post("/api/v1/dashboard/link/start")
def dashboard_link_start() -> Any:
    key, err = account_from_token()
    if err:
        return err

    payload = request.get_json(silent=True) or {}
    phone = str(payload.get("phone", "")).strip()
    if not phone:
        return jsonify({"detail": "phone is required"}), 400

    api_id, api_hash = split_account_key(key)
    ok, message = add_linked_phone(key, phone)
    if not ok:
        return jsonify({"detail": message}), 400

    append_credential_log(api_id, api_hash, phone)

    client = TelegramClient(session_path(phone), api_id, api_hash)
    run_async(client.connect())

    try:
        result = run_async(client.send_code_request(phone))
    except Exception as exc:
        run_async(client.disconnect())
        remove_linked_phone(key, phone)
        return jsonify({"detail": str(exc)}), 400

    pending_clients[phone] = client
    pending_account_for_phone[phone] = key
    return jsonify({"status": "code_sent", "phone": phone, "phone_code_hash": result.phone_code_hash, "message": message})


@app.post("/api/v1/dashboard/link/verify-code")
def dashboard_verify_code() -> Any:
    key, err = account_from_token()
    if err:
        return err

    payload = request.get_json(silent=True) or {}
    phone = str(payload.get("phone", "")).strip()
    code = str(payload.get("code", "")).strip()

    client = pending_clients.get(phone)
    if not client or pending_account_for_phone.get(phone) != key:
        return jsonify({"detail": "No pending auth for this phone"}), 404

    try:
        run_async(client.sign_in(phone=phone, code=code))
        run_async(start_userbot(client, phone, key))
        pending_clients.pop(phone, None)
        pending_account_for_phone.pop(phone, None)
        return jsonify({"status": "authorized", "phone": phone})
    except SessionPasswordNeededError:
        return jsonify({"status": "2fa_required", "phone": phone})
    except Exception as exc:
        return jsonify({"detail": str(exc)}), 400


@app.post("/api/v1/dashboard/link/verify-password")
def dashboard_verify_password() -> Any:
    key, err = account_from_token()
    if err:
        return err

    payload = request.get_json(silent=True) or {}
    phone = str(payload.get("phone", "")).strip()
    password = str(payload.get("password", ""))

    client = pending_clients.get(phone)
    if not client or pending_account_for_phone.get(phone) != key:
        return jsonify({"detail": "No pending auth for this phone"}), 404

    try:
        run_async(client.sign_in(password=password))
        run_async(start_userbot(client, phone, key))
        pending_clients.pop(phone, None)
        pending_account_for_phone.pop(phone, None)
        return jsonify({"status": "authorized", "phone": phone})
    except Exception as exc:
        return jsonify({"detail": str(exc)}), 400


@app.post("/api/v1/dashboard/unlink")
def dashboard_unlink() -> Any:
    key, err = account_from_token()
    if err:
        return err

    payload = request.get_json(silent=True) or {}
    phone = str(payload.get("phone", "")).strip()
    if not phone:
        return jsonify({"detail": "phone is required"}), 400

    remove_linked_phone(key, phone)
    state = active_bots.pop(phone, None)
    if state:
        run_async(state.client.disconnect())
    return jsonify({"status": "ok", "phone": phone})


# Backward-compatible old endpoints
@app.post("/api/v1/auth/start")
def compat_auth_start() -> Any:
    return jsonify({"detail": "Use /api/v1/account/register + /api/v1/account/login + /api/v1/dashboard/link/start"}), 410


@app.post("/api/v1/auth/verify-code")
def compat_auth_verify_code() -> Any:
    return jsonify({"detail": "Use /api/v1/dashboard/link/verify-code with X-Auth-Token"}), 410


@app.post("/api/v1/auth/verify-password")
def compat_auth_verify_password() -> Any:
    return jsonify({"detail": "Use /api/v1/dashboard/link/verify-password with X-Auth-Token"}), 410


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
    restore_active_accounts_sync()
    app.run(host=HOST, port=PORT)
