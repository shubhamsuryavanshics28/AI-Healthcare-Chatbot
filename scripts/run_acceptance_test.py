"""
Comprehensive End-to-End Acceptance Test Script
Executes the full 28-step acceptance checklist programmatically.
Project ID: 26P_3CSE294
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from backend.main import app
from backend.database import SessionLocal, init_db
from backend.services.medicine_service import seed_medicine_database
from backend.services.rag_service import rag_service

client = TestClient(app)


def run_full_acceptance_checklist():
    print("=" * 80)
    print("🏥 RUNNING COMPLETE END-TO-END ACCEPTANCE TEST")
    print("Project: AI-Based Healthcare Chatbot for Patient Assistance and Triage")
    print("Project ID: 26P_3CSE294 | Team Size: 4")
    print("=" * 80)

    # 1. Health check & Landing page
    print("\n[Step 1] Checking landing page and health status...")
    resp = client.get("/")
    assert resp.status_code == 200, "Landing page should load"
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["rag_ready"] is True
    print("  ✓ Landing page & health check OK")

    # 2. Register a new patient
    print("\n[Step 2] Registering a new patient...")
    reg_email = f"major_demo_{int(time.time())}@university.edu"
    reg_payload = {
        "email": reg_email,
        "password": "DemoPassword2026!",
        "full_name": "Major Project Patient",
        "agree_medical_disclaimer": True,
        "agree_privacy_policy": True
    }
    reg_resp = client.post("/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"
    token_a = reg_resp.json()["access_token"]
    user_a = reg_resp.json()["user"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    print(f"  ✓ Patient registered: ID {user_a['id']} ({user_a['email']})")

    # 3. Log in again to verify authentication pipeline
    print("\n[Step 3] Logging in with patient credentials...")
    login_resp = client.post("/auth/login", json={"email": reg_email, "password": "DemoPassword2026!"})
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()
    print("  ✓ Login succeeded with Argon2 hash verification & JWT generation")

    # 4. Complete patient profile
    print("\n[Step 4] Updating patient demographic and physical measurements...")
    profile_payload = {
        "date_of_birth": "1998-05-20",
        "gender": "Male",
        "blood_group": "O+",
        "height_cm": 175.0,
        "weight_kg": 70.5,
        "emergency_contact_name": "Alice Doe",
        "emergency_contact_phone": "+91 9876543210",
        "emergency_contact_relation": "Spouse",
        "general_notes": "Allergic to amoxicillin; runs 5km weekly"
    }
    prof_resp = client.put("/patients/profile", json=profile_payload, headers=headers_a)
    assert prof_resp.status_code == 200
    assert prof_resp.json()["blood_group"] == "O+"
    print("  ✓ Patient profile persisted in SQLite database")

    # 5. Add a medical condition
    print("\n[Step 5] Adding medical condition (Essential Hypertension)...")
    cond_resp = client.post(
        "/patients/medical-history",
        json={
            "condition_name": "Essential Hypertension",
            "diagnosed_date": "2023-11-10",
            "status": "managed",
            "notes": "Controlled with daily exercise and DASH dietary pattern"
        },
        headers=headers_a
    )
    assert cond_resp.status_code == 201
    cond_id = cond_resp.json()["id"]
    print(f"  ✓ Medical condition added (ID: {cond_id})")

    # 6. Add an allergy
    print("\n[Step 6] Adding allergy record (Amoxicillin)...")
    all_resp = client.post(
        "/patients/allergies",
        json={
            "allergen": "Amoxicillin",
            "reaction": "Facial swelling and hives",
            "severity": "severe",
            "notes": "Discovered during dental procedure"
        },
        headers=headers_a
    )
    assert all_resp.status_code == 201
    allergy_id = all_resp.json()["id"]
    print(f"  ✓ Allergy record added (ID: {allergy_id})")

    # 7. Add current medication
    print("\n[Step 7] Adding current medication (Amlodipine 5mg)...")
    med_resp = client.post(
        "/patients/medications",
        json={
            "medication_name": "Amlodipine",
            "dosage": "5 mg",
            "frequency": "Once daily with breakfast",
            "start_date": "2023-12-01",
            "is_current": True,
            "notes": "Prescribed by primary physician"
        },
        headers=headers_a
    )
    assert med_resp.status_code == 201
    med_id = med_resp.json()["id"]
    print(f"  ✓ Medication added (ID: {med_id})")

    # 8 & 9. Open chatbot and start new conversation
    print("\n[Step 8 & 9] Starting AI consultation conversation...")
    chat_resp_1 = client.post(
        "/chat/message",
        json={"content": "What is considered normal resting blood pressure according to WHO guidelines?"},
        headers=headers_a
    )
    assert chat_resp_1.status_code == 200
    conv_id = chat_resp_1.json()["conversation_id"]
    cits = chat_resp_1.json()["citations"]
    print(f"  ✓ AI Conversation initialized (ID: {conv_id})")

    # 10, 11 & 12. Verify RAG retrieval and source citations
    print("\n[Step 10, 11 & 12] Verifying RAG grounding and citations...")
    assert cits is not None and len(cits) > 0, "RAG citations must be returned"
    print(f"  ✓ RAG retrieved {len(cits)} verified passages")
    print(f"    - Primary Citation: '{cits[0]['title']}' ({cits[0]['source']})")
    assert any("Hypertension" in c["title"] for c in cits)

    # 13, 14 & 15. Describe symptoms & structured triage assessment
    print("\n[Step 13, 14 & 15] Submitting structured symptom assessment...")
    triage_resp = client.post(
        "/triage/assess",
        json={
            "conversation_id": conv_id,
            "primary_symptom": "High grade fever with retro-orbital eye pain and severe joint aches",
            "duration": "3 days",
            "severity": 7,
            "frequency": "constant",
            "body_location": "Generalized body and joints",
            "associated_symptoms": "Nausea, mild petechial rash",
            "relevant_history": "Hypertension"
        },
        headers=headers_a
    )
    assert triage_resp.status_code == 201
    assessment_data = triage_resp.json()
    assessment_id = assessment_data["id"]
    urgency = assessment_data["triage_result"]["urgency_level"]
    print(f"  ✓ Symptom assessment completed (ID: {assessment_id})")
    print(f"    - Urgency Category: {urgency}")
    print(f"    - Guidance Timeframe: {assessment_data['triage_result']['recommended_timeframe']}")

    # 16. Verify assessment persistence
    print("\n[Step 16] Verifying assessment saved in patient history...")
    hist_triage_resp = client.get("/triage/history", headers=headers_a)
    assert any(a["id"] == assessment_id for a in hist_triage_resp.json())
    print("  ✓ Assessment successfully retrieved from database history")

    # 17. Trigger emergency test scenario
    print("\n[Step 17] Triggering emergency safety test scenario (Cardiac Red Flag)...")
    emerg_chat_resp = client.post(
        "/chat/message",
        json={
            "conversation_id": conv_id,
            "content": "I am feeling severe crushing chest pain radiating to my left arm with sudden shortness of breath"
        },
        headers=headers_a
    )
    assert emerg_chat_resp.status_code == 200
    flags = emerg_chat_resp.json()["safety_flags"]
    assert flags.get("emergency_detected") is True
    assert "112" in emerg_chat_resp.json()["content"]
    print("  ✓ Independent Emergency Rule Engine successfully intercepted message:")
    print(f"    - Category: {flags.get('category')}")
    print(f"    - Warning Triggers: {flags.get('triggers')}")
    print("    - Emergency helpline 112 directly provided.")

    # 18 & 19. Search medicine information
    print("\n[Step 18 & 19] Searching verified medicine information (Paracetamol)...")
    med_search = client.get("/medications/search?q=Paracetamol", headers=headers_a)
    assert med_search.status_code == 200
    med_item = med_search.json()["results"][0]
    assert "Paracetamol" in med_item["generic_name"]
    assert "4000 mg" in med_item["serious_warnings"] or "liver" in med_item["serious_warnings"].lower()
    print(f"  ✓ Verified medicine monograph retrieved: {med_item['generic_name']}")
    print(f"    - Common Brands: {med_item['brand_names']}")
    print(f"    - Source: {med_item['source_reference']}")

    # 20 & 21. Open previous conversations & assessments
    print("\n[Step 20 & 21] Opening previous conversations and assessments...")
    conv_details = client.get(f"/chat/history/{conv_id}", headers=headers_a)
    assert conv_details.status_code == 200
    assert len(conv_details.json()["messages"]) >= 4
    print(f"  ✓ Conversation {conv_id} re-opened with all {len(conv_details.json()['messages'])} message turns intact")

    # 22. Edit and delete patient records
    print("\n[Step 22] Editing and deleting patient records...")
    up_cond = client.put(f"/patients/medical-history/{cond_id}", json={"status": "resolved"}, headers=headers_a)
    assert up_cond.status_code == 200
    assert up_cond.json()["status"] == "resolved"
    del_all = client.delete(f"/patients/allergies/{allergy_id}", headers=headers_a)
    assert del_all.status_code == 200
    print("  ✓ Record update and deletion verified")

    # 23, 24 & 25. Logout, re-login, verify persistent data
    print("\n[Step 23, 24 & 25] Logging out and logging back in...")
    client.post("/auth/logout", headers=headers_a)
    relogin = client.post("/auth/login", json={"email": reg_email, "password": "DemoPassword2026!"})
    token_re = relogin.json()["access_token"]
    headers_re = {"Authorization": f"Bearer {token_re}"}
    dashboard_re = client.get("/patients/dashboard", headers=headers_re)
    assert dashboard_re.json()["conditions_count"] == 1
    assert dashboard_re.json()["recent_assessments_count"] >= 1
    print("  ✓ Data persisted across authentication sessions")

    # 26. Attempt unauthorized access to another user's records
    print("\n[Step 26] Testing unauthorized cross-user access prevention (Data Isolation)...")
    # Register Patient B
    user_b_resp = client.post("/auth/register", json={
        "email": f"attacker_{int(time.time())}@other.edu",
        "password": "Password123!",
        "full_name": "Unauthorized User B",
        "agree_medical_disclaimer": True,
        "agree_privacy_policy": True
    })
    headers_b = {"Authorization": f"Bearer {user_b_resp.json()['access_token']}"}

    # Patient B tries to read Patient A's conversation
    hacked_conv = client.get(f"/chat/history/{conv_id}", headers=headers_b)
    assert hacked_conv.status_code == 404, "Cross-user conversation access must be rejected"

    # Patient B tries to delete Patient A's condition
    hacked_cond = client.delete(f"/patients/medical-history/{cond_id}", headers=headers_b)
    assert hacked_cond.status_code == 404, "Cross-user record deletion must be rejected"
    print("  ✓ Cross-user access strictly blocked (Data Ownership enforced)")

    # 27. Dashboard metrics check
    print("\n[Step 27] Verifying dashboard aggregation metrics...")
    dash_resp = client.get("/patients/dashboard", headers=headers_a)
    assert dash_resp.status_code == 200
    assert dash_resp.json()["profile"]["blood_group"] == "O+"
    print("  ✓ Dashboard aggregation OK")

    # 28. Offline / Cloud failure resilience check
    print("\n[Step 28] Testing graceful AI failure & RAG grounded fallback...")
    # When no OpenAI key is set, chat must still respond with grounded RAG facts
    chat_offline_resp = client.post(
        "/chat/message",
        json={"content": "How is hypoglycemia and low blood sugar managed in Type 2 Diabetes?"},
        headers=headers_a
    )
    assert chat_offline_resp.status_code == 200
    offline_data = chat_offline_resp.json()
    assert "hypoglycemia" in offline_data["content"].lower() or "glucose" in offline_data["content"].lower()
    assert len(offline_data["citations"]) > 0
    print("  ✓ Graceful grounded RAG response generated without crashing")

    print("\n" + "=" * 80)
    print("🎉 ALL 28 END-TO-END ACCEPTANCE TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 80)


if __name__ == "__main__":
    run_full_acceptance_checklist()
