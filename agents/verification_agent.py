import math
from datetime import datetime, timedelta

from config import get_gemini_response
from database import SessionLocal
from models import Alert, Visit


class VerificationAgent:
    def __init__(self, session=None):
        self.session = session or SessionLocal()
        self._owns_session = session is None

    def _close(self):
        if self._owns_session:
            self.session.close()

    @staticmethod
    def haversine_distance(lat1, lng1, lat2, lng2):
        earth_radius = 6371000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lng2 - lng1)

        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return earth_radius * c

    def execute(self, visit_id):
        try:
            visit = self.session.get(Visit, visit_id)
            if not visit or not visit.worker or not visit.household:
                return {"error": "Visit not found"}

            household = visit.household
            distance_m = self.haversine_distance(
                visit.gps_lat,
                visit.gps_lng,
                household.lat,
                household.lng,
            )
            photo_reused = False
            if visit.photo_hash:
                recent_threshold = visit.visit_date - timedelta(days=30)
                reused = (
                    self.session.query(Visit)
                    .filter(
                        Visit.photo_hash == visit.photo_hash,
                        Visit.id != visit.id,
                        Visit.visit_date >= recent_threshold,
                    )
                    .first()
                )
                photo_reused = reused is not None

            odd_timing = (
                visit.visit_date.weekday() == 6
                or visit.visit_date.hour < 6
                or visit.visit_date.hour >= 21
            )

            flags = sum([distance_m > 500, photo_reused, odd_timing])
            if flags == 0:
                status = "verified"
            elif distance_m > 2000 or flags >= 2:
                status = "fake"
            else:
                status = "flagged"

            system_prompt = (
                "You are a fraud detection analyst for rural health programs. "
                "A health worker visit was flagged. Generate a 1-sentence explanation in English. "
                f"Use these facts: Distance from household: {distance_m:.1f}m. "
                f"Photo reused: {'yes' if photo_reused else 'no'}. "
                f"Odd timing: {'yes' if odd_timing else 'no'}."
            )
            reason = get_gemini_response(system_prompt, f"Visit ID: {visit.id}")
            if not reason or "temporarily unavailable" in str(reason).lower():
                parts = []
                if distance_m > 500:
                    parts.append(f"GPS was {distance_m:.0f} meters away from the household")
                if photo_reused:
                    parts.append("the same photo evidence appeared in another recent visit")
                if odd_timing:
                    parts.append("the report was submitted at an unusual time")
                reason = "Visit appears normal." if not parts else " and ".join(parts).capitalize() + "."

            visit.status = status
            visit.verification_reason = reason

            if status in {"flagged", "fake"}:
                existing_alert = (
                    self.session.query(Alert)
                    .filter(Alert.visit_id == visit.id, Alert.alert_type == "fake_visit")
                    .first()
                )
                if not existing_alert:
                    alert = Alert(
                        visit_id=visit.id,
                        alert_type="fake_visit",
                        severity="critical" if status == "fake" else "high",
                        message=reason,
                        zone=visit.worker.zone,
                        is_resolved=False,
                    )
                    self.session.add(alert)

            self.session.commit()
            return {
                "visit_id": visit.id,
                "status": status,
                "reason": reason,
                "distance_m": round(distance_m, 2),
            }
        except Exception as exc:
            self.session.rollback()
            return {"error": str(exc)}
        finally:
            self._close()
