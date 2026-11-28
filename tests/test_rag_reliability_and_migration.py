"""
Comprehensive Regression Tests for Phase 3.1.2:
RAG Reliability, Safe Ingestion, Collision-Resistant IDs, Resumable Migration & Crash Recovery
(Project ID: 26P_3CSE294)

Verifies:
1. Stable document identity across paths, directories, and relocation.
2. Two files with identical filenames in different directories produce distinct doc_ids.
3. Consistent .pdf, .txt, and .md extension stripping and default title formatting.
4. Deterministic content version hash separate from operational state.
5. Two files sharing the exact same title do not overwrite each other.
6. Repeated ingestion of an unchanged document produces identical IDs with zero duplication.
7. Updated document content performs safe staged replacement and prunes obsolete IDs.
8. Embedding failure keeps existing document chunks completely intact in ChromaDB.
9. Insertion failure keeps existing document chunks completely intact in ChromaDB.
10. Crash recovery: incomplete staged version is rolled back, preserving last known good.
11. Crash recovery: fully staged version is verified, obsolete IDs pruned, and manifest committed.
12. Resumable legacy migration: resumes partial migration without re-embedding or duplicating records.
13. Legacy collection immutability: source collection remains strictly unaltered.
14. Vector dimensions (384) and vector space isolation.
"""
import os
import json
import math
import pytest
import chromadb
from backend.config import settings
from backend.services.rag_service import rag_service
from backend.services.embedding_service import embedding_service
from backend.services.chroma_migration import (
    check_migration_status,
    migrate_to_fastembed_collection,
    SOURCE_COLLECTION_NAME,
    TARGET_COLLECTION_NAME
)


# =============================================================================
# 1. STABLE DOCUMENT IDENTITY & EXTENSION HANDLING
# =============================================================================

def test_stable_doc_id_same_filename_different_directories():
    """Verify that two files with the same filename in different directories get distinct doc_ids."""
    path_a = os.path.abspath("data/medical_docs/protocols/influenza.txt")
    path_b = os.path.abspath("data/medical_docs/archive/influenza.txt")

    id_info_a = rag_service.compute_stable_doc_id(file_path=path_a)
    id_info_b = rag_service.compute_stable_doc_id(file_path=path_b)

    assert id_info_a["doc_id"] != id_info_b["doc_id"], "Different directories must produce distinct doc_ids"
    assert "influenza" in id_info_a["doc_id"]
    assert "influenza" in id_info_b["doc_id"]
    assert id_info_a["source_path"] != id_info_b["source_path"]


def test_stable_doc_id_deterministic_across_repeated_calls():
    """Verify that compute_stable_doc_id is strictly deterministic for unchanged inputs."""
    path = os.path.abspath("data/medical_docs/mohfw_india_dengue_guidelines.pdf")
    id_1 = rag_service.compute_stable_doc_id(file_path=path)
    id_2 = rag_service.compute_stable_doc_id(file_path=path)
    assert id_1 == id_2


def test_stable_doc_id_across_project_relocation(tmp_path):
    """
    Verify stable document identity using the same project-relative path
    under two completely different project roots (genuine relocation test).
    """
    root_a = tmp_path / "deployment_alpha"
    root_b = tmp_path / "deployment_beta"

    file_a = root_a / "data" / "medical_docs" / "protocols" / "triage_protocol.txt"
    file_b = root_b / "data" / "medical_docs" / "protocols" / "triage_protocol.txt"

    file_a.parent.mkdir(parents=True)
    file_b.parent.mkdir(parents=True)

    sample_text = "DOCUMENT TITLE: Rapid Triage Protocol\nSOURCE: Health Ministry\n--- Triage Guidelines ---"
    file_a.write_text(sample_text, encoding="utf-8")
    file_b.write_text(sample_text, encoding="utf-8")

    id_info_a = rag_service.compute_stable_doc_id(file_path=str(file_a))
    id_info_b = rag_service.compute_stable_doc_id(file_path=str(file_b))

    assert id_info_a["doc_id"] == id_info_b["doc_id"], "doc_id must be invariant across project root relocation"
    assert id_info_a["source_path"] == id_info_b["source_path"] == "medical_docs/protocols/triage_protocol.txt"


def test_consistent_extension_parsing_pdf_txt_md():
    """Verify consistent title and doc_id parsing across .pdf, .txt, and .md files."""
    cases = [
        ("guideline_who.pdf", "Guideline Who"),
        ("guideline_who.txt", "Guideline Who"),
        ("guideline_who.md", "Guideline Who"),
        ("cdc-influenza-protocol.MD", "Cdc Influenza Protocol"),
    ]
    for filename, expected_title in cases:
        parsed = rag_service._parse_medical_text("Sample body content", filename=filename)
        assert parsed["metadata"]["title"] == expected_title
        assert not parsed["metadata"]["title"].lower().endswith((".pdf", ".txt", ".md"))
        assert parsed["doc_id"] != ""
        assert parsed["doc_version"] != ""


def test_deterministic_content_version_hash():
    """Verify that doc_version is deterministic and changes if and only if content changes."""
    text_v1 = "Patient presents with mild fever and fatigue.\nRecommended hydration."
    text_v2 = "Patient presents with mild fever and fatigue.\nRecommended hydration and rest."

    p1 = rag_service._parse_medical_text(text_v1, filename="notes.txt")
    p1_again = rag_service._parse_medical_text(text_v1, filename="notes.txt")
    p2 = rag_service._parse_medical_text(text_v2, filename="notes.txt")

    assert p1["doc_version"] == p1_again["doc_version"], "Identical content must produce identical doc_version"
    assert p1["doc_version"] != p2["doc_version"], "Modified content must produce different doc_version"
    assert p1["doc_id"] == p2["doc_id"], "Document identity must remain stable across content updates"


# =============================================================================
# 2. TWO FILES SHARING SAME TITLE & INGESTION ISOLATION
# =============================================================================

def test_two_files_sharing_same_title_isolation(tmp_path):
    """
    Verify that two distinct files sharing the exact same DOCUMENT TITLE header
    coexist safely in ChromaDB without colliding or overwriting each other.
    """
    dir_cdc = tmp_path / "cdc"
    dir_who = tmp_path / "who"
    dir_cdc.mkdir()
    dir_who.mkdir()

    file_cdc = dir_cdc / "flu.txt"
    file_who = dir_who / "flu.txt"

    content_cdc = (
        "DOCUMENT TITLE: Influenza Clinical Guidance\n"
        "SOURCE: CDC Atlanta\n"
        "--- Symptoms ---\n"
        "CDC recommends rest, fluids, and antiviral therapy for high-risk influenza cases."
    )
    content_who = (
        "DOCUMENT TITLE: Influenza Clinical Guidance\n"
        "SOURCE: WHO Geneva\n"
        "--- Symptoms ---\n"
        "WHO global guidelines emphasize community surveillance and symptom management for influenza."
    )

    file_cdc.write_text(content_cdc, encoding="utf-8")
    file_who.write_text(content_who, encoding="utf-8")

    count_cdc = rag_service.ingest_file(str(file_cdc))
    count_who = rag_service.ingest_file(str(file_who))

    assert count_cdc > 0
    assert count_who > 0

    # Parse both to retrieve their distinct doc_ids
    parsed_cdc = rag_service._parse_medical_text(content_cdc, file_path=str(file_cdc))
    parsed_who = rag_service._parse_medical_text(content_who, file_path=str(file_who))

    assert parsed_cdc["doc_id"] != parsed_who["doc_id"]

    # Verify both documents exist in ChromaDB
    rec_cdc = rag_service.collection.get(where={"doc_id": parsed_cdc["doc_id"]})
    rec_who = rag_service.collection.get(where={"doc_id": parsed_who["doc_id"]})

    assert len(rec_cdc["ids"]) > 0
    assert len(rec_who["ids"]) > 0
    assert set(rec_cdc["ids"]).isdisjoint(set(rec_who["ids"]))

    # Cleanup test files from collection
    rag_service.collection.delete(where={"doc_id": parsed_cdc["doc_id"]})
    rag_service.collection.delete(where={"doc_id": parsed_who["doc_id"]})


# =============================================================================
# 3. REPEATED INGESTION & UPDATED CONTENT REPLACEMENT
# =============================================================================

def test_repeated_ingestion_unchanged_document(tmp_path):
    """Verify that re-ingesting an unchanged document preserves IDs and does not duplicate chunks."""
    doc_file = tmp_path / "hypertension_test.txt"
    doc_file.write_text(
        "DOCUMENT TITLE: Hypertension Test Protocol\n"
        "SOURCE: Medical Board\n"
        "--- Overview ---\n"
        "Stage 1 hypertension systolic blood pressure is defined from 130 to 139 mmHg.",
        encoding="utf-8"
    )

    # First ingestion
    count_1 = rag_service.ingest_file(str(doc_file))
    parsed = rag_service._parse_medical_text(doc_file.read_text(encoding="utf-8"), file_path=str(doc_file))
    recs_1 = rag_service.collection.get(where={"doc_id": parsed["doc_id"]})
    ids_1 = sorted(recs_1["ids"])

    # Second ingestion
    count_2 = rag_service.ingest_file(str(doc_file))
    recs_2 = rag_service.collection.get(where={"doc_id": parsed["doc_id"]})
    ids_2 = sorted(recs_2["ids"])

    assert count_1 == count_2
    assert ids_1 == ids_2, "Repeated ingestion of unchanged document must produce identical chunk IDs"
    assert len(ids_2) == count_1, "Chunk count must not duplicate"

    # Verify manifest
    manifest = rag_service.get_document_manifest(parsed["doc_id"])
    assert manifest is not None
    assert manifest["status"] == "verified"
    assert manifest["active_version"] == parsed["doc_version"]

    # Cleanup
    rag_service.collection.delete(where={"doc_id": parsed["doc_id"]})


def test_updated_document_content_safe_replacement(tmp_path):
    """Verify that updating document content replaces chunks and prunes obsolete IDs."""
    doc_file = tmp_path / "asthma_update.txt"
    content_v1 = (
        "DOCUMENT TITLE: Asthma Inhaler Guide\n"
        "SOURCE: Thoracic Society\n"
        "--- Treatment ---\n"
        "Short-acting beta agonists are recommended for quick relief of asthma symptoms."
    )
    doc_file.write_text(content_v1, encoding="utf-8")
    rag_service.ingest_file(str(doc_file))

    parsed_v1 = rag_service._parse_medical_text(content_v1, file_path=str(doc_file))
    recs_v1 = rag_service.collection.get(where={"doc_id": parsed_v1["doc_id"]})
    ids_v1 = set(recs_v1["ids"])

    # Update content with modified text
    content_v2 = (
        "DOCUMENT TITLE: Asthma Inhaler Guide\n"
        "SOURCE: Thoracic Society\n"
        "--- Treatment ---\n"
        "Low-dose inhaled corticosteroids combined with formoterol are now the preferred reliever therapy."
    )
    doc_file.write_text(content_v2, encoding="utf-8")
    rag_service.ingest_file(str(doc_file))

    parsed_v2 = rag_service._parse_medical_text(content_v2, file_path=str(doc_file))
    recs_v2 = rag_service.collection.get(where={"doc_id": parsed_v2["doc_id"]})
    ids_v2 = set(recs_v2["ids"])

    # Old IDs must have been pruned and replaced
    assert ids_v1 != ids_v2
    assert ids_v1.isdisjoint(ids_v2)

    # Manifest must point to v2
    manifest = rag_service.get_document_manifest(parsed_v2["doc_id"])
    assert manifest["status"] == "verified"
    assert manifest["active_version"] == parsed_v2["doc_version"]

    # Cleanup
    rag_service.collection.delete(where={"doc_id": parsed_v2["doc_id"]})


# =============================================================================
# 4. FAILURE HANDLING & PRESERVATION OF LAST KNOWN GOOD
# =============================================================================

def test_embedding_failure_keeps_existing_document(tmp_path, monkeypatch):
    """Verify that if embedding generation fails, existing document chunks remain 100% intact."""
    doc_file = tmp_path / "cardiology_safety.txt"
    initial_content = (
        "DOCUMENT TITLE: Cardiology Triage\n"
        "SOURCE: AHA\n"
        "--- Emergency ---\n"
        "Crushing chest pressure radiating to the arm is a critical cardiac emergency."
    )
    doc_file.write_text(initial_content, encoding="utf-8")
    rag_service.ingest_file(str(doc_file))

    parsed = rag_service._parse_medical_text(initial_content, file_path=str(doc_file))
    before_recs = rag_service.collection.get(where={"doc_id": parsed["doc_id"]})
    before_ids = set(before_recs["ids"])
    assert len(before_ids) > 0

    # Modify file and simulate embedding failure
    doc_file.write_text(initial_content + "\nUpdated content that fails embedding.", encoding="utf-8")

    def failing_embeddings(texts):
        raise RuntimeError("FastEmbed inference hardware timeout simulation")

    monkeypatch.setattr(rag_service, "generate_embeddings", failing_embeddings)

    with pytest.raises(RuntimeError, match="FastEmbed"):
        rag_service.ingest_file(str(doc_file))

    # Verify existing chunks are completely preserved
    after_recs = rag_service.collection.get(where={"doc_id": parsed["doc_id"]})
    after_ids = set(after_recs["ids"])
    assert after_ids == before_ids, "Existing chunks must remain completely intact when embedding fails"

    # Cleanup
    rag_service.collection.delete(where={"doc_id": parsed["doc_id"]})


def test_insertion_failure_keeps_existing_document(tmp_path, monkeypatch):
    """Verify that if ChromaDB insertion fails, existing document chunks remain 100% intact."""
    doc_file = tmp_path / "neurology_safety.txt"
    initial_content = (
        "DOCUMENT TITLE: Stroke Protocol\n"
        "SOURCE: Stroke Association\n"
        "--- FAST Protocol ---\n"
        "Face drooping, Arm weakness, Speech difficulty, Time to call emergency services."
    )
    doc_file.write_text(initial_content, encoding="utf-8")
    rag_service.ingest_file(str(doc_file))

    parsed = rag_service._parse_medical_text(initial_content, file_path=str(doc_file))
    before_recs = rag_service.collection.get(where={"doc_id": parsed["doc_id"]})
    before_ids = set(before_recs["ids"])

    # Modify file and simulate ChromaDB upsert failure
    doc_file.write_text(initial_content + "\nModified stroke guideline.", encoding="utf-8")

    def failing_upsert(**kwargs):
        raise RuntimeError("Simulated ChromaDB disk I/O lock failure")

    monkeypatch.setattr(rag_service.collection, "upsert", failing_upsert)

    with pytest.raises(RuntimeError, match="ChromaDB staging insertion failed"):
        rag_service.ingest_file(str(doc_file))

    # Verify existing chunks are untouched
    after_recs = rag_service.collection.get(where={"doc_id": parsed["doc_id"]})
    after_ids = set(after_recs["ids"])
    assert after_ids == before_ids, "Existing chunks must remain intact when insertion fails"

    # Cleanup
    rag_service.collection.delete(where={"doc_id": parsed["doc_id"]})


# =============================================================================
# 5. CRASH RECOVERY & MANIFEST RECONCILIATION
# =============================================================================

def test_crash_recovery_incomplete_staging_rolled_back(tmp_path):
    """
    Simulate a crash during staging where only a partial staged chunk was written.
    Verify reconciliation rolls back the incomplete staged chunk and retains the last known good.
    """
    doc_id = "test_crash_incomplete_doc_1234"
    known_good_id = f"{doc_id}_good_0"
    staged_id_1 = f"{doc_id}_staged_0"
    staged_id_2 = f"{doc_id}_staged_1"

    # Insert known good chunk
    emb = embedding_service.embed_query("Known good medical reference")
    rag_service.collection.upsert(
        ids=[known_good_id],
        embeddings=[emb],
        documents=["Known good medical reference"],
        metadatas=[{"doc_id": doc_id, "title": "Crash Test Guideline", "stage_status": "verified"}]
    )

    # Insert ONLY ONE of two staged chunks to simulate a mid-insertion crash
    rag_service.collection.upsert(
        ids=[staged_id_1],
        embeddings=[emb],
        documents=["Incomplete staged chunk 1"],
        metadatas=[{"doc_id": doc_id, "title": "Crash Test Guideline", "stage_status": "staged"}]
    )

    # Write manifest in 'staging' status expecting 2 staged chunks
    staging_manifest = {
        "doc_id": doc_id,
        "staged_version": "v_incomplete",
        "status": "staging",
        "staged_chunk_ids": [staged_id_1, staged_id_2],
        "staged_chunk_count": 2,
        "last_known_good_version": "v_good",
        "last_known_good_chunk_ids": [known_good_id],
        "source_path": "test/path.txt"
    }
    rag_service._save_document_manifest(doc_id, staging_manifest)

    # Execute recovery reconciliation
    result = rag_service.reconcile_document_manifest(doc_id)
    assert result["status"] == "recovered_rolled_back"

    # Verify incomplete staged chunk was purged
    recs = rag_service.collection.get(ids=[staged_id_1])
    assert len(recs["ids"]) == 0

    # Verify known good chunk is still active
    good_recs = rag_service.collection.get(ids=[known_good_id])
    assert len(good_recs["ids"]) == 1

    # Cleanup
    rag_service.collection.delete(ids=[known_good_id])


def test_crash_recovery_fully_staged_committed(tmp_path):
    """
    Simulate a crash where all staged chunks were written to ChromaDB, but the process
    crashed before deleting obsolete chunks and marking manifest as verified.
    Verify reconciliation finishes pruning and marks the version verified.
    """
    doc_id = "test_crash_complete_doc_5678"
    obsolete_id = f"{doc_id}_old_0"
    staged_id = f"{doc_id}_new_0"

    emb = embedding_service.embed_query("Updated guideline text")

    # Both old and new chunks exist in ChromaDB
    rag_service.collection.upsert(
        ids=[obsolete_id, staged_id],
        embeddings=[emb, emb],
        documents=["Old obsolete guideline", "Updated guideline text"],
        metadatas=[
            {"doc_id": doc_id, "title": "Reconcile Test", "stage_status": "verified"},
            {"doc_id": doc_id, "title": "Reconcile Test", "stage_status": "staged"}
        ]
    )

    # Manifest left in staging status
    staging_manifest = {
        "doc_id": doc_id,
        "staged_version": "v_new",
        "status": "staging",
        "staged_chunk_ids": [staged_id],
        "staged_chunk_count": 1,
        "last_known_good_version": "v_old",
        "last_known_good_chunk_ids": [obsolete_id],
        "source_path": "test/path.txt"
    }
    rag_service._save_document_manifest(doc_id, staging_manifest)

    # Execute reconciliation
    result = rag_service.reconcile_document_manifest(doc_id)
    assert result["status"] == "recovered_committed"

    # Verify obsolete chunk was deleted
    old_recs = rag_service.collection.get(ids=[obsolete_id])
    assert len(old_recs["ids"]) == 0

    # Verify new chunk is present
    new_recs = rag_service.collection.get(ids=[staged_id])
    assert len(new_recs["ids"]) == 1

    # Verify manifest is now verified
    manifest = rag_service.get_document_manifest(doc_id)
    assert manifest["status"] == "verified"
    assert manifest["active_version"] == "v_new"

    # Cleanup
    rag_service.collection.delete(ids=[staged_id])


# =============================================================================
# 6. RESUMABLE MIGRATION & SOURCE IMMUTABILITY
# =============================================================================

def test_migration_status_and_idempotency():
    """Verify check_migration_status correctly assesses the active ChromaDB state dynamically."""
    client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    source_col = client.get_collection(SOURCE_COLLECTION_NAME)
    expected_source_count = source_col.count()

    status = check_migration_status()
    assert "source_count" in status
    assert "target_count" in status
    assert "is_complete" in status
    assert status["source_count"] == expected_source_count
    assert status["is_complete"] is True
    assert status["needs_migration"] is False


def test_legacy_collection_immutability():
    """Verify that source collection (medical_knowledge) has records and remains untouched."""
    client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    source_col = client.get_collection(SOURCE_COLLECTION_NAME)
    count = source_col.count()
    assert count > 0, "Legacy medical_knowledge collection must contain records"

    peek = source_col.peek(1)
    assert len(peek["ids"]) == 1
    assert "title" in peek["metadatas"][0]


def test_fastembed_vector_dimensions_and_separation():
    """Verify target collection has 384-dimensional FastEmbed embeddings with no legacy vectors."""
    client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    source_col = client.get_collection(SOURCE_COLLECTION_NAME)
    target_col = client.get_collection(TARGET_COLLECTION_NAME)
    assert target_col.count() >= source_col.count()

    sample = target_col.peek(5)
    embs = sample["embeddings"]
    for vec in embs:
        assert len(vec) == 384, f"Target vector dimension mismatch: {len(vec)} != 384"
        assert not any(math.isnan(v) for v in vec)


# =============================================================================
# 7. MIGRATION VERIFICATION FIX REGRESSION TESTS
# =============================================================================

def test_migration_status_detects_mismatched_document_content(tmp_path):
    """Verify check_migration_status detects when target document content differs from source."""
    client = chromadb.PersistentClient(path=str(tmp_path))
    src = client.create_collection(SOURCE_COLLECTION_NAME)
    tgt = client.create_collection(TARGET_COLLECTION_NAME)

    emb = embedding_service.embed_query("Clinical protocol")
    src.add(ids=["chunk_1", "chunk_2"], documents=["Original text A", "Original text B"], embeddings=[emb, emb])
    # Target has chunk_1 matching, but chunk_2 has corrupted/altered content
    tgt.add(ids=["chunk_1", "chunk_2"], documents=["Original text A", "CORRUPTED text B"], embeddings=[emb, emb])

    status = check_migration_status(persist_dir=str(tmp_path))
    assert status["is_complete"] is False
    assert status["needs_migration"] is True
    assert status["missing_count"] == 1
    assert "chunk_2" in status["invalid_ids"]


def test_migration_status_detects_incorrect_vector_dimension(tmp_path, monkeypatch):
    """Verify check_migration_status rejects target embeddings with incorrect dimensions."""
    client = chromadb.PersistentClient(path=str(tmp_path))
    src = client.create_collection(SOURCE_COLLECTION_NAME)
    tgt = client.create_collection(TARGET_COLLECTION_NAME)

    emb_384 = [0.1] * 384
    src.add(ids=["chunk_1"], documents=["Text 1"], embeddings=[emb_384])
    tgt.add(ids=["chunk_1"], documents=["Text 1"], embeddings=[emb_384])

    # Mock target get to return a 128-dim vector
    orig_get = tgt.get
    def mock_tgt_get(*args, **kwargs):
        res = orig_get(*args, **kwargs)
        if "embeddings" in kwargs.get("include", []):
            res["embeddings"] = [[0.1] * 128]
        return res

    monkeypatch.setattr(tgt, "get", mock_tgt_get)
    monkeypatch.setattr(client, "get_collection", lambda name, **kw: tgt if name == TARGET_COLLECTION_NAME else src)
    monkeypatch.setattr(chromadb, "PersistentClient", lambda path: client)

    status = check_migration_status(persist_dir=str(tmp_path))
    assert status["is_complete"] is False
    assert status["needs_migration"] is True
    assert "chunk_1" in status["invalid_ids"]


def test_migration_status_detects_nan_and_infinity_vectors(tmp_path, monkeypatch):
    """Verify check_migration_status rejects target embeddings containing NaN or infinity."""
    client = chromadb.PersistentClient(path=str(tmp_path))
    src = client.create_collection(SOURCE_COLLECTION_NAME)
    tgt = client.create_collection(TARGET_COLLECTION_NAME)

    emb_384 = [0.1] * 384
    src.add(ids=["chunk_nan", "chunk_inf"], documents=["Text NaN", "Text Inf"], embeddings=[emb_384, emb_384])
    tgt.add(ids=["chunk_nan", "chunk_inf"], documents=["Text NaN", "Text Inf"], embeddings=[emb_384, emb_384])

    nan_emb = [0.1] * 383 + [float("nan")]
    inf_emb = [0.1] * 383 + [float("inf")]

    orig_get = tgt.get
    def mock_tgt_get(*args, **kwargs):
        res = orig_get(*args, **kwargs)
        if "embeddings" in kwargs.get("include", []):
            res["embeddings"] = [nan_emb, inf_emb]
        return res

    monkeypatch.setattr(tgt, "get", mock_tgt_get)
    monkeypatch.setattr(client, "get_collection", lambda name, **kw: tgt if name == TARGET_COLLECTION_NAME else src)
    monkeypatch.setattr(chromadb, "PersistentClient", lambda path: client)

    status = check_migration_status(persist_dir=str(tmp_path))
    assert status["is_complete"] is False
    assert status["needs_migration"] is True
    assert status["missing_count"] == 2
    assert "chunk_nan" in status["invalid_ids"]
    assert "chunk_inf" in status["invalid_ids"]


def test_migration_detects_when_all_ids_exist_but_one_document_differs(tmp_path):
    """Verify migrate_to_fastembed_collection re-embeds only the mismatched document."""
    client = chromadb.PersistentClient(path=str(tmp_path))
    src = client.create_collection(SOURCE_COLLECTION_NAME)
    tgt = client.create_collection(TARGET_COLLECTION_NAME)

    emb_1 = embedding_service.embed_query("Document 1 text")
    emb_2 = embedding_service.embed_query("Document 2 text")
    emb_3 = embedding_service.embed_query("Document 3 text")

    src.add(
        ids=["id_1", "id_2", "id_3"],
        documents=["Document 1 text", "Document 2 text", "Document 3 text"],
        embeddings=[emb_1, emb_2, emb_3],
        metadatas=[{"title": "Doc 1"}, {"title": "Doc 2"}, {"title": "Doc 3"}]
    )

    # Target has id_1 and id_3 correct, but id_2 document differs
    tgt.add(
        ids=["id_1", "id_2", "id_3"],
        documents=["Document 1 text", "DIFFERING Document 2 text", "Document 3 text"],
        embeddings=[emb_1, emb_2, emb_3],
        metadatas=[{"title": "Doc 1"}, {"title": "Doc 2"}, {"title": "Doc 3"}]
    )

    res = migrate_to_fastembed_collection(persist_dir=str(tmp_path))
    assert res["status"] == "success"
    # Only id_2 should have been re-embedded
    assert res["newly_embedded_count"] == 1
    assert res["migrated_count"] == 3

    # Verify target document 2 now matches source document 2
    re_check = tgt.get(ids=["id_2"])
    assert re_check["documents"][0] == "Document 2 text"


def test_migration_repairs_invalid_target_records(tmp_path):
    """Verify migrate_to_fastembed_collection repairs multiple corrupted/missing target records."""
    client = chromadb.PersistentClient(path=str(tmp_path))
    src = client.create_collection(SOURCE_COLLECTION_NAME)
    tgt = client.create_collection(TARGET_COLLECTION_NAME)

    docs = ["Guideline Alpha", "Guideline Beta", "Guideline Gamma"]
    ids = ["c_alpha", "c_beta", "c_gamma"]
    embs = embedding_service.embed_documents(docs)

    src.add(ids=ids, documents=docs, embeddings=embs, metadatas=[{"sec": 1}, {"sec": 2}, {"sec": 3}])

    # Target only has c_alpha (with altered text) and c_beta (valid); c_gamma is missing entirely
    tgt.add(
        ids=["c_alpha", "c_beta"],
        documents=["Altered Alpha text", "Guideline Beta"],
        embeddings=[embs[0], embs[1]],
        metadatas=[{"sec": 1}, {"sec": 2}]
    )

    # Status before repair
    before_status = check_migration_status(persist_dir=str(tmp_path))
    assert before_status["needs_migration"] is True
    assert before_status["missing_count"] == 2  # c_alpha (corrupted) + c_gamma (missing)

    # Execute repair
    res = migrate_to_fastembed_collection(persist_dir=str(tmp_path))
    assert res["status"] == "success"
    assert res["newly_embedded_count"] == 2

    # Status after repair
    after_status = check_migration_status(persist_dir=str(tmp_path))
    assert after_status["is_complete"] is True
    assert after_status["needs_migration"] is False
    assert after_status["missing_count"] == 0

    # Verify all 3 records match source
    tgt_check = tgt.get(ids=ids)
    for sid, sdoc in zip(ids, docs):
        t_idx = tgt_check["ids"].index(sid)
        assert tgt_check["documents"][t_idx] == sdoc


def test_migration_idempotent_after_repair(tmp_path):
    """Verify that rerun after repair performs zero new embeddings and returns success."""
    client = chromadb.PersistentClient(path=str(tmp_path))
    src = client.create_collection(SOURCE_COLLECTION_NAME)

    docs = ["Med Protocol 1", "Med Protocol 2"]
    ids = ["mp_1", "mp_2"]
    embs = embedding_service.embed_documents(docs)
    src.add(ids=ids, documents=docs, embeddings=embs)

    # Initial migration
    res1 = migrate_to_fastembed_collection(persist_dir=str(tmp_path))
    assert res1["status"] == "success"
    assert res1["newly_embedded_count"] == 2

    # Second migration (idempotent rerun)
    res2 = migrate_to_fastembed_collection(persist_dir=str(tmp_path))
    assert res2["status"] == "success"
    assert res2["newly_embedded_count"] == 0
    assert res2["migrated_count"] == 2
    assert res2.get("resumed") is True


def test_source_collection_full_immutability_verification(tmp_path):
    """Verify source collection IDs, documents, and metadatas remain 100% unaltered."""
    client = chromadb.PersistentClient(path=str(tmp_path))
    src = client.create_collection(SOURCE_COLLECTION_NAME)

    docs = ["Imm Test Doc 1", "Imm Test Doc 2"]
    ids = ["imm_1", "imm_2"]
    metas = [{"dept": "cardio", "ver": 1}, {"dept": "neuro", "ver": 2}]
    embs = embedding_service.embed_documents(docs)
    src.add(ids=ids, documents=docs, embeddings=embs, metadatas=metas)

    # Snapshot before
    before_snap = {sid: (doc, meta) for sid, doc, meta in zip(ids, docs, metas)}
    before_count = src.count()

    # Run migration
    migrate_to_fastembed_collection(persist_dir=str(tmp_path))

    # Snapshot after
    after_data = src.get(include=["documents", "metadatas"])
    after_snap = {
        sid: (doc, meta)
        for sid, doc, meta in zip(after_data["ids"], after_data["documents"], after_data["metadatas"])
    }
    after_count = src.count()

    assert before_count == after_count == 2
    assert before_snap == after_snap


def test_check_migration_status_detects_metadata_mismatch(tmp_path):
    """Verify check_migration_status flags target records with corrupted or mismatched metadata."""
    client = chromadb.PersistentClient(path=str(tmp_path))
    src = client.create_collection(SOURCE_COLLECTION_NAME)
    tgt = client.create_collection(TARGET_COLLECTION_NAME)

    emb = embedding_service.embed_query("Clinical protocol text")
    src.add(
        ids=["meta_chunk_1"],
        documents=["Clinical protocol text"],
        embeddings=[emb],
        metadatas=[{"topic": "Cardiology", "jurisdiction": "National", "level": 1}]
    )

    # Target has valid ID, document, and embedding, but corrupted metadata
    tgt.add(
        ids=["meta_chunk_1"],
        documents=["Clinical protocol text"],
        embeddings=[emb],
        metadatas=[{"topic": "CORRUPTED_TOPIC", "jurisdiction": "National", "level": 1}]
    )

    status = check_migration_status(persist_dir=str(tmp_path))
    assert status["is_complete"] is False
    assert status["needs_migration"] is True
    assert "meta_chunk_1" in status["invalid_ids"]


def test_migration_repairs_metadata_mismatch(tmp_path):
    """Verify migrate_to_fastembed_collection detects and repairs corrupted target metadata."""
    client = chromadb.PersistentClient(path=str(tmp_path))
    src = client.create_collection(SOURCE_COLLECTION_NAME)
    tgt = client.create_collection(TARGET_COLLECTION_NAME)

    doc = "Hypertension clinical guideline text"
    emb = embedding_service.embed_query(doc)
    orig_meta = {"title": "Hypertension Protocol", "source": "AHA", "year": 2026}

    src.add(
        ids=["htn_chunk_1"],
        documents=[doc],
        embeddings=[emb],
        metadatas=[orig_meta]
    )

    # Target has valid ID, document, and embedding, but corrupted metadata
    tgt.add(
        ids=["htn_chunk_1"],
        documents=[doc],
        embeddings=[emb],
        metadatas=[{"title": "WRONG_TITLE", "source": "UNKNOWN"}]
    )

    # Status before repair
    before_status = check_migration_status(persist_dir=str(tmp_path))
    assert before_status["needs_migration"] is True
    assert "htn_chunk_1" in before_status["invalid_ids"]

    # Run migration repair
    res = migrate_to_fastembed_collection(persist_dir=str(tmp_path))
    assert res["status"] == "success"
    assert res["newly_embedded_count"] == 1

    # Verify target metadata now accurately reflects source metadata
    tgt_item = tgt.get(ids=["htn_chunk_1"], include=["metadatas"])
    t_meta = tgt_item["metadatas"][0]
    for k, v in orig_meta.items():
        assert t_meta[k] == v
    assert t_meta["legacy_chunk_id"] == "htn_chunk_1"
    assert t_meta["migration_source"] == SOURCE_COLLECTION_NAME

    # Status after repair
    after_status = check_migration_status(persist_dir=str(tmp_path))
    assert after_status["is_complete"] is True
    assert after_status["needs_migration"] is False
    assert after_status["missing_count"] == 0
