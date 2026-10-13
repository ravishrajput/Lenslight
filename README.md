# Lenslight

Lenslight is an AI analytics app with a React frontend and FastAPI backend. Chat can analyze the bundled local event-log CSV together with BigQuery warehouse results and produce a concise investigation report.

## What is already implemented
- FastAPI backend with auth, chat history, streaming responses, PDF export, and scheduled digest emails
- Mongo-based persistence for users, chats, messages, and sessions
- Bundled six-month local event-log dataset with checkout, address, latency, and failure records
- Optional BigQuery queries for warehouse metrics
- LLM report generation using Gemini, with Anthropic as an optional fallback
- React frontend with login, chat flow, connections page, and digest settings

## Required services
Before deployment, you need:
- MongoDB database (Mongo Atlas or local MongoDB)
- Gemini API key (or an Anthropic API key as an alternative)
- Email API key if weekly digest delivery is enabled
- A frontend origin and backend URL for CORS and deep links

## Local setup

### 1) Create backend environment file
Copy the sample file and fill in your secrets:

cp backend/.env.example backend/.env

Then set real values for:
- MONGO_URL
- DB_NAME
- JWT_SECRET
- GEMINI_API_KEY
- GEMINI_MODEL
- WEBHOOK_CRON_SECRET
- FRONTEND_URL
- DEMO_EMAIL / DEMO_PASSWORD
- EMAIL_API_KEY (optional)

### 2) Create frontend environment file
cp frontend/.env.example frontend/.env

Set:
- REACT_APP_BACKEND_URL=http://localhost:8000

### 3) Install backend dependencies
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

### 4) Run backend
cd backend
source .venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8000 --reload

### 5) Run frontend
cd frontend
npm install
npm start

The UI should open on http://localhost:3000 and the API will be on http://localhost:8000.

## Render deployment

Deploy the FastAPI backend as a Docker web service and the React frontend as a static site. Render connects to GitHub and deploys on pushes, so no cloud CLI or custom GitHub Actions workflow is needed. MongoDB remains external; use MongoDB Atlas.

Chat defaults to both the bundled local dataset and BigQuery. The CSV is at `backend/data/splunk_events.csv`; to replace it, update that file and redeploy the backend. `backend/scripts/generate_splunk_sample.py` regenerates the six-month sample in both that location and `samples/splunk_events.csv`. Weekly digests use the local CSV.

### 1) Deploy the backend

In Render, create a **New Web Service** and connect this repository. Configure:

- Runtime: Docker
- Dockerfile path: `backend/Dockerfile`
- Docker build context: `backend`
- Health check path: `/api/`
- Branch: `main`

Add these environment variables in the service settings:

- `MONGO_URL`: MongoDB Atlas connection string
- `DB_NAME`: `lenslight`
- `JWT_SECRET`: long random signing secret
- `GEMINI_API_KEY`: Google AI Studio API key
- `GEMINI_MODEL`: `gemini-2.0-flash`
- `FRONTEND_URL`: leave unset until the frontend is deployed
- `GCP_PROJECT_ID` and `GOOGLE_CLOUD_PROJECT`: Google Cloud project ID
- `BQ_DATASET`: BigQuery dataset name
- `BQ_TABLE`: BigQuery orders table name
- `GOOGLE_APPLICATION_CREDENTIALS`: `/etc/secrets/gcp-service-account.json`

In the backend service's **Environment → Secret Files**, add `gcp-service-account.json` containing a Google service-account key JSON. Do not commit this file or put it in the frontend. Enable the BigQuery API and grant the service account **BigQuery Job User** on the project and **BigQuery Data Viewer** on the dataset. BigQuery is optional; users can turn off its source in chat to analyze the local CSV only.

Optional backend variables: `WEBHOOK_CRON_SECRET`, `DEMO_EMAIL`, `DEMO_PASSWORD`, `EMAIL_API_KEY`, `EMAIL_FROM_NAME`, and `EMAIL_REPLY_TO`.

Deploy the service and copy its public URL, for example `https://lenslight-api.onrender.com`.

### 2) Deploy the frontend

Create a **New Static Site** from the same repository. Configure:

- Branch: `main`
- Root directory: `frontend`
- Build command: `npm ci && npm run build`
- Publish directory: `build`

Set the build environment variable `REACT_APP_BACKEND_URL` to the backend URL from step 1, with no trailing slash. Add a rewrite rule from `/*` to `/index.html` so client-side routes work. Deploy and copy the static site URL.

### 3) Connect the app URLs

In the backend service, set `FRONTEND_URL` to the exact static site origin, such as `https://lenslight-web.onrender.com`, then save and redeploy. This origin must match exactly for CORS and login cookies. The frontend build embeds the backend URL, so rebuild the static site if that URL changes.

In MongoDB Atlas, allow connections from the backend service's outbound IP addresses. For a temporary connectivity test, a broad Atlas IP allowlist can help isolate the cause, but restrict it again before production and use a dedicated database user with a strong password.

After setup, Render automatically redeploys each service when its configured branch changes. For production use, choose an always-on backend plan; low-cost/free plans can sleep and add cold-start delays.

## Production notes

- Keep `.env` files and credentials out of version control; use GitHub secrets for deployment values.
- Chat can combine local CSV findings with BigQuery results; if BigQuery is unavailable, the report should disclose that and continue with local findings.
- Keep each service's environment variables configured in Render; the frontend API URL is a build-time value.
