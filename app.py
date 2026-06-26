from datetime import datetime, timedelta

from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from sqlalchemy import case, func

from agents import IngestionAgent, PredictionAgent, SupervisorAgent, VerificationAgent
from config import FLASK_DEBUG, FLASK_PORT
from database import SessionLocal, init_db
from demo_data import generate_demo_data
from models import Alert, HealthWorker, Household, PHC, Visit


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})


def isoformat_or_none(value):
    return value.isoformat() if value else None


def serialize_visit(visit):
    return {
        "id": visit.id,
        "worker_id": visit.worker_id,
        "household_id": visit.household_id,
        "visit_date": isoformat_or_none(visit.visit_date),
        "gps_lat": visit.gps_lat,
        "gps_lng": visit.gps_lng,
        "photo_hash": visit.photo_hash,
        "reported_symptoms": visit.reported_symptoms,
        "status": visit.status,
        "verification_reason": visit.verification_reason,
        "created_at": isoformat_or_none(visit.created_at),
    }


def serialize_alert(alert):
    return {
        "id": alert.id,
        "visit_id": alert.visit_id,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "message": alert.message,
        "zone": alert.zone,
        "is_resolved": alert.is_resolved,
        "created_at": isoformat_or_none(alert.created_at),
    }


def ensure_demo_data():
    session = SessionLocal()
    try:
        has_workers = session.query(func.count(HealthWorker.id)).scalar() or 0
        if has_workers == 0:
            session.close()
            generate_demo_data()
            return
    finally:
        SessionLocal.remove()


@app.before_request
def require_json_for_posts():
    if request.method == "POST" and request.path.startswith("/api/"):
        if not request.is_json:
            return jsonify({"error": "Request body must be JSON"}), 400


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/<path:filename>")
def frontend_assets(filename):
    if filename.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    return send_from_directory(FRONTEND_DIR, filename)


@app.get("/api/dashboard")
def dashboard():
    session = SessionLocal()
    try:
        today = datetime.utcnow().date()
        seven_days_ago = datetime.utcnow() - timedelta(days=7)

        total_workers = session.query(func.count(HealthWorker.id)).scalar() or 0
        visits_today = session.query(func.count(Visit.id)).filter(
            func.date(Visit.visit_date) == today.isoformat()
        ).scalar() or 0
        flagged_visits = session.query(func.count(Visit.id)).filter(
            Visit.status.in_(["flagged", "fake"])
        ).scalar() or 0
        active_alerts = session.query(func.count(Alert.id)).filter(Alert.is_resolved.is_(False)).scalar() or 0
        critical_zones = session.query(func.count(func.distinct(Household.zone))).filter(
            Household.risk_level == "critical"
        ).scalar() or 0

        recent_alerts = (
            session.query(Alert)
            .order_by(
                case(
                    (Alert.severity == "critical", 0),
                    (Alert.severity == "high", 1),
                    (Alert.severity == "medium", 2),
                    else_=3,
                ),
                Alert.created_at.desc(),
            )
            .limit(8)
            .all()
        )

        zone_rows = session.query(Household.zone).distinct().order_by(Household.zone.asc()).all()
        zone_summary = []
        for (zone,) in zone_rows:
            visit_count = session.query(func.count(Visit.id)).join(Household, Visit.household_id == Household.id).filter(
                Household.zone == zone,
                Visit.visit_date >= seven_days_ago,
            ).scalar() or 0
            unvisited = session.query(func.count(Household.id)).filter(
                Household.zone == zone,
                ((Household.last_visit_date.is_(None)) | (Household.last_visit_date < datetime.utcnow() - timedelta(days=30))),
            ).scalar() or 0
            sample_household = session.query(Household).filter(Household.zone == zone).first()
            zone_summary.append(
                {
                    "zone": zone,
                    "risk_level": sample_household.risk_level if sample_household else "normal",
                    "visits_last_7d": int(visit_count),
                    "unvisited_households": int(unvisited),
                    "lat": sample_household.lat if sample_household else None,
                    "lng": sample_household.lng if sample_household else None,
                }
            )

        return jsonify(
            {
                "total_workers": total_workers,
                "visits_today": visits_today,
                "flagged_visits": flagged_visits,
                "active_alerts": active_alerts,
                "critical_zones": critical_zones,
                "recent_alerts": [serialize_alert(alert) for alert in recent_alerts],
                "zone_summary": zone_summary,
            }
        )
    finally:
        session.close()
        SessionLocal.remove()


@app.get("/api/alerts")
def list_alerts():
    session = SessionLocal()
    try:
        resolved = request.args.get("resolved")
        query = session.query(Alert)
        if resolved is not None:
            query = query.filter(Alert.is_resolved.is_(resolved.lower() == "true"))
        alerts = query.order_by(
            case(
                (Alert.severity == "critical", 0),
                (Alert.severity == "high", 1),
                (Alert.severity == "medium", 2),
                else_=3,
            ),
            Alert.created_at.desc(),
        ).all()
        return jsonify([serialize_alert(alert) for alert in alerts])
    finally:
        session.close()
        SessionLocal.remove()


@app.post("/api/alerts/<int:alert_id>/resolve")
def resolve_alert(alert_id):
    session = SessionLocal()
    try:
        alert = session.get(Alert, alert_id)
        if not alert:
            return jsonify({"error": "Alert not found"}), 404
        alert.is_resolved = True
        session.commit()
        return jsonify({"status": "resolved", "alert": serialize_alert(alert)})
    finally:
        session.close()
        SessionLocal.remove()


@app.post("/api/visit/submit")
def submit_visit():
    payload = request.get_json(silent=True) or {}
    result = IngestionAgent().execute(payload)
    status_code = 400 if "error" in result else 200
    return jsonify(result), status_code


@app.post("/api/visit/<int:visit_id>/verify")
def verify_visit(visit_id):
    result = VerificationAgent().execute(visit_id)
    status_code = 404 if result.get("error") == "Visit not found" else 200
    return jsonify(result), status_code


@app.post("/api/predict")
def predict_zones():
    result = PredictionAgent().execute()
    return jsonify(result)


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    query = payload.get("query", "").strip()
    language = payload.get("language", "english")
    if not query:
        return jsonify({"error": "Query is required"}), 400
    result = SupervisorAgent().execute(query=query, language=language)
    return jsonify(result)


@app.get("/api/workers")
def list_workers():
    session = SessionLocal()
    try:
        today = datetime.utcnow().date()
        workers = session.query(HealthWorker).order_by(HealthWorker.name.asc()).all()
        payload = []
        for worker in workers:
            visits_today = session.query(func.count(Visit.id)).filter(
                Visit.worker_id == worker.id,
                func.date(Visit.visit_date) == today.isoformat(),
            ).scalar() or 0
            last_visit = (
                session.query(Visit)
                .filter(Visit.worker_id == worker.id)
                .order_by(Visit.visit_date.desc())
                .first()
            )
            payload.append(
                {
                    "id": worker.id,
                    "name": worker.name,
                    "phone": worker.phone,
                    "zone": worker.zone,
                    "language": worker.language,
                    "phc_id": worker.phc_id,
                    "visits_today": int(visits_today),
                    "total_visits": len(worker.visits),
                    "status": "active" if visits_today > 0 else "inactive",
                    "last_visit": isoformat_or_none(last_visit.visit_date if last_visit else None),
                    "created_at": isoformat_or_none(worker.created_at),
                }
            )
        return jsonify(payload)
    finally:
        session.close()
        SessionLocal.remove()


@app.get("/api/workers/<int:worker_id>")
def worker_detail(worker_id):
    session = SessionLocal()
    try:
        worker = session.get(HealthWorker, worker_id)
        if not worker:
            return jsonify({"error": "Worker not found"}), 404
        visits = (
            session.query(Visit)
            .filter(Visit.worker_id == worker_id)
            .order_by(Visit.visit_date.desc())
            .limit(10)
            .all()
        )
        return jsonify(
            {
                "id": worker.id,
                "name": worker.name,
                "phone": worker.phone,
                "zone": worker.zone,
                "language": worker.language,
                "phc_id": worker.phc_id,
                "created_at": isoformat_or_none(worker.created_at),
                "last_10_visits": [serialize_visit(visit) for visit in visits],
            }
        )
    finally:
        session.close()
        SessionLocal.remove()


@app.get("/api/zones")
def list_zones():
    session = SessionLocal()
    try:
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        fourteen_days_ago = datetime.utcnow() - timedelta(days=14)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        zones = session.query(Household.zone).distinct().order_by(Household.zone.asc()).all()
        payload = []
        for (zone,) in zones:
            households = session.query(Household).filter(Household.zone == zone).all()
            household_ids = [household.id for household in households]
            visits_7d = session.query(func.count(Visit.id)).filter(
                Visit.household_id.in_(household_ids),
                Visit.visit_date >= seven_days_ago,
            ).scalar() or 0
            visits_14d = session.query(func.count(Visit.id)).filter(
                Visit.household_id.in_(household_ids),
                Visit.visit_date >= fourteen_days_ago,
            ).scalar() or 0
            visits_30d = session.query(func.count(Visit.id)).filter(
                Visit.household_id.in_(household_ids),
                Visit.visit_date >= thirty_days_ago,
            ).scalar() or 0
            unvisited = session.query(func.count(Household.id)).filter(
                Household.zone == zone,
                ((Household.last_visit_date.is_(None)) | (Household.last_visit_date < thirty_days_ago)),
            ).scalar() or 0
            sample = households[0] if households else None
            payload.append(
                {
                    "zone": zone,
                    "risk_level": sample.risk_level if sample else "normal",
                    "phc_id": sample.phc_id if sample else None,
                    "lat": sample.lat if sample else None,
                    "lng": sample.lng if sample else None,
                    "visits_7d": int(visits_7d),
                    "visits_14d": int(visits_14d),
                    "visits_30d": int(visits_30d),
                    "unvisited_households": int(unvisited),
                    "household_count": len(households),
                }
            )
        return jsonify(payload)
    finally:
        session.close()
        SessionLocal.remove()


@app.post("/api/demo/reset")
def reset_demo():
    generate_demo_data()
    return jsonify({"status": "reset", "message": "Demo data regenerated."})


def bootstrap():
    init_db()
    ensure_demo_data()


bootstrap()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=FLASK_DEBUG)
