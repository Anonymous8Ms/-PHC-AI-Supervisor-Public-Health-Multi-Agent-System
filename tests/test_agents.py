"""Unit tests for multi-agent logic (ingestion, verification, prediction, supervisor)."""

from datetime import datetime

import pytest


def test_haversine_distance_zero():
    from agents.verification_agent import VerificationAgent

    assert VerificationAgent.haversine_distance(20.5, 81.5, 20.5, 81.5) == 0


def test_haversine_distance_known_points():
    from agents.verification_agent import VerificationAgent

    dist = VerificationAgent.haversine_distance(28.6139, 77.2090, 28.6200, 77.2150)
    assert 500 < dist < 1500


def test_haversine_distance_symmetric():
    from agents.verification_agent import VerificationAgent

    d1 = VerificationAgent.haversine_distance(20.0, 81.0, 21.0, 82.0)
    d2 = VerificationAgent.haversine_distance(21.0, 82.0, 20.0, 81.0)
    assert abs(d1 - d2) < 0.001


def test_prediction_agent_returns_fallback_predictions(db_session, monkeypatch):
    from agents import prediction_agent
    from agents.prediction_agent import PredictionAgent

    monkeypatch.setattr(
        prediction_agent,
        "get_gemini_response",
        lambda *args, **kwargs: {"error": "AI service temporarily unavailable"},
    )

    result = PredictionAgent(session=db_session).execute()
    assert isinstance(result, list)
    assert result
    assert {"zone", "risk_level", "reason", "recommended_action"} <= set(result[0].keys())


def test_prediction_agent_fallback_marks_critical_zones(db_session, monkeypatch):
    from agents import prediction_agent
    from agents.prediction_agent import PredictionAgent

    monkeypatch.setattr(
        prediction_agent,
        "get_gemini_response",
        lambda *args, **kwargs: {"error": "unavailable"},
    )

    predictions = PredictionAgent(session=db_session).execute()
    critical_or_high = [p for p in predictions if p["risk_level"] in ("critical", "high")]
    assert len(critical_or_high) >= 1


def test_prediction_agent_updates_household_risk_levels(db_session, monkeypatch):
    from agents import prediction_agent
    from agents.prediction_agent import PredictionAgent
    from models import Household

    monkeypatch.setattr(
        prediction_agent,
        "get_gemini_response",
        lambda *args, **kwargs: {"error": "unavailable"},
    )

    PredictionAgent(session=db_session).execute()
    db_session.expire_all()
    zones_with_risk = (
        db_session.query(Household.zone, Household.risk_level)
        .distinct()
        .all()
    )
    risk_levels = {rl for _, rl in zones_with_risk}
    assert risk_levels.issubset({"normal", "high", "critical"})


def test_supervisor_agent_redirects_off_topic_queries(db_session):
    from agents.supervisor_agent import SupervisorAgent

    result = SupervisorAgent(session=db_session).execute(
        query="Write me a movie review",
        language="english",
    )
    assert result["agent"] == "supervisor"
    assert "outside my trained dashboard scope" in result["response"].lower()


def test_supervisor_agent_handles_greeting_without_gemini(db_session):
    from agents.supervisor_agent import SupervisorAgent

    result = SupervisorAgent(session=db_session).execute(
        query="hi",
        language="english",
    )
    assert result["agent"] == "supervisor"
    assert "supervisor agent" in result["response"].lower()


def test_supervisor_agent_handles_hindi_greeting(db_session):
    from agents.supervisor_agent import SupervisorAgent

    result = SupervisorAgent(session=db_session).execute(
        query="namaste",
        language="hindi",
    )
    assert result["agent"] == "supervisor"
    assert "namaste" in result["response"].lower()


def test_supervisor_agent_role_question(db_session):
    from agents.supervisor_agent import SupervisorAgent

    result = SupervisorAgent(session=db_session).execute(
        query="who are you",
        language="english",
    )
    assert "supervisor" in result["response"].lower() or "monitor" in result["response"].lower()


def test_supervisor_agent_flagged_worker_query(db_session):
    from agents.supervisor_agent import SupervisorAgent

    result = SupervisorAgent(session=db_session).execute(
        query="which worker has flagged visits",
        language="english",
    )
    assert result["agent"] == "supervisor"
    assert isinstance(result["response"], str)


def test_supervisor_agent_critical_zone_query(db_session):
    from agents.supervisor_agent import SupervisorAgent

    result = SupervisorAgent(session=db_session).execute(
        query="which zones are critical",
        language="english",
    )
    assert result["agent"] == "supervisor"
    assert isinstance(result["response"], str)


def test_supervisor_agent_alert_query(db_session):
    from agents.supervisor_agent import SupervisorAgent

    result = SupervisorAgent(session=db_session).execute(
        query="show me active alerts",
        language="english",
    )
    assert result["agent"] == "supervisor"


def test_supervisor_agent_logs_chat(db_session):
    from agents.supervisor_agent import SupervisorAgent
    from models import ChatLog

    before_count = db_session.query(ChatLog).count()
    SupervisorAgent(session=db_session).execute(query="hello", language="english")
    after_count = db_session.query(ChatLog).count()
    assert after_count == before_count + 1


def test_ingestion_agent_rejects_invalid_coordinates(db_session):
    from agents.ingestion_agent import IngestionAgent
    from models import Household

    household = db_session.query(Household).first()
    worker = household.phc.health_workers[0]

    result = IngestionAgent(session=db_session).execute(
        {
            "worker_id": worker.id,
            "household_id": household.id,
            "gps_lat": "bad-latitude",
            "gps_lng": household.lng,
        }
    )
    assert result["code"] == "invalid_coordinates"


def test_ingestion_agent_rejects_missing_fields(db_session):
    from agents.ingestion_agent import IngestionAgent

    result = IngestionAgent(session=db_session).execute({})
    assert result["code"] == "missing_fields"
    assert set(result["details"]["fields"]) == {"worker_id", "household_id", "gps_lat", "gps_lng"}


def test_ingestion_agent_rejects_invalid_worker(db_session):
    from agents.ingestion_agent import IngestionAgent
    from models import Household

    household = db_session.query(Household).first()
    result = IngestionAgent(session=db_session).execute(
        {
            "worker_id": 99999,
            "household_id": household.id,
            "gps_lat": household.lat,
            "gps_lng": household.lng,
        }
    )
    assert result["code"] == "invalid_reference"


def test_ingestion_agent_rejects_invalid_household(db_session):
    from agents.ingestion_agent import IngestionAgent
    from models import HealthWorker

    worker = db_session.query(HealthWorker).first()
    result = IngestionAgent(session=db_session).execute(
        {
            "worker_id": worker.id,
            "household_id": 99999,
            "gps_lat": 20.0,
            "gps_lng": 81.0,
        }
    )
    assert result["code"] == "invalid_reference"


def test_ingestion_agent_rejects_invalid_date(db_session):
    from agents.ingestion_agent import IngestionAgent
    from models import Household

    household = db_session.query(Household).first()
    worker = household.phc.health_workers[0]

    result = IngestionAgent(session=db_session).execute(
        {
            "worker_id": worker.id,
            "household_id": household.id,
            "gps_lat": household.lat,
            "gps_lng": household.lng,
            "visit_date": "not-a-date",
        }
    )
    assert result["code"] == "invalid_visit_date"


def test_ingestion_agent_stores_visit_successfully(db_session, monkeypatch):
    from agents import ingestion_agent
    from agents.ingestion_agent import IngestionAgent
    from models import Household, Visit

    monkeypatch.setattr(
        ingestion_agent,
        "get_gemini_response",
        lambda *args, **kwargs: "Mild fever noted.",
    )

    household = db_session.query(Household).first()
    worker = household.phc.health_workers[0]

    result = IngestionAgent(session=db_session).execute(
        {
            "worker_id": worker.id,
            "household_id": household.id,
            "gps_lat": household.lat,
            "gps_lng": household.lng,
            "photo_hash": "test-hash",
            "reported_symptoms": "Fever and cough",
            "visit_date": datetime.utcnow().isoformat(),
        }
    )
    assert result["status"] == "stored"
    visit = db_session.get(Visit, result["visit_id"])
    assert visit.status == "pending"
    assert visit.reported_symptoms == "Fever and cough"


def test_ingestion_agent_stores_no_symptoms_visit(db_session):
    from agents.ingestion_agent import IngestionAgent
    from models import Household

    household = db_session.query(Household).first()
    worker = household.phc.health_workers[0]

    result = IngestionAgent(session=db_session).execute(
        {
            "worker_id": worker.id,
            "household_id": household.id,
            "gps_lat": household.lat,
            "gps_lng": household.lng,
        }
    )
    assert result["status"] == "stored"
    assert "No symptoms" in result["summary"]


def test_ingestion_agent_updates_household_last_visit(db_session):
    from agents.ingestion_agent import IngestionAgent
    from models import Household

    household = db_session.query(Household).first()
    worker = household.phc.health_workers[0]

    IngestionAgent(session=db_session).execute(
        {
            "worker_id": worker.id,
            "household_id": household.id,
            "gps_lat": household.lat,
            "gps_lng": household.lng,
        }
    )
    db_session.expire(household)
    assert household.last_visit_date is not None


def test_verification_agent_returns_not_found_for_unknown_visit(db_session):
    from agents.verification_agent import VerificationAgent

    result = VerificationAgent(session=db_session).execute(999999)
    assert result["code"] == "visit_not_found"


def test_verification_agent_verifies_valid_visit(db_session, monkeypatch):
    from agents import verification_agent
    from agents.verification_agent import VerificationAgent
    from models import Visit

    monkeypatch.setattr(
        verification_agent,
        "get_gemini_response",
        lambda *args, **kwargs: "Visit looks legitimate.",
    )

    visit = db_session.query(Visit).filter(Visit.status == "pending").first()
    if not visit:
        pytest.skip("No pending visits in demo data")

    result = VerificationAgent(session=db_session).execute(visit.id)
    assert result["status"] in ("verified", "flagged", "fake")
    assert "distance_m" in result


def test_verification_agent_flags_far_visit(db_session, monkeypatch):
    from agents import verification_agent
    from agents.verification_agent import VerificationAgent
    from models import Visit

    monkeypatch.setattr(
        verification_agent,
        "get_gemini_response",
        lambda *args, **kwargs: "GPS anomaly detected.",
    )

    visit = db_session.query(Visit).filter(Visit.status == "fake").first()
    if not visit:
        pytest.skip("No fake visits in demo data")

    result = VerificationAgent(session=db_session).execute(visit.id)
    assert result["status"] == "fake"
    assert result["distance_m"] > 500


def test_verification_agent_creates_alert_for_fake_visit(db_session, monkeypatch):
    from agents import verification_agent
    from agents.verification_agent import VerificationAgent
    from models import Alert, Visit

    monkeypatch.setattr(
        verification_agent,
        "get_gemini_response",
        lambda *args, **kwargs: "Suspicious patterns detected.",
    )

    visit = db_session.query(Visit).filter(Visit.status == "fake").first()
    if not visit:
        pytest.skip("No fake visits")

    db_session.query(Alert).filter(Alert.visit_id == visit.id).delete()
    db_session.commit()

    VerificationAgent(session=db_session).execute(visit.id)
    alert = db_session.query(Alert).filter(Alert.visit_id == visit.id).first()
    assert alert is not None
    assert alert.alert_type == "fake_visit"
