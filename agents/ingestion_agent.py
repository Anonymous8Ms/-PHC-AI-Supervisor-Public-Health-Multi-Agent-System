from datetime import datetime

from config import get_gemini_response
from database import SessionLocal
from models import HealthWorker, Household, Visit


class IngestionAgent:
    def __init__(self, session=None):
        self.session = session or SessionLocal()
        self._owns_session = session is None

    def _close(self):
        if self._owns_session:
            self.session.close()

    def execute(self, payload):
        try:
            worker = self.session.get(HealthWorker, payload.get("worker_id"))
            household = self.session.get(Household, payload.get("household_id"))

            if not worker or not household:
                missing = []
                if not worker:
                    missing.append("worker_id")
                if not household:
                    missing.append("household_id")
                return {"error": f"Invalid reference: {', '.join(missing)}"}

            reported_symptoms = (payload.get("reported_symptoms") or "").strip()
            visit_date_raw = payload.get("visit_date")
            visit_date = datetime.fromisoformat(visit_date_raw) if visit_date_raw else datetime.utcnow()

            summary = "No symptoms reported. Routine follow-up recorded."
            if reported_symptoms:
                system_prompt = (
                    "You are a medical data summarizer. Summarize the following health worker "
                    "visit report in 2 sentences. Focus on key symptoms and recommended follow-up actions. "
                    f"Report: {reported_symptoms}"
                )
                summary = get_gemini_response(system_prompt, reported_symptoms)
                if not summary or "temporarily unavailable" in str(summary).lower():
                    summary = "Symptoms noted and follow-up may be required based on the reported condition."

            visit = Visit(
                worker_id=worker.id,
                household_id=household.id,
                visit_date=visit_date,
                gps_lat=float(payload.get("gps_lat")),
                gps_lng=float(payload.get("gps_lng")),
                photo_hash=payload.get("photo_hash"),
                reported_symptoms=reported_symptoms or None,
                status="pending",
            )
            self.session.add(visit)
            household.last_visit_date = visit_date
            self.session.commit()

            return {"visit_id": visit.id, "summary": summary, "status": "stored"}
        except Exception as exc:
            self.session.rollback()
            return {"error": str(exc)}
        finally:
            self._close()
