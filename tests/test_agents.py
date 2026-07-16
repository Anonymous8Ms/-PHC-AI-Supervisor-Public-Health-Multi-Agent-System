def test_haversine_distance_zero():
    from agents.verification_agent import VerificationAgent

    assert VerificationAgent.haversine_distance(20.5, 81.5, 20.5, 81.5) == 0


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


def test_verification_agent_returns_not_found_for_unknown_visit(db_session):
    from agents.verification_agent import VerificationAgent

    result = VerificationAgent(session=db_session).execute(999999)
    assert result["code"] == "visit_not_found"
