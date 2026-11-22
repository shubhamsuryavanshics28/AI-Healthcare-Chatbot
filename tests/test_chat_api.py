"""
Automated Tests: AI Healthcare Chatbot Endpoints, Context Assembly, and Emergency Overrides
"""
from fastapi import status


def test_chat_message_creation_and_auto_conversation(client, authenticated_patient):
    payload = {
        "content": "What is the recommended DASH diet and lifestyle for high blood pressure?"
    }
    resp = client.post("/chat/message", json=payload, headers=authenticated_patient["headers"])
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["role"] == "assistant"
    assert len(data["content"]) > 20
    assert data["conversation_id"] is not None

    conv_id = data["conversation_id"]

    # Retrieve conversation history
    hist_resp = client.get(f"/chat/history/{conv_id}", headers=authenticated_patient["headers"])
    assert hist_resp.status_code == status.HTTP_200_OK
    conv_data = hist_resp.json()
    assert len(conv_data["messages"]) >= 2  # user + assistant


def test_chat_emergency_interception(client, authenticated_patient):
    """
    CRITICAL SAFETY REQUIREMENT:
    Verify that emergency symptoms immediately trigger emergency escalation in chat.
    """
    payload = {
        "content": "I am having severe crushing chest pain, cold sweating, and arm numbness right now"
    }
    resp = client.post("/chat/message", json=payload, headers=authenticated_patient["headers"])
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert "EMERGENCY" in data["content"] or "112" in data["content"]
    assert data["safety_flags"]["emergency_detected"] is True


def test_chat_rag_citations_included(client, authenticated_patient):
    payload = {
        "content": "What medications are dangerous for dengue fever patients according to Indian health guidelines?"
    }
    resp = client.post("/chat/message", json=payload, headers=authenticated_patient["headers"])
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["citations"] is not None
    assert len(data["citations"]) > 0
    assert any("Dengue" in c["title"] for c in data["citations"])


def test_delete_conversation(client, authenticated_patient):
    # Start chat
    resp = client.post(
        "/chat/message",
        json={"content": "Temporary consultation to delete"},
        headers=authenticated_patient["headers"]
    )
    conv_id = resp.json()["conversation_id"]

    # Delete
    del_resp = client.delete(f"/chat/history/{conv_id}", headers=authenticated_patient["headers"])
    assert del_resp.status_code == status.HTTP_200_OK

    # Verify 404
    get_resp = client.get(f"/chat/history/{conv_id}", headers=authenticated_patient["headers"])
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND
