import hashlib
import random
from datetime import datetime, timedelta, time

from database import Base, SessionLocal, engine, init_db
from models import Alert, HealthWorker, Household, PHC, Visit


random.seed(42)


PHC_DATA = [
    {"name": "PHC Kurud", "district": "Dhamtari", "state": "Chhattisgarh", "lat": 20.8310, "lng": 81.7198},
    {"name": "PHC Jagdalpur", "district": "Bastar", "state": "Chhattisgarh", "lat": 19.0748, "lng": 82.0315},
    {"name": "PHC Dhamtari", "district": "Dhamtari", "state": "Chhattisgarh", "lat": 20.7074, "lng": 81.5487},
]

WORKER_NAMES = [
    "Lata Bai",
    "Sunita Devi",
    "Premchand",
    "Rukmini Sahu",
    "Kiran Netam",
    "Mohan Lal",
    "Sushila Mandavi",
    "Devendra Rao",
    "Meena Patel",
    "Ramesh Yadav",
    "Anita Kumari",
    "Bhola Nishad",
]

ZONES = [
    "Kurud North",
    "Kurud South",
    "Kurud River Belt",
    "Kurud Forest Edge",
    "Jagdalpur Central",
    "Jagdalpur East",
    "Jagdalpur Tribal Hamlet",
    "Jagdalpur Market Line",
    "Dhamtari Lake View",
    "Dhamtari West",
    "Dhamtari Canal Road",
    "Dhamtari Upland",
]

SYMPTOMS = [
    "Mild fever and cough reported for two family members. Advised hydration and revisit in two days.",
    "Pregnant woman reported dizziness and swelling. Recommended PHC referral and blood pressure monitoring.",
    "Child missed vaccination schedule and has cold symptoms. Counseling provided and immunization follow-up planned.",
    "Elderly patient reports joint pain and reduced appetite. Suggested nutrition support and check-up.",
    "No acute symptoms reported. Routine maternal health and sanitation guidance completed.",
]


def random_offset():
    lat_delta = random.uniform(-0.035, 0.035)
    lng_delta = random.uniform(-0.035, 0.035)
    return lat_delta, lng_delta


def build_photo_hash(seed_text):
    return hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:64]


def reset_database():
    SessionLocal.remove()
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    init_db()


def generate_demo_data():
    reset_database()
    session = SessionLocal()
    now = datetime.utcnow()

    try:
        phcs = [PHC(**item) for item in PHC_DATA]
        session.add_all(phcs)
        session.flush()

        workers = []
        for index, name in enumerate(WORKER_NAMES):
            phc = phcs[index // 4]
            worker = HealthWorker(
                name=name,
                phone=f"+91-90000{index + 100:03d}",
                zone=ZONES[index],
                phc_id=phc.id,
                language="hindi" if index % 3 else "odia",
                created_at=now - timedelta(days=random.randint(30, 180)),
            )
            workers.append(worker)
        session.add_all(workers)
        session.flush()

        households = []
        for index in range(40):
            phc = phcs[index % len(phcs)]
            zone = ZONES[index % len(ZONES)]
            lat_delta, lng_delta = random_offset()
            last_visit_gap = random.randint(3, 45)
            household = Household(
                address=f"House {index + 1}, {zone}, {phc.district}",
                zone=zone,
                lat=round(phc.lat + lat_delta, 6),
                lng=round(phc.lng + lng_delta, 6),
                phc_id=phc.id,
                risk_level="critical" if index % 13 == 0 else "high" if index % 7 == 0 else "normal",
                last_visit_date=now - timedelta(days=last_visit_gap),
            )
            households.append(household)
        session.add_all(households)
        session.flush()

        fake_visit_specs = {
            5: {"distance_shift": (0.18, 0.19), "photo_hash": "reused-photo-alpha", "visit_time": time(22, 15), "status": "fake"},
            21: {"distance_shift": (0.22, -0.16), "photo_hash": "reused-photo-alpha", "visit_time": time(5, 20), "status": "fake"},
            47: {"distance_shift": (-0.20, 0.21), "photo_hash": "reused-photo-bravo", "visit_time": time(7, 45), "status": "flagged"},
            63: {"distance_shift": (0.16, 0.14), "photo_hash": "reused-photo-bravo", "visit_time": time(21, 30), "status": "fake"},
        }

        visits = []
        for index in range(80):
            worker = workers[index % len(workers)]
            household = households[index % len(households)]
            visit_day_offset = random.randint(0, 29)
            base_date = now - timedelta(days=visit_day_offset)
            visit_datetime = base_date.replace(
                hour=random.randint(8, 18),
                minute=random.choice([0, 10, 20, 30, 40, 50]),
                second=0,
                microsecond=0,
            )

            gps_lat = household.lat + random.uniform(-0.0018, 0.0018)
            gps_lng = household.lng + random.uniform(-0.0018, 0.0018)
            photo_hash = build_photo_hash(f"visit-{index}-{worker.id}-{household.id}")
            status = "verified" if index % 6 else "pending"
            verification_reason = "Visit appears normal." if status == "verified" else None

            if index in fake_visit_specs:
                spec = fake_visit_specs[index]
                visit_datetime = visit_datetime.replace(
                    hour=spec["visit_time"].hour,
                    minute=spec["visit_time"].minute,
                )
                while visit_datetime.weekday() != 6:
                    visit_datetime -= timedelta(days=1)
                gps_lat = household.lat + spec["distance_shift"][0]
                gps_lng = household.lng + spec["distance_shift"][1]
                photo_hash = spec["photo_hash"]
                status = spec["status"]
                verification_reason = "Suspicious location, repeated photo, and odd timing detected."

            visit = Visit(
                worker_id=worker.id,
                household_id=household.id,
                visit_date=visit_datetime,
                gps_lat=round(gps_lat, 6),
                gps_lng=round(gps_lng, 6),
                photo_hash=photo_hash,
                reported_symptoms=random.choice(SYMPTOMS),
                status=status,
                verification_reason=verification_reason,
                created_at=visit_datetime,
            )
            household.last_visit_date = max(
                household.last_visit_date or visit_datetime,
                visit_datetime,
            )
            visits.append(visit)

        session.add_all(visits)
        session.flush()

        seeded_alerts = [
            ("fake_visit", "critical", "Lata Bai reported a visit 24 km away from the mapped household and reused a prior photo.", "Kurud North", False, visits[5].id),
            ("fake_visit", "high", "Premchand filed a Sunday dawn visit with reused evidence. Supervisor review needed.", "Kurud South", False, visits[21].id),
            ("fake_visit", "critical", "Rukmini Sahu submitted a late-night visit from outside the assigned zone.", "Dhamtari Lake View", False, visits[63].id),
            ("missed_area", "high", "Kurud River Belt has multiple households without a confirmed visit in over 30 days.", "Kurud River Belt", False, None),
            ("missed_area", "medium", "Jagdalpur East coverage dropped below the weekly baseline.", "Jagdalpur East", False, None),
            ("outbreak_risk", "critical", "Dhamtari Upland shows low visit density and several high-risk households.", "Dhamtari Upland", False, None),
            ("worker_burnout", "medium", "Sunita Devi logged 11 visits in one day across distant households.", "Kurud Forest Edge", True, None),
            ("worker_burnout", "low", "Meena Patel has had three consecutive heavy field days. Consider route balancing.", "Dhamtari West", True, None),
            ("missed_area", "high", "Jagdalpur Tribal Hamlet remains underserved for the past two weeks.", "Jagdalpur Tribal Hamlet", False, None),
            ("outbreak_risk", "critical", "Jagdalpur Market Line has a cluster of fever reports and low recent attendance.", "Jagdalpur Market Line", True, None),
        ]

        alerts = []
        for index, (alert_type, severity, message, zone, is_resolved, visit_id) in enumerate(seeded_alerts):
            alerts.append(
                Alert(
                    visit_id=visit_id,
                    alert_type=alert_type,
                    severity=severity,
                    message=message,
                    zone=zone,
                    is_resolved=is_resolved,
                    created_at=now - timedelta(days=index % 6, hours=index * 2),
                )
            )
        session.add_all(alerts)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        SessionLocal.remove()


if __name__ == "__main__":
    generate_demo_data()
    print("Demo data generated successfully.")
