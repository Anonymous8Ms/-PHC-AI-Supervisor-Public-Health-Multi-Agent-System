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


def test_workers_endpoint_returns_seeded_workers(client):
    response = client.get("/api/workers")
    payload = response.get_json()

    assert response.status_code == 200
    assert len(payload) == 12
    assert {"id", "name", "zone", "visits_today", "status"} <= set(payload[0].keys())


def test_zones_endpoint_returns_zone_metrics(client):
    response = client.get("/api/zones")
    payload = response.get_json()

    assert response.status_code == 200
    assert len(payload) == 12
    assert {"zone", "risk_level", "visits_7d", "visits_14d", "visits_30d"} <= set(payload[0].keys())


def test_submit_visit_stores_pending_visit(client, db_session, monkeypatch):
    from agents import ingestion_agent
    from models import Household, Visit

    monkeypatch.setattr(
        ingestion_agent,
        "get_gemini_response",
        lambda *args, **kwargs: "Mild fever reported. Follow-up suggested.",
    )

    household = db_session.query(Household).first()
    worker = household.phc.health_workers[0]

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


def test_submit_visit_rejects_missing_fields(client):
    response = client.post(
        "/api/visit/submit",
        json={"worker_id": 1, "household_id": 1},
    )
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["code"] == "missing_fields"


def test_submit_visit_rejects_invalid_references(client):
    response = client.post(
        "/api/visit/submit",
        json={
            "worker_id": 9999,
            "household_id": 9999,
            "gps_lat": 20.0,
            "gps_lng": 81.0,
        },
    )
    payload = response.get_json()

    assert response.status_code == 404
    assert payload["code"] == "invalid_reference"


def test_submit_visit_rejects_invalid_visit_date(client, db_session):
    from models import Household

    household = db_session.query(Household).first()
    worker = household.phc.health_workers[0]

    response = client.post(
        "/api/visit/submit",
        json={
            "worker_id": worker.id,
            "household_id": household.id,
            "gps_lat": household.lat,
            "gps_lng": household.lng,
            "visit_date": "not-a-date",
        },
    )
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["code"] == "invalid_visit_date"


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


def test_verify_visit_returns_not_found_for_unknown_visit(client):
    response = client.post("/api/visit/999999/verify", json={})
    payload = response.get_json()

    assert response.status_code == 404
    assert payload["code"] == "visit_not_found"


def test_alerts_reject_invalid_resolved_filter(client):
    response = client.get("/api/alerts?resolved=maybe")
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["code"] == "invalid_query_parameter"


def test_resolve_alert_returns_not_found_for_unknown_id(client):
    response = client.post("/api/alerts/999999/resolve", json={})
    payload = response.get_json()

    assert response.status_code == 404
    assert payload["code"] == "alert_not_found"


def test_resolve_alert_marks_existing_alert_as_resolved(client, db_session):
    from models import Alert

    alert = db_session.query(Alert).filter(Alert.is_resolved.is_(False)).first()
    response = client.post(f"/api/alerts/{alert.id}/resolve", json={})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "resolved"


def test_predict_endpoint_returns_zone_list(client, monkeypatch):
    from agents import prediction_agent

    monkeypatch.setattr(
        prediction_agent,
        "get_gemini_response",
        lambda *args, **kwargs: {"error": "AI service temporarily unavailable"},
    )

    response = client.post("/api/predict", json={})
    payload = response.get_json()

    assert response.status_code == 200
    assert isinstance(payload, list)
    assert payload


def test_worker_detail_returns_not_found_for_unknown_worker(client):
    response = client.get("/api/workers/999999")
    payload = response.get_json()

    assert response.status_code == 404
    assert payload["code"] == "worker_not_found"


def test_chat_requires_query(client):
    response = client.post("/api/chat", json={"query": ""})
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["code"] == "missing_query"


def test_api_routes_require_json_for_posts(client):
    response = client.post(
        "/api/chat",
        data="query=hello",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["code"] == "invalid_json"
