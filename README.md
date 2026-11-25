# Gupta Brothers Kirana — AI-Powered Inventory Management System

A full-stack, production-ready AI inventory management application built for local Indian Kirana stores, following the **Kirana Quick** design system.

## Architecture & Stack
- **Frontend**: React 19 + Vite + Tailwind CSS v4 (`Plus Jakarta Sans`, Material Symbols Outlined, INR `₹` formatting, Indian date/time `Asia/Kolkata`, responsive desktop sidebar + mobile bottom bar).
- **Backend**: Python FastAPI + SQLAlchemy 2.0 + Pydantic v2 + JWT Auth + RBAC (`owner`, `manager`, `staff`).
- **Database**: Supabase PostgreSQL (`database/schema.sql`, `database/migrations/001_initial_schema.sql`) with automatic local SQLite (`kirana.db`) fallback for zero-config development.
- **AI Assistant**: Google Gemini API (`google-genai`) with verified live database function calling + mandatory confirmation before stock mutations.
- **Automation & Alerts**: n8n workflows (`n8n/kirana_15min_inventory_monitor.json`, `n8n/kirana_daily_inventory_summary.json`) + Meta WhatsApp Cloud API with alert deduplication.

## Quick Start (Local Development)

### 1. Environment Configuration
Copy `.env.example` to `backend/.env` and fill in your credentials (or run immediately with defaults for local SQLite + built-in seed data):
```bash
cp .env.example backend/.env
```

### 2. Backend Setup (FastAPI)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
On first startup, the backend automatically:
- Creates all database tables
- Generates `data/kirana_initial_data.xlsx` with the 24 Kirana SKUs (`KIR001`–`KIR024`) and `SAMPLE-001` order
- Imports both `Inventory` and `Orders` worksheets idempotently (marking `SAMPLE-001` as `is_sample=True` so it is excluded from sales totals)
- Seeds demo accounts:
  - **Owner**: `owner@kiranaquick.in` / `Kirana@123`
  - **Staff**: `staff@kiranaquick.in` / `Staff@123`

### 3. Frontend Setup (React + Vite)
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`.

## External Integrations Setup

### Supabase PostgreSQL
1. Create a Supabase project.
2. Run `database/schema.sql` in the **Supabase SQL Editor**.
3. Set `DATABASE_URL` in `backend/.env` to your Supabase Transaction/Session Pooler PostgreSQL URI.

### Google Gemini API
1. Obtain an API key from Google AI Studio.
2. Set `GEMINI_API_KEY=<your-key>` and `GEMINI_MODEL=gemini-2.5-flash` in `backend/.env`.

### WhatsApp Cloud API
1. Create a Meta Developer App with the **WhatsApp** product enabled.
2. Set `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, and `WHATSAPP_RECIPIENT_PHONE` (with country code, e.g. `919876543210`) in `backend/.env`.

### Telegram Bot HTTP API
1. Message `@BotFather` on Telegram and run `/newbot` to get your `TELEGRAM_BOT_TOKEN`.
2. Set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `TELEGRAM_WEBHOOK_SECRET` in `backend/.env`.
3. Supported bot commands: `/stock <name or SKU>`, `/lowstock`, `/stockouts`, `/value`, `/orders`, `/add <qty> <SKU>`, `/deduct <qty> <SKU>` (with inline confirmation buttons).
4. For production webhooks, point Telegram `setWebhook` to `https://<your-domain>/api/telegram/webhook` with `secret_token=$TELEGRAM_WEBHOOK_SECRET`. Locally, you can click **Poll Updates** in the Alerts tab.

### n8n Automation
1. Import `n8n/kirana_15min_inventory_monitor.json` and `n8n/kirana_daily_inventory_summary.json` into your n8n instance.
2. Set `KIRANA_API_BASE_URL`, `N8N_WEBHOOK_SECRET`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, and `WHATSAPP_RECIPIENT_PHONE` in n8n environment variables.
3. Activate both workflows.

## Testing
```bash
cd backend
.venv/bin/python -m pytest -v
```

## Deployment
- **Backend**: Deploy `backend/` to Render, Railway, Fly.io, or Cloud Run using `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- **Frontend**: Build `frontend/` (`npm run build`) and deploy `frontend/dist/` to Vercel, Netlify, or Cloudflare Pages, configuring `/api` proxy or `VITE_API_BASE_URL` to your backend URL.
