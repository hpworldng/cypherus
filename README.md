# Cypherus Userbot Foundation (Lightweight)

This is now a **lightweight** build.

## What changed
- Removed FastAPI + Pydantic + Uvicorn stack.
- Switched to **Flask + Telethon** only.
- No static API key.
- Fewer dependencies, easier install on Termux.

---

## Super simple install (Termux)

Run these exactly:

```bash
pkg update -y && pkg upgrade -y
pkg install -y python git

git clone https://github.com/hpworldng/cypherus.git
cd cypherus

python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip setuptools wheel
pip install -e .
```

Start app:

```bash
python app/main.py
```

Open in browser:
- `http://127.0.0.1:3000`

---

## API endpoints (public)

- `POST /api/v1/auth/start`
- `POST /api/v1/auth/verify-code`
- `POST /api/v1/auth/verify-password`
- `GET /health`

---

## Railway deploy

### Env vars
- `PORT` (Railway auto-sets this)
- `PUBLIC_BASE_URL` (optional)
- `SESSION_DIR` (optional, default `sessions`)

### Start command

```bash
python app/main.py
```

---

## Quick usage

1. Open the web page.
2. Enter Telegram `API ID`, `API Hash`, and phone number.
3. Enter login code.
4. If prompted, enter 2FA password.
5. In Telegram, test:
   - `.ping`
   - `.autoreply on I am busy now`
   - `.autoreply off`

---

## Note
Use this only on accounts you own or have permission to automate.
