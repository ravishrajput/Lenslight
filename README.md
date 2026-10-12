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

## Production deployment

### Option A: separate backend + frontend hosting
- Backend: Render, Railway, Fly.io, or a VPS
- Frontend: Vercel, Netlify, or CloudFront

Recommended env config:
- Backend:
  - MONGO_URL
  - DB_NAME
  - JWT_SECRET
  - EMERGENT_LLM_KEY
  - WEBHOOK_CRON_SECRET
  - FRONTEND_URL=https://your-frontend-domain
  - DEMO_EMAIL=demo@insightlens.app
  - DEMO_PASSWORD=strong-demo-password
  - EMERGENT_EMAIL_KEY
- Frontend:
  - REACT_APP_BACKEND_URL=https://your-backend-domain

### Option B: single host
Use a reverse proxy or Docker to serve the frontend and proxy API requests to the FastAPI server.

## Production notes
- Replace mock Splunk/BigQuery connectors in backend/mock_data.py with real APIs when you're ready to use live data.
- Keep .env files out of version control. Only commit .env.example templates.
- Add a health endpoint check and monitoring for the API and Mongo connection in production.
- If you want the app to be fully customer-ready, add: real Splunk connectors, real BigQuery integration, RBAC, request logging, rate limiting, and deployment automation.

## Current status
The project is structurally complete and the main real blocker I found was a frontend dependency mismatch:
- `date-fns` was set to 4.1.0 while `react-day-picker` expects 2.x/3.x.
- That has been corrected in the project to a compatible version.

After you fill in your .env files and install the app dependencies, it is ready to run and deploy.
