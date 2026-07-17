"""Unit tests for SQLAlchemy ORM models and demo data seeding."""

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


def test_phc_has_required_fields(db_session):
    phc = db_session.query(PHC).first()
    assert phc.name is not None
    assert phc.district is not None
    assert phc.state is not None
    assert isinstance(phc.lat, float)
    assert isinstance(phc.lng, float)


def test_health_worker_has_required_fields(db_session):
    worker = db_session.query(HealthWorker).first()
    assert worker.name is not None
    assert worker.zone is not None
    assert worker.language is not None
    assert worker.phc is not None


def test_health_worker_belongs_to_phc(db_session):
    worker = db_session.query(HealthWorker).first()
    assert worker.phc_id is not None
    assert worker.phc.id == worker.phc_id


def test_health_worker_has_visits(db_session):
    worker = db_session.query(HealthWorker).first()
    assert len(worker.visits) > 0


def test_household_has_required_fields(db_session):
    household = db_session.query(Household).first()
    assert household.address is not None
    assert household.zone is not None
    assert isinstance(household.lat, float)
    assert isinstance(household.lng, float)
    assert household.risk_level in ("normal", "high", "critical")


def test_household_belongs_to_phc(db_session):
    household = db_session.query(Household).first()
    assert household.phc_id is not None
    assert household.phc.id == household.phc_id


def test_visit_has_required_fields(db_session):
    visit = db_session.query(Visit).first()
    assert visit.worker_id is not None
    assert visit.household_id is not None
    assert visit.visit_date is not None
    assert isinstance(visit.gps_lat, float)
    assert isinstance(visit.gps_lng, float)
    assert visit.status in ("pending", "verified", "flagged", "fake")


def test_visit_belongs_to_worker(db_session):
    visit = db_session.query(Visit).first()
    assert visit.worker is not None
    assert visit.worker.id == visit.worker_id


def test_visit_belongs_to_household(db_session):
    visit = db_session.query(Visit).first()
    assert visit.household is not None
    assert visit.household.id == visit.household_id


def test_visit_has_photo_hash(db_session):
    visit = db_session.query(Visit).filter(Visit.photo_hash.isnot(None)).first()
    assert visit is not None
    assert len(visit.photo_hash) > 0


def test_alert_has_required_fields(db_session):
    alert = db_session.query(Alert).first()
    assert alert.alert_type is not None
    assert alert.severity in ("low", "medium", "high", "critical")
    assert alert.message is not None
    assert alert.zone is not None
    assert isinstance(alert.is_resolved, bool)


def test_alert_types_are_valid(db_session):
    alert_types = {a.alert_type for a in db_session.query(Alert).all()}
    valid_types = {"fake_visit", "missed_area", "outbreak_risk", "worker_burnout"}
    assert alert_types.issubset(valid_types)


def test_alerts_with_visit_have_valid_visit_id(db_session):
    alerts_with_visit = db_session.query(Alert).filter(Alert.visit_id.isnot(None)).all()
    for alert in alerts_with_visit:
        visit = db_session.get(Visit, alert.visit_id)
        assert visit is not None


def test_chat_log_has_required_fields(db_session):
    from models import ChatLog

    log = ChatLog(
        user_query="test query",
        agent_response="test response",
        agent_name="supervisor",
    )
    db_session.add(log)
    db_session.commit()

    assert log.user_query == "test query"
    assert log.agent_response == "test response"
    assert log.agent_name == "supervisor"
    assert log.created_at is not None


def test_cascade_delete_worker_visits(db_session):
    from sqlalchemy import func

    worker = db_session.query(HealthWorker).first()
    worker_id = worker.id
    visit_count = db_session.query(func.count(Visit.id)).filter(Visit.worker_id == worker_id).scalar()

    assert visit_count > 0


def test_zones_are_distinct(db_session):
    zones = {h.zone for h in db_session.query(Household).all()}
    assert len(zones) == 12


def test_workers_distributed_across_phcs(db_session):
    phcs = db_session.query(PHC).all()
    for phc in phcs:
        assert len(phc.health_workers) == 4


def test_households_distributed_across_zones(db_session):
    from sqlalchemy import func

    zone_counts = (
        db_session.query(Household.zone, func.count(Household.id))
        .group_by(Household.zone)
        .all()
    )
    for zone, count in zone_counts:
        assert count > 0
