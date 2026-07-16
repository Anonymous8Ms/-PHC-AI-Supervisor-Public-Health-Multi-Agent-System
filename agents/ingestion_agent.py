"""Agent responsible for validating and storing visit submissions."""

from datetime import datetime
from typing import Any, Dict, Optional

from config import get_gemini_response
from database import SessionLocal
from models import HealthWorker, Household, Visit


class IngestionAgent:
    """Store a visit report and request an AI summary when symptoms exist."""

    def __init__(self, session: Optional[Any] = None) -> None:
        self.session = session or SessionLocal()
        self._owns_session = session is None

    def _close(self) -> None:
        if self._owns_session:
            self.session.close()

    @staticmethod
    def _error(
        message: str,
        status_code: int,
        code: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "error": message,
            "status_code": status_code,
            "code": code,
        }
        if details:
            payload["details"] = details
        return payload

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            required_fields = ["worker_id", "household_id", "gps_lat", "gps_lng"]
            missing_fields = [field for field in required_fields if payload.get(field) in (None, "")]
            if missing_fields:
                return self._error(
                    "Missing required visit fields",
                    400,
                    "missing_fields",
                    {"fields": missing_fields},
                )

            worker = self.session.get(HealthWorker, payload.get("worker_id"))
            household = self.session.get(Household, payload.get("household_id"))

            if not worker or not household:
                missing = []
                if not worker:
                    missing.append("worker_id")
                if not household:
                    missing.append("household_id")
                return self._error(
                    f"Invalid reference: {', '.join(missing)}",
                    404,
                    "invalid_reference",
                    {"fields": missing},
                )

            reported_symptoms = (payload.get("reported_symptoms") or "").strip()
            visit_date_raw = payload.get("visit_date")
            try:
                visit_date = datetime.fromisoformat(visit_date_raw) if visit_date_raw else datetime.utcnow()
            except ValueError:
                return self._error(
                    "visit_date must be a valid ISO 8601 datetime",
                    400,
                    "invalid_visit_date",
                )

            try:
                gps_lat = float(payload.get("gps_lat"))
                gps_lng = float(payload.get("gps_lng"))
            except (TypeError, ValueError):
                return self._error(
                    "gps_lat and gps_lng must be valid numbers",
                    400,
                    "invalid_coordinates",
                )

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
                gps_lat=gps_lat,
                gps_lng=gps_lng,
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
            return self._error(
                "Unable to store visit",
                500,
                "ingestion_failed",
                {"exception": str(exc)},
            )
        finally:
            self._close()
