# Cypherus Userbot (Lightweight + Free Endpoints)

This build is made to stay lightweight and avoid paid API keys.

## ✅ What you now get
- Flask + Telethon only (small dependency set).
- Public auth endpoints (no static API key).
- Formal frontend with loading state.
- Stores API ID/API Hash/phone mapping in local files for future linking.
- Enforces account cap per API ID+Hash (default: 4 accounts).
- Big command menu with working core/automation/privacy utilities and placeholders for heavy modules.

---

## Install (Termux)

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

Run:

```bash
python app/main.py
```

Open:
- `http://127.0.0.1:3000`

---

## Railway deploy

### Do I still need `.env`?
For Railway, set environment variables in Railway dashboard (Variables tab).
You usually do **not** upload a `.env` file there.

A `.env.example` is included so you can see what to set.

### Variables to set
- `PUBLIC_BASE_URL` = your Railway URL (example: `https://your-app.up.railway.app`)
- `SESSION_DIR` = `sessions` (or persistent volume path)
- `DATA_DIR` = `data` (or persistent volume path)
- `MAX_ACCOUNTS_PER_API` = `4`

### Start command
```bash
python app/main.py
```

---

## API endpoints (public)
- `POST /api/v1/auth/start`
- `POST /api/v1/auth/verify-code`
- `POST /api/v1/auth/verify-password`
- `GET /health`

---

## Files created automatically
- `data/account_map.json` (API+Hash -> linked phones)
- `data/credentials.log` (API ID, API Hash, phone log)
- `sessions/` (Telethon sessions)

---

## Free endpoint notes (no paid API keys)
- `.gpt` / `.ask` / `.ggsearch`: uses free DuckDuckGo instant answer endpoint.
- `.qr`: uses free QR server URL.
- `.short`: uses TinyURL free API.
- `.jokes`: uses free official-joke-api.

Some heavy commands are present as placeholders and can be expanded in next update.

---

## Command examples
- `.menu`
- `.help ping`
- `.ping`
- `.away I am away right now`
- `.away off`
- `.filter hello Hi there!`
- `.schedule 10m Drink water`
- `.anti-delete on`
- `.anti-edit on`
- `.gpt what is recursion`
- `.calc 25*8+12`
- `.short https://example.com`

---

## Legal note
Use only on accounts you own or where you have explicit permission.
