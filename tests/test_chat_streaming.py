"""
Automated Tests: Server-Sent Events (SSE) Chat Streaming Endpoint (/chat/message/stream)
Verifies:
1. Progressive SSE event formatting (start, token, done).
2. Emergency pre-stream interception with critical hotline 112/102.
3. Database persistence of streaming assistant responses.
4. Empty/whitespace message validation (HTTP 422).
5. Cross-patient conversation data isolation (HTTP 404).
"""
import json
import pytest
from fastapi import status


def _parse_sse_events(response_text: str):
    """Utility to parse SSE data payloads from a raw event-stream text."""
    events = []
    lines = response_text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("data:"):
            raw_json = line[len("data:"):].strip()
            if raw_json:
                try:
                    events.append(json.loads(raw_json))
                except json.JSONDecodeError:
                    pass
    return events


def test_chat_message_stream_basic(client, authenticated_patient):
    """
    Verify normal symptom consultation over SSE:
    1. Status code is 200 OK.
    2. Content-Type is text/event-stream.
    3. Events include 'start', 'token', and 'done'.
    4. Messages are saved to the database.
    """
    payload = {
        "content": "I have had a mild headache since this morning. What safe steps can I take?"
    }
    resp = client.post(
        "/chat/message/stream",
        json=payload,
        headers=authenticated_patient["headers"]
    )
    assert resp.status_code == status.HTTP_200_OK
    assert "text/event-stream" in resp.headers.get("content-type", "")

    events = _parse_sse_events(resp.text)
    assert len(events) >= 3

    event_types = [e.get("type") for e in events]
    assert "start" in event_types
    assert "token" in event_types
    assert "done" in event_types

    start_event = next(e for e in events if e.get("type") == "start")
    assert "conversation_id" in start_event
    conv_id = start_event["conversation_id"]

    done_event = next(e for e in events if e.get("type") == "done")
    assert "full_content" in done_event
    full_text = done_event["full_content"]
    assert len(full_text) > 30

    # Verify conversation history in DB
    hist_resp = client.get(
        f"/chat/history/{conv_id}",
        headers=authenticated_patient["headers"]
    )
    assert hist_resp.status_code == status.HTTP_200_OK
    history = hist_resp.json()
    assert len(history["messages"]) >= 2
    assert history["messages"][0]["role"] == "user"
    assert history["messages"][1]["role"] == "assistant"
    assert history["messages"][1]["content"] == full_text


def test_chat_message_stream_emergency(client, authenticated_patient):
    """
    CRITICAL SAFETY REQUIREMENT:
    Verify that emergency symptoms over SSE immediately yield an 'emergency' event
    with 112/102 guidelines without waiting for LLM completion.
    """
    payload = {
        "content": "Crushing chest pain radiating to my left arm, sweating heavily and feeling faint"
    }
    resp = client.post(
        "/chat/message/stream",
        json=payload,
        headers=authenticated_patient["headers"]
    )
    assert resp.status_code == status.HTTP_200_OK
    assert "text/event-stream" in resp.headers.get("content-type", "")

    events = _parse_sse_events(resp.text)
    event_types = [e.get("type") for e in events]

    assert "emergency" in event_types
    emergency_event = next(e for e in events if e.get("type") == "emergency")
    assert emergency_event["safety_flags"]["emergency_detected"] is True
    assert "112" in emergency_event["content"] or "EMERGENCY" in emergency_event["content"]


def test_chat_message_stream_empty_content_validation(client, authenticated_patient):
    """
    Verify that empty or whitespace-only messages are rejected with HTTP 422.
    """
    resp = client.post(
        "/chat/message/stream",
        json={"content": "     "},
        headers=authenticated_patient["headers"]
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "cannot be empty" in resp.json()["detail"].lower()


def test_chat_message_stream_existing_conversation(client, authenticated_patient):
    """
    Verify streaming into an existing conversation preserves multi-turn context.
    """
    # Turn 1
    resp1 = client.post(
        "/chat/message/stream",
        json={"content": "I am having mild fever of 100 F."},
        headers=authenticated_patient["headers"]
    )
    assert resp1.status_code == status.HTTP_200_OK
    events1 = _parse_sse_events(resp1.text)
    conv_id = next(e for e in events1 if e.get("type") == "start")["conversation_id"]

    # Turn 2 into same conversation
    resp2 = client.post(
        "/chat/message/stream",
        json={"conversation_id": conv_id, "content": "I am drinking plenty of fluids and resting."},
        headers=authenticated_patient["headers"]
    )
    assert resp2.status_code == status.HTTP_200_OK
    events2 = _parse_sse_events(resp2.text)
    conv_id2 = next(e for e in events2 if e.get("type") == "start")["conversation_id"]
    assert conv_id2 == conv_id

    # Check that history now has 4 messages
    hist_resp = client.get(
        f"/chat/history/{conv_id}",
        headers=authenticated_patient["headers"]
    )
    assert hist_resp.status_code == status.HTTP_200_OK
    history = hist_resp.json()
    assert len(history["messages"]) == 4


def test_chat_message_stream_patient_isolation(client, authenticated_patient, second_patient):
    """
    Verify Patient B cannot stream into Patient A's private conversation.
    """
    # Patient A creates a conversation
    resp_a = client.post(
        "/chat/message/stream",
        json={"content": "Private health inquiry regarding test results."},
        headers=authenticated_patient["headers"]
    )
    events_a = _parse_sse_events(resp_a.text)
    conv_id = next(e for e in events_a if e.get("type") == "start")["conversation_id"]

    # Patient B attempts to stream into Patient A's conversation
    resp_b = client.post(
        "/chat/message/stream",
        json={"conversation_id": conv_id, "content": "Unauthorized intrusion attempt."},
        headers=second_patient["headers"]
    )
    assert resp_b.status_code == status.HTTP_404_NOT_FOUND
