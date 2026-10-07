"""Tests for streaming chat endpoint + PDF + backward-compat."""
import json
import os
import time
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
DEMO_EMAIL = "demo@insightlens.app"
DEMO_PASSWORD = "demo1234"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def chat_id(session):
    r = session.post(f"{BASE_URL}/api/chats", json={})
    assert r.status_code == 200
    return r.json()["chat_id"]


def _consume_sse(resp):
    events = []
    buf = ""
    for raw in resp.iter_content(chunk_size=None, decode_unicode=True):
        if not raw:
            continue
        buf += raw
        while "\n\n" in buf:
            chunk, buf = buf.split("\n\n", 1)
            for line in chunk.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    try:
                        events.append(json.loads(line[5:].strip()))
                    except Exception:
                        pass
    return events


def test_stream_endpoint_content_type_and_ordering(session, chat_id):
    """POST /api/chats/{id}/messages/stream — Content-Type + ordered events + persistence."""
    with session.post(
        f"{BASE_URL}/api/chats/{chat_id}/messages/stream",
        json={"content": "Why was checkout rate down yesterday in the US?", "sources": ["splunk", "bigquery"]},
        stream=True,
        timeout=120,
    ) as r:
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert ct.startswith("text/event-stream"), f"bad content-type: {ct}"
        events = _consume_sse(r)

    assert len(events) >= 4, f"too few events: {events}"
    types = [e["type"] for e in events]
    assert types[0] == "user_message"
    assert "start" in types
    assert "delta" in types
    assert "artifacts" in types
    assert types[-1] == "done"

    # order: user_message -> start -> deltas -> artifacts -> done
    assert types.index("start") < types.index("delta")
    assert types.index("delta") < types.index("artifacts")
    assert types.index("artifacts") < types.index("done")

    start_evt = next(e for e in events if e["type"] == "start")
    done_evt = next(e for e in events if e["type"] == "done")
    assert start_evt["message_id"] == done_evt["message_id"]
    assistant_id = start_evt["message_id"]

    full_text = "".join(e.get("text", "") for e in events if e["type"] == "delta")
    assert len(full_text) > 20, f"no streamed text: {full_text!r}"

    artifacts_evt = next(e for e in events if e["type"] == "artifacts")
    assert isinstance(artifacts_evt["data"], list)
    assert len(artifacts_evt["data"]) > 0

    # Verify persistence via GET /messages
    m = session.get(f"{BASE_URL}/api/chats/{chat_id}/messages").json()["messages"]
    asst = [x for x in m if x["message_id"] == assistant_id]
    assert len(asst) == 1
    assert asst[0]["role"] == "assistant"
    assert asst[0]["content"] == full_text
    assert asst[0]["artifacts"] == artifacts_evt["data"]

    # Chat auto-renamed
    chats = session.get(f"{BASE_URL}/api/chats").json()["chats"]
    me = next(c for c in chats if c["chat_id"] == chat_id)
    assert me["title"].startswith("Why was checkout rate")

    # PDF endpoint
    pdf = session.get(f"{BASE_URL}/api/messages/{assistant_id}/pdf")
    assert pdf.status_code == 200, f"pdf status={pdf.status_code} body={pdf.text[:200]}"
    assert pdf.headers.get("content-type", "").startswith("application/pdf")
    assert pdf.content[:4] == b"%PDF"


def test_stream_404_for_other_users_chat(session):
    """Stream on nonexistent chat returns 404."""
    r = session.post(
        f"{BASE_URL}/api/chats/chat_doesnotexist/messages/stream",
        json={"content": "hi", "sources": ["splunk"]},
    )
    assert r.status_code == 404


def test_non_streaming_backward_compat(session):
    """Original POST /api/chats/{id}/messages still returns full response."""
    r = session.post(f"{BASE_URL}/api/chats", json={})
    cid = r.json()["chat_id"]
    r = session.post(
        f"{BASE_URL}/api/chats/{cid}/messages",
        json={"content": "Compare revenue across markets for the last 14 days.", "sources": ["bigquery"]},
        timeout=120,
    )
    assert r.status_code == 200
    body = r.json()
    assert "user_message" in body and "assistant_message" in body
    assert body["assistant_message"]["role"] == "assistant"
    assert len(body["assistant_message"]["content"]) > 10
    assert isinstance(body["assistant_message"]["artifacts"], list)
    # cleanup
    session.delete(f"{BASE_URL}/api/chats/{cid}")
