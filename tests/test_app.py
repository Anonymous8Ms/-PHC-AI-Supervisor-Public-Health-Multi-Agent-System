"""Integration tests for Flask API endpoints."""

from datetime import datetime

import pytest


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_health_endpoint_returns_database_type(client):
    response = client.get("/api/health")
    payload = response.get_json()
    assert "database" in payload
    assert payload["database"] in ("sqlite", "postgresql")


def test_dashboard_endpoint_returns_summary(client):
    response = client.get("/api/dashboard")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["total_workers"] == 12
    assert "zone_summary" in payload
    assert isinstance(payload["recent_alerts"], list)


def test_dashboard_returns_required_fields(client):
    response = client.get("/api/dashboard")
    payload = response.get_json()

    required_fields = [
        "total_workers", "visits_today", "flagged_visits",
        "active_alerts", "critical_zones", "recent_alerts", "zone_summary",
    ]
    for field in required_fields:
        assert field in payload, f"Missing field: {field}"


def test_dashboard_zone_summary_structure(client):
    response = client.get("/api/dashboard")
    payload = response.get_json()

    zone_summary = payload["zone_summary"]
    assert isinstance(zone_summary, list)
    if zone_summary:
        zone = zone_summary[0]
        assert {"zone", "risk_level", "visits_last_7d", "unvisited_households"}.issubset(zone.keys())


def test_workers_endpoint_returns_seeded_workers(client):
    response = client.get("/api/workers")
    payload = response.get_json()

    assert response.status_code == 200
    assert len(payload) == 12
    assert {"id", "name", "zone", "visits_today", "status"} <= set(payload[0].keys())


def test_workers_endpoint_sorted_by_name(client):
    response = client.get("/api/workers")
    payload = response.get_json()
    names = [w["name"] for w in payload]
    assert names == sorted(names)


def test_worker_detail_returns_worker_info(client, db_session):
    from models import HealthWorker

    worker = db_session.query(HealthWorker).first()
    response = client.get(f"/api/workers/{worker.id}")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["name"] == worker.name
    assert payload["zone"] == worker.zone
    assert "last_10_visits" in payload


def test_worker_detail_returns_not_found_for_unknown_worker(client):
    response = client.get("/api/workers/999999")
    payload = response.get_json()

    assert response.status_code == 404
    assert payload["code"] == "worker_not_found"


def test_zones_endpoint_returns_zone_metrics(client):
    response = client.get("/api/zones")
    payload = response.get_json()

    assert response.status_code == 200
    assert len(payload) == 12
    assert {"zone", "risk_level", "visits_7d", "visits_14d", "visits_30d"} <= set(payload[0].keys())


def test_zones_endpoint_includes_household_count(client):
    response = client.get("/api/zones")
    payload = response.get_json()
    assert "household_count" in payload[0]


def test_zones_endpoint_includes_unvisited_count(client):
    response = client.get("/api/zones")
    payload = response.get_json()
    assert "unvisited_households" in payload[0]


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


def test_verify_visit_includes_distance(client, db_session, monkeypatch):
    from agents import verification_agent

    monkeypatch.setattr(
        verification_agent,
        "get_gemini_response",
        lambda *args, **kwargs: "Analysis complete.",
    )

    from models import Visit
    visit = db_session.query(Visit).filter(Visit.status == "pending").first()
    if not visit:
        pytest.skip("No pending visits")

    response = client.post(f"/api/visit/{visit.id}/verify", json={})
    payload = response.get_json()
    assert "distance_m" in payload
    assert isinstance(payload["distance_m"], (int, float))


def test_alerts_endpoint_returns_all_alerts(client):
    response = client.get("/api/alerts")
    payload = response.get_json()

    assert response.status_code == 200
    assert isinstance(payload, list)
    assert len(payload) >= 10


def test_alerts_endpoint_filters_resolved(client):
    response = client.get("/api/alerts?resolved=false")
    payload = response.get_json()
    assert response.status_code == 200
    for alert in payload:
        assert alert["is_resolved"] is False


def test_alerts_endpoint_filters_unresolved(client):
    response = client.get("/api/alerts?resolved=true")
    payload = response.get_json()
    assert response.status_code == 200
    for alert in payload:
        assert alert["is_resolved"] is True


def test_alerts_reject_invalid_resolved_filter(client):
    response = client.get("/api/alerts?resolved=maybe")
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["code"] == "invalid_query_parameter"


def test_alerts_ordered_by_severity(client):
    response = client.get("/api/alerts")
    payload = response.get_json()
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    severities = [severity_order.get(a["severity"], 4) for a in payload]
    assert severities == sorted(severities)


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


def test_resolve_alert_persists_in_database(client, db_session):
    from models import Alert

    alert = db_session.query(Alert).filter(Alert.is_resolved.is_(False)).first()
    alert_id = alert.id
    client.post(f"/api/alerts/{alert_id}/resolve", json={})
    db_session.expire_all()
    refreshed_alert = db_session.get(Alert, alert_id)
    assert refreshed_alert.is_resolved is True


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


def test_predict_endpoint_predictions_have_required_fields(client, monkeypatch):
    from agents import prediction_agent

    monkeypatch.setattr(
        prediction_agent,
        "get_gemini_response",
        lambda *args, **kwargs: {"error": "unavailable"},
    )

    response = client.post("/api/predict", json={})
    payload = response.get_json()

    for prediction in payload:
        assert {"zone", "risk_level", "reason", "recommended_action"}.issubset(prediction.keys())


def test_chat_requires_query(client):
    response = client.post("/api/chat", json={"query": ""})
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["code"] == "missing_query"


def test_chat_handles_valid_query(client):
    response = client.post("/api/chat", json={"query": "hello"})
    payload = response.get_json()

    assert response.status_code == 200
    assert "response" in payload
    assert payload["agent"] == "supervisor"


def test_chat_handles_hindi_query(client):
    response = client.post("/api/chat", json={"query": "namaste", "language": "hindi"})
    payload = response.get_json()

    assert response.status_code == 200
    assert "response" in payload


def test_chat_rejects_off_topic_query(client):
    response = client.post("/api/chat", json={"query": "what is the weather on mars"})
    payload = response.get_json()

    assert response.status_code == 200
    assert "outside" in payload["response"].lower() or "scope" in payload["response"].lower()


def test_api_routes_require_json_for_posts(client):
    response = client.post(
        "/api/chat",
        data="query=hello",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["code"] == "invalid_json"


def test_404_handler_returns_json_for_api(client):
    response = client.get("/api/nonexistent")
    payload = response.get_json()

    assert response.status_code == 404
    assert "error" in payload


def test_demo_reset_endpoint(client):
    response = client.post("/api/demo/reset", json={})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "reset"


def test_demo_reset_repopulates_data(client):
    client.post("/api/demo/reset")
    response = client.get("/api/dashboard")
    payload = response.get_json()
    assert payload["total_workers"] == 12


def test_frontend_index(client):
    response = client.get("/")
    assert response.status_code == 200


def test_alerts_have_required_fields(client):
    response = client.get("/api/alerts")
    payload = response.get_json()

    for alert in payload:
        assert {"id", "alert_type", "severity", "message", "zone", "is_resolved"}.issubset(alert.keys())
