"""Unit tests for demo data generation."""

from models import Alert, HealthWorker, Household, PHC, Visit


def test_demo_data_creates_phcs(db_session):
    assert db_session.query(PHC).count() == 3


def test_demo_data_phc_locations(db_session):
    phcs = db_session.query(PHC).all()
    states = {p.state for p in phcs}
    assert "Chhattisgarh" in states


def test_demo_data_creates_workers(db_session):
    assert db_session.query(HealthWorker).count() == 12


def test_demo_data_workers_have_phones(db_session):
    workers = db_session.query(HealthWorker).all()
    for worker in workers:
        assert worker.phone is not None
        assert worker.phone.startswith("+91")


def test_demo_data_creates_households(db_session):
    assert db_session.query(Household).count() == 40


def test_demo_data_households_have_zones(db_session):
    households = db_session.query(Household).all()
    for h in households:
        assert h.zone is not None
        assert len(h.zone) > 0


def test_demo_data_creates_visits(db_session):
    assert db_session.query(Visit).count() == 80


def test_demo_data_visits_have_valid_gps(db_session):
    visits = db_session.query(Visit).all()
    for v in visits:
        assert -90 <= v.gps_lat <= 90
        assert -180 <= v.gps_lng <= 180


def test_demo_data_visits_have_photo_hashes(db_session):
    visits = db_session.query(Visit).all()
    for v in visits:
        assert v.photo_hash is not None
        assert len(v.photo_hash) > 0


def test_demo_data_creates_alerts(db_session):
    assert db_session.query(Alert).count() >= 10


def test_demo_data_alerts_have_valid_severity(db_session):
    alerts = db_session.query(Alert).all()
    valid_severities = {"low", "medium", "high", "critical"}
    for alert in alerts:
        assert alert.severity in valid_severities


def test_demo_data_has_fake_visits(db_session):
    fake_visits = db_session.query(Visit).filter(Visit.status == "fake").count()
    assert fake_visits >= 1


def test_demo_data_has_flagged_visits(db_session):
    flagged_visits = db_session.query(Visit).filter(Visit.status == "flagged").count()
    assert flagged_visits >= 1


def test_demo_data_has_verified_visits(db_session):
    verified = db_session.query(Visit).filter(Visit.status == "verified").count()
    assert verified >= 1


def test_demo_data_household_risk_levels(db_session):
    risk_levels = {h.risk_level for h in db_session.query(Household).all()}
    assert risk_levels.issubset({"normal", "high", "critical"})


def test_demo_data_critical_zones_exist(db_session):
    critical = db_session.query(Household).filter(Household.risk_level == "critical").count()
    assert critical >= 1


def test_demo_data_alerts_resolved_status(db_session):
    alerts = db_session.query(Alert).all()
    resolved_count = sum(1 for a in alerts if a.is_resolved)
    unresolved_count = sum(1 for a in alerts if not a.is_resolved)
    assert resolved_count >= 1
    assert unresolved_count >= 1
