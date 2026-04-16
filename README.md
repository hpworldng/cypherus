# Cypherus Userbot Foundation

A Python foundation for a Telegram **userbot** with:

- FastAPI backend
- Web frontend for account linking (API ID/hash, phone, login code, 2FA)
- Telethon session handling
- Starter userbot commands (`.ping`, `.autoreply on`, `.autoreply off`)

## Run locally (Termux / Linux)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 3000
```

Open: `http://localhost:3000`

## Environment variables

- `PORT` (default `3000`)
- `HOST` (default `0.0.0.0`)
- `PUBLIC_BASE_URL` (default `http://localhost:${PORT}`)
- `STATIC_API_KEY` (default `cypherus-v1`)
- `SESSION_DIR` (default `sessions`)

Static API endpoint format:

- `POST /api/v1/<STATIC_API_KEY>/auth/start`
- `POST /api/v1/<STATIC_API_KEY>/auth/verify-code`
- `POST /api/v1/<STATIC_API_KEY>/auth/verify-password`

## Railway deploy

Set these variables in Railway:

- `PORT` (Railway usually injects this automatically)
- `PUBLIC_BASE_URL` (your Railway domain)
- `STATIC_API_KEY` (your fixed key)

Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Notes

Use this only on accounts you own or have explicit authorization to automate.
