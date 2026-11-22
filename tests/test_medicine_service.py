"""
Automated Tests: Medicine Information Repository and Clinical Reference Lookup
"""
from fastapi import status


def test_search_medicine_by_generic_name(client, authenticated_patient):
    resp = client.get("/medications/search?q=Paracetamol", headers=authenticated_patient["headers"])
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total_found"] >= 1
    assert any("Paracetamol" in m["generic_name"] for m in data["results"])
    assert "disclaimer" in data


def test_search_medicine_by_brand_name(client, authenticated_patient):
    resp = client.get("/medications/search?q=Dolo", headers=authenticated_patient["headers"])
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total_found"] >= 1
    assert any("Dolo 650" in (m.get("brand_names") or "") for m in data["results"])


def test_get_medicine_detail_by_id(client, authenticated_patient):
    # First search to get an ID
    search_resp = client.get("/medications/search?q=Metformin", headers=authenticated_patient["headers"])
    assert search_resp.status_code == status.HTTP_200_OK
    med_id = search_resp.json()["results"][0]["id"]

    detail_resp = client.get(f"/medications/{med_id}", headers=authenticated_patient["headers"])
    assert detail_resp.status_code == status.HTTP_200_OK
    data = detail_resp.json()
    assert "Metformin" in data["generic_name"]
    assert "Lactic Acidosis" in data["serious_warnings"]
    assert data["source_reference"] is not None


def test_get_nonexistent_medicine_returns_404(client, authenticated_patient):
    resp = client.get("/medications/99999", headers=authenticated_patient["headers"])
    assert resp.status_code == status.HTTP_404_NOT_FOUND
