# Cypherus Userbot Foundation

This project runs a Telegram **userbot** with:
- a backend server (Python + FastAPI)
- a simple web page for login/linking
- starter commands: `.ping`, `.autoreply on`, `.autoreply off`

---

## Very simple setup (Termux)

> If you are not technical, copy and run commands exactly one-by-one.

### 1) Install packages in Termux

```bash
pkg update -y && pkg upgrade -y
pkg install -y python git libcrypt rust
```

### 2) Clone project

```bash
git clone https://github.com/hpworldng/cypherus.git
cd cypherus
```

### 3) Create and activate virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 4) Upgrade pip tools

```bash
pip install --upgrade pip setuptools wheel
```

### 5) Install project dependencies

```bash
pip install -e .
```

### 6) Start server

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 3000
```

### 7) Open in browser

- On same phone: `http://127.0.0.1:3000`
- If exposing to internet, use your host URL instead.

---

## Important: no static API key

This version is **public endpoint style**.

Auth endpoints are:
- `POST /api/v1/auth/start`
- `POST /api/v1/auth/verify-code`
- `POST /api/v1/auth/verify-password`

No `STATIC_API_KEY` is required.

---

## Railway deploy (simple)

### Environment variables
- `PORT` (Railway usually sets this automatically)
- `PUBLIC_BASE_URL` (your Railway domain, optional)
- `SESSION_DIR` (optional, default `sessions`)

### Start command

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

## Troubleshooting

### Error: `No command uvicorn found`
Use:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 3000
```

### Error building dependencies on Termux
Install Rust first:

```bash
pkg install -y rust
```

Then run again:

```bash
pip install -e .
```

---

## Notes

Use this only on accounts you own or where you have explicit permission.
