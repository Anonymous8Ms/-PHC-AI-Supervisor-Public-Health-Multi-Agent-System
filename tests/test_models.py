from models import Alert, HealthWorker, Household, PHC, Visit


def test_demo_data_counts(db_session):
    assert db_session.query(PHC).count() == 3
    assert db_session.query(HealthWorker).count() == 12
    assert db_session.query(Household).count() == 40
    assert db_session.query(Visit).count() == 80
    assert db_session.query(Alert).count() >= 10


def test_model_relationships_are_wired(db_session):
    phc = db_session.query(PHC).first()

    assert phc is not None
    assert len(phc.health_workers) == 4
    assert len(phc.households) > 0
    assert phc.health_workers[0].visits is not None
