"""Backend tests for Weekly Digest endpoints and cron webhook."""
import os
import time
import uuid
import subprocess
import json
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # fallback: read from frontend env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').strip("'")
BASE_URL = BASE_URL.rstrip("/")

API = f"{BASE_URL}/api"

# Read cron secret
with open("/app/backend/.env") as f:
    env = {}
    for line in f:
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.strip().split("=", 1)
            env[k] = v.strip().strip('"').strip("'")
CRON_SECRET = env["WEBHOOK_CRON_SECRET"]

DEMO_EMAIL = "demo@insightlens.app"
DEMO_PASSWORD = "demo1234"


@pytest.fixture(scope="module")
def auth_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    token = r.json().get("token")
    assert token
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ---------- /api/digests/me ----------
def test_digest_me(auth_session):
    r = auth_session.get(f"{API}/digests/me", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == DEMO_EMAIL
    assert data["digest_email"] == "delivered@resend.dev"
    assert isinstance(data["subscribed"], bool)


# ---------- /api/digests/subscribe ----------
def test_digest_subscribe_true(auth_session):
    r = auth_session.post(f"{API}/digests/subscribe",
                          json={"subscribed": True, "digest_email": "delivered@resend.dev"}, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["subscribed"] is True
    assert data["digest_email"] == "delivered@resend.dev"
    # verify persistence
    me = auth_session.get(f"{API}/digests/me").json()
    assert me["subscribed"] is True
    assert me["digest_email"] == "delivered@resend.dev"


def test_digest_unsubscribe(auth_session):
    r = auth_session.post(f"{API}/digests/subscribe", json={"subscribed": False}, timeout=10)
    assert r.status_code == 200
    assert r.json()["subscribed"] is False
    me = auth_session.get(f"{API}/digests/me").json()
    assert me["subscribed"] is False
    # Re-subscribe for subsequent cron test
    auth_session.post(f"{API}/digests/subscribe",
                      json={"subscribed": True, "digest_email": "delivered@resend.dev"})


def _mongo_latest_digest_run():
    out = subprocess.run(
        ["mongosh", "--quiet", "--eval",
         "db=db.getSiblingDB('test_database'); printjson(db.digest_runs.find().sort({sent_at:-1}).limit(1).toArray())"],
        capture_output=True, text=True, timeout=15
    )
    return out.stdout


# ---------- /api/digests/preview ----------
def test_digest_preview_queues_and_sends(auth_session):
    before = _mongo_latest_digest_run()
    r = auth_session.post(f"{API}/digests/preview", timeout=10)
    assert r.status_code == 200
    assert r.json().get("status") == "queued"

    # Poll Mongo up to 90s for a new row
    found = False
    deadline = time.time() + 90
    while time.time() < deadline:
        time.sleep(5)
        latest = _mongo_latest_digest_run()
        if latest != before and ("sent" in latest or "error" in latest):
            found = True
            print("DIGEST RUN LATEST:", latest[:600])
            break
    assert found, "No new digest_runs row appeared within 90s"


# ---------- /api/cron/weekly-digest ----------
def test_cron_no_auth():
    r = requests.post(f"{API}/cron/weekly-digest", json={}, timeout=10)
    assert r.status_code == 401


def test_cron_wrong_token():
    r = requests.post(f"{API}/cron/weekly-digest",
                      headers={"Authorization": "Bearer wrong"}, json={}, timeout=10)
    assert r.status_code == 401


def test_cron_correct_token_and_idempotency():
    webhook_id = f"test_{uuid.uuid4().hex[:8]}"
    headers = {"Authorization": f"Bearer {CRON_SECRET}", "X-Webhook-Id": webhook_id}
    t0 = time.time()
    r = requests.post(f"{API}/cron/weekly-digest", headers=headers, json={"run_id": webhook_id}, timeout=10)
    elapsed = time.time() - t0
    assert r.status_code == 200, f"got {r.status_code} {r.text}"
    assert elapsed < 5, f"webhook ack took {elapsed:.1f}s (>5s)"
    assert r.json().get("status") == "accepted"

    # Second call -> duplicate
    r2 = requests.post(f"{API}/cron/weekly-digest", headers=headers, json={"run_id": webhook_id}, timeout=10)
    assert r2.status_code == 200
    assert r2.json().get("status") == "duplicate"

    # Wait for background work to record a digest_run (sent or error OK)
    deadline = time.time() + 90
    saw = False
    while time.time() < deadline:
        time.sleep(5)
        latest = _mongo_latest_digest_run()
        if "status:" in latest and ("'sent'" in latest or "'error'" in latest):
            saw = True
            print("CRON DIGEST RUN LATEST:", latest[:600])
            break
    assert saw, "Expected a digest_runs row after cron dispatch"
