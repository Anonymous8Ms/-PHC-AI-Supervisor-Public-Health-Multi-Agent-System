from datetime import datetime


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_dashboard_endpoint_returns_summary(client):
    response = client.get("/api/dashboard")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["total_workers"] == 12
    assert "zone_summary" in payload
    assert isinstance(payload["recent_alerts"], list)


def test_submit_visit_stores_pending_visit(client, db_session, monkeypatch):
    from agents import ingestion_agent
    from models import Household, Visit

    monkeypatch.setattr(
        ingestion_agent,
        "get_gemini_response",
        lambda *args, **kwargs: "Mild fever reported. Follow-up suggested.",
    )

    household = db_session.query(Household).first()
    worker = household.phc.workers[0]

    response = client.post(
        "/api/visit/submit",
        json={
            "worker_id": worker.id,
            "household_id": household.id,
            "gps_lat": household.lat,
            "gps_lng": household.lng,
            "photo_hash": "demo-photo-hash",
            "reported_symptoms": "Fever for two days",
            "visit_date": datetime.utcnow().isoformat(),
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "stored"

    stored_visit = db_session.get(Visit, payload["visit_id"])
    assert stored_visit is not None
    assert stored_visit.status == "pending"


def test_verify_visit_endpoint_returns_flagged_status(client, db_session, monkeypatch):
    from agents import verification_agent
    from models import Alert, Visit

    monkeypatch.setattr(
        verification_agent,
        "get_gemini_response",
        lambda *args, **kwargs: "GPS and timing patterns look suspicious.",
    )

    flagged_visit = (
        db_session.query(Visit)
        .filter(Visit.status.in_(["flagged", "fake"]))
        .order_by(Visit.visit_date.desc())
        .first()
    )
    flagged_visit.status = "pending"
    flagged_visit.verification_reason = None
    db_session.commit()

    response = client.post(f"/api/visit/{flagged_visit.id}/verify", json={})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] in {"flagged", "fake"}

    stored_alert = db_session.query(Alert).filter(Alert.visit_id == flagged_visit.id).first()
    assert stored_alert is not None
