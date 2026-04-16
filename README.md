# Cypherus Userbot Dashboard (Lightweight)

This version now uses **account-first login flow**:
1) Create dashboard account with API ID + API Hash.
2) Login with same API ID + API Hash.
3) Link up to 4 Telegram phones (devices) from dashboard.
4) Manage/unlink linked devices from dashboard.

It also restores previously linked active accounts on server restart.

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

Open `http://127.0.0.1:3000`.

---

## Dashboard Flow

- **Create account:** API ID + API Hash
- **Login:** API ID + API Hash
- **Link device:** phone -> code -> (optional) 2FA
- **Manage devices:** see linked devices + unlink

---

## API (new)

### Account
- `POST /api/v1/account/register`
- `POST /api/v1/account/login`

### Dashboard (requires `X-Auth-Token`)
- `GET /api/v1/dashboard/me`
- `POST /api/v1/dashboard/link/start`
- `POST /api/v1/dashboard/link/verify-code`
- `POST /api/v1/dashboard/link/verify-password`
- `POST /api/v1/dashboard/unlink`

### Health
- `GET /health`

Old `/api/v1/auth/*` endpoints are now compatibility responses (410).

---

## Persistence / Restart behavior

Saved data:
- `data/dashboard_accounts.json`
- `data/linked_devices.json`
- `data/credentials.log`
- `sessions/*`

On restart, app auto-loads linked devices and reconnects authorized sessions.

---

## AI Endpoint (free)
Used for `.gpt` and `.ask`:

`https://devtoolbox-api.devtoolbox-api.workers.dev/ai/generate`

Set custom endpoint with env var:
- `AI_ENDPOINT=...`

---

## Environment variables
See `.env.example`.
For Railway: set these in Railway Variables tab.

- `PUBLIC_BASE_URL`
- `SESSION_DIR`
- `DATA_DIR`
- `MAX_ACCOUNTS_PER_API`
- `AI_ENDPOINT`

---

## Notes
- This is a lightweight base. Many heavy commands are wired and respond, and can be expanded module-by-module.
- Use only with accounts you own or have explicit permission to automate.
