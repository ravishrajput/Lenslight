# Lenslight

Lenslight is a dark-mode AI analytics app for investigating Splunk and BigQuery data through a chat interface. It connects a FastAPI backend with a React frontend and uses an LLM to turn operational + warehouse data into a concise investigation report.

## What is already implemented
- FastAPI backend with auth, chat history, streaming responses, PDF export, and scheduled digest emails
- Mongo-based persistence for users, chats, messages, and sessions
- Mock Splunk and BigQuery data sources to simulate real data analysis
- LLM report generation via the Emergent LLM integration
- React frontend with login, chat flow, connections page, and digest settings

## Required services
Before deployment, you need:
- MongoDB database (Mongo Atlas or local MongoDB)
- Emergent LLM API key
- Emergent email API key for weekly digest emails
- A frontend origin and backend URL for CORS and deep links

## Local setup

### 1) Create backend environment file
Copy the sample file and fill in your secrets:

cp backend/.env.example backend/.env

Then set real values for:
- MONGO_URL
- DB_NAME
- JWT_SECRET
- EMERGENT_LLM_KEY
- WEBHOOK_CRON_SECRET
- FRONTEND_URL
- DEMO_EMAIL / DEMO_PASSWORD
- EMERGENT_EMAIL_KEY

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

Chat analysis and weekly digests use the bundled local dataset at `backend/data/splunk_events.csv`; they do not require Splunk or BigQuery credentials. To replace the dataset, update that CSV and redeploy the backend. `backend/scripts/generate_splunk_sample.py` regenerates the six-month sample both there and in `samples/splunk_events.csv`.

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
- The default analysis source is the bundled static CSV; live cloud connectors are not used by chat or digests.
- Keep each service's environment variables configured in Render; the frontend API URL is a build-time value.

## Current status
The project is structurally complete and the main real blocker I found was a frontend dependency mismatch:
- `date-fns` was set to 4.1.0 while `react-day-picker` expects 2.x/3.x.
- That has been corrected in the project to a compatible version.

After you fill in your .env files and install the app dependencies, it is ready to run and deploy.
