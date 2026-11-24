# PROJECT STATUS: AI-Based Healthcare Chatbot for Patient Assistance and Triage

**Project ID:** 26P_3CSE294  
**Project Title:** AI-Based Healthcare Chatbot for Patient Assistance and Triage  
**Team Size:** 4  
**Degree/Major:** B.Tech Computer Science and Engineering (AI & ML)  
**Academic Demonstration Status:** ✅ COMPLETE & TESTED (Production-Ready Major Project)

---

## 1. System Architecture Summary

```text
+---------------------------------------------------------------------------------------+
|                                    PRESENTATION LAYER                                 |
|   HTML5 + CSS3 + Vanilla JavaScript (Responsive Healthcare Interface, Mobile-Ready)   |
|                                                                                       |
|  [Landing] [Register/Login] [Dashboard] [AI Chat & Triage] [Profile] [Medical Hist]   |
|  [Allergies & Meds] [Symptom Assessment Wizard] [Triage History] [Medicine Lookup]     |
+-------------------------------------------+-------------------------------------------+
                                            | JSON / REST API (JWT Authenticated)
                                            v
+---------------------------------------------------------------------------------------+
|                                    FASTAPI BACKEND                                    |
|                                                                                       |
|  +--------------------+  +----------------------+  +--------------------------------+ |
|  |   Authentication   |  |   Patient Records    |  |    Independent Emergency       | |
|  |  JWT + Argon2id    |  |  Profile, History,   |  |        Safety Engine           | |
|  | Data Isolation RLS |  |  Allergies, Meds     |  | (Deterministic Medical Rules)  | |
|  +--------------------+  +----------------------+  +--------------------------------+ |
|                                                                   |                   |
|  +---------------------------------------------+                  | Overrides AI      |
|  |              AI & Chat Engine               |                  v                   |
|  |  - AsyncOpenAI (Responses / Chat API)       |  +---------------------------------+ |
|  |  - Medical Safety Prompts & Guardrails      |  |  4-Level Preliminary Triage     | |
|  |  - Chat History & Dynamic Context Window    |  |  1. Emergency (Call 112 / ER)   | |
|  |  - Non-prescriptive, Non-diagnostic Rules   |  |  2. Urgent Medical Attention    | |
|  |  - Assist First -> Ask Next -> Personalize  |  |  3. Routine Consultation        | |
|  +----------------------+----------------------+  |  4. Self-care & Monitoring      | |
|                         | Grounding / Citations   +---------------------------------+ |
|                         v                                                             |
|  +---------------------------------------------+                                      |
|  |                 RAG Pipeline                |                                      |
|  |  - PyMuPDF PDF Text & Section Extraction    |                                      |
|  |  - Semantic Chunking & Metadata Enrichment  |                                      |
|  |  - OpenAI text-embedding-3-small Embeddings |                                      |
|  |  - Hybrid Retrieval (Vector + Keyword)      |                                      |
|  |  - Supportive Evidence (Not a Gatekeeper)   |                                      |
|  +---------------------------------------------+                                      |
+---------------------+-------------------------------------+---------------------------+
                      |                                     |
                      v                                     v
+-----------------------------------+ +-------------------------------------------------+
|         RELATIONAL DATABASE       | |               VECTOR DATABASE                   |
|       SQLite (SQLAlchemy ORM)     | |              Persistent ChromaDB                |
|  - Users & Consents               | |  - Official Medical Docs (WHO, CDC, MedlinePlus)|
|  - Patient Profiles               | |  - Document Chunks, Embeddings, Metadata        |
|  - Medical Conditions & Allergies | |  - Curated Indian Health & MoHFW References     |
|  - Current Medications            | +-------------------------------------------------+
|  - Conversations & Chat Messages  |
|  - Symptom Assessments & Triage   |
|  - Curated Medicine Repository    |
+-----------------------------------+
```

---

## 2. Development Phases & Verification Status

| Phase | Description | Status | Verification & Deliverables |
|---|---|---|---|
| **Phase 1** | Project initialization, directory structure, environment setup, database models & schema | ✅ COMPLETED | SQLite initialized, SQLAlchemy models created (`User`, `PatientProfile`, `MedicalCondition`, `Allergy`, `PatientMedication`, `Conversation`, `ChatMessage`, `SymptomAssessment`, `TriageResult`, `MedicineInformation`). |
| **Phase 2** | User authentication, Argon2id hashing, JWT tokens, user consent, route protection | ✅ COMPLETED | `/auth/register`, `/auth/login`, `/auth/me`, `/auth/logout`. Scoped data authorization. 8 automated unit tests passed. |
| **Phase 3** | Patient record management (Profile, Medical conditions, Allergies, Current medications CRUD) | ✅ COMPLETED | Full CRUD routes with per-user data isolation. Cross-user access strictly returns 404. 5 tests passed. |
| **Phase 4** | Independent emergency detection safety engine & 4-tier triage system | ✅ COMPLETED | Cardiac, respiratory, FAST stroke, anaphylaxis, massive hemorrhage, DKA rules. India 112 helpline. 13 tests passed. |
| **Phase 5** | RAG medical knowledge ingestion pipeline (PyMuPDF, ChromaDB, official sources) & hybrid retrieval | ✅ COMPLETED | PyMuPDF extraction, 28 indexed chunks, semantic similarity + keyword match, supportive grounding. 4 tests passed. |
| **Phase 6** | AI Chatbot service (AsyncOpenAI, conversational history, grounding, safety guardrails, offline fallback) | ✅ COMPLETED | Official AsyncOpenAI SDK, clinical prompt engineering, citations, graceful grounded fallback when offline. 4 tests passed. |
| **Phase 7** | Source-backed medicine information lookup module | ✅ COMPLETED | 10 curated verified medicines (FDA, MedlinePlus, CDSCO), generic names, brand names, indications, black box warnings. 4 tests passed. |
| **Phase 8** | Complete frontend UI implementation (Landing, Auth, Dashboard, Chat, Records, Triage, Medicine) | ✅ COMPLETED | 10 responsive HTML pages, clean healthcare design (blue/teal/white), mobile-friendly navigation, modal dialogs. |
| **Phase 9** | Automated testing & Manual medical safety benchmark | ✅ COMPLETED | 46 Pytest test cases passing in 4.65 seconds. Complete manual clinical safety suite passed. |
| **Phase 10**| End-to-end acceptance testing, documentation (README, diagrams, deployment guide) & demonstration prep | ✅ COMPLETED | Full 28-step acceptance checklist executed programmatically with 100% success. Render Procfile, run.py, Swagger docs ready. |
| **Phase 11**| **AI Consultant Conversational Overhaul & RAG Gatekeeper Decoupling** | ✅ COMPLETED | Implemented *Assist First -> Ask Next -> Personalize Continuously*. Decoupled RAG from blocking general assistance. Multi-turn context memory tracking. Markdown rendering & retry UI. 15 new automated tests added. |

---

## 3. Detailed Summary of Phase 11: AI Consultant Overhaul

### Problems Identified & Root Causes
1. **RAG Gatekeeping**: When queries did not find an exact document match in the 5 local guidelines, the system previously output: *"Our current verified medical knowledge base does not contain an exact protocol match for this specific topic."* This blocked safe, evidence-based general advice.
2. **Missing Immediate Assistance**: The chatbot previously asked questions without offering immediate, practical relief steps (hydration, rest, compress, positioning, dietary comfort).
3. **Conversational Memory Deficits**: Follow-up turns (e.g. "since yesterday", "continuous", "getting worse") were not systematically tracked, occasionally prompting repeated questions.
4. **Intent Confusion**: Greetings and casual conversation were triggering vector database lookups unnecessarily.
5. **Frontend Rendering**: Markdown elements (`###` headers, bullet points, numbered lists) were rendered with plain regex replacements.

### Improvements Implemented
- **Assist First -> Ask Next -> Personalize Continuously**: The AI immediately provides practical self-care steps in the first response for common symptoms (Headache, Fever, Sore throat, Cough, Stomach ache, Nausea, Fatigue, etc.), followed by non-diagnostic explanations, 1–3 focused questions, and red-flag warning signs.
- **RAG as Supportive Evidence (Not a Gatekeeper)**: Official medical references (WHO, CDC, FDA, MoHFW) are retrieved to support facts and provide citations. When no specific document exists, safe general clinical guidance is provided without rejecting the patient.
- **Intent Classifier**: Automatically distinguishes Greetings, Out-of-Scope queries, Short Follow-Ups, and Clinical Inquiries.
- **Patient Background Integration**: Automatically includes patient demographics (age, gender), active conditions, drug/food allergies, and current medications to cross-reference potential contraindications.
- **Frontend Markdown & UX**: Upgraded Markdown renderer supporting headings (`###`), styled list items, callout boxes, and an automated "🔄 Retry" button on communication errors.

---

## 4. Test Suite Summary

- **Total Automated Pytest Tests:** 61 (46 baseline + 15 AI Consultant improvement tests)
- **Passed:** 61 (100%)
- **Failed:** 0
- **Execution Time:** ~8.69 seconds
- **100-Case Clinical Evaluation Benchmark:** 100 / 100 Passed (100.0% accuracy & safety score)
- **End-to-End Acceptance Steps:** 28 / 28 Passed (100% Complete)

---

## 5. Key Artifacts & Deliverables

1. **Source Code:** Complete backend (`backend/`), frontend (`frontend/`), models, schemas, services, and routes.
2. **Database:** SQLite `healthcare.db` with relational schema ready for PostgreSQL.
3. **Vector DB:** Persistent ChromaDB at `data/chromadb/` with medical literature chunks.
4. **Official Reference Documents:** WHO, CDC, FDA, MedlinePlus, and India MoHFW PDFs in `data/medical_docs/`.
5. **Interactive Web Interface:** HTML5/CSS3/Vanilla JS with active chat, symptom assessment wizard, and verified medicine directory.
6. **Live Deployment:** [https://arogya-ai-wdj7.onrender.com](https://arogya-ai-wdj7.onrender.com)
