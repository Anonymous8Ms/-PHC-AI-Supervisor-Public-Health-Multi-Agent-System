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
