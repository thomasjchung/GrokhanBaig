# GrokhanBaig

Mobile events feed. Mock data lives in `src/data/mockApi.ts`. The backend contract is `docs/frontend-api.md`.

```bash
npm install
npm run dev
```

The API (Google sign-in, the one Gmail invite, and the Instagram account `@farhanandtommyclub`) runs beside it:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Put `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`. The Google client’s redirect URI is `http://127.0.0.1:5174/api/google/callback`. Open http://127.0.0.1:5174/ and choose Continue with Google.