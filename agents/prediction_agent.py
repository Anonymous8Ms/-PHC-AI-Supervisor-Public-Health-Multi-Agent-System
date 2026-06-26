from datetime import datetime, timedelta

from sqlalchemy import func

from config import get_gemini_response
from database import SessionLocal
from models import Alert, Household, Visit


class PredictionAgent:
    def __init__(self, session=None):
        self.session = session or SessionLocal()
        self._owns_session = session is None

    def _close(self):
        if self._owns_session:
            self.session.close()

    def _fallback_prediction(self, zone_metrics):
        predictions = []
        for item in zone_metrics:
            unvisited = item["unvisited_households"]
            visits_7d = item["visits_7d"]
            if unvisited >= 3 or visits_7d == 0:
                risk_level = "critical" if unvisited >= 5 or visits_7d == 0 else "high"
                predictions.append(
                    {
                        "zone": item["zone"],
                        "risk_level": risk_level,
                        "reason": (
                            f"{item['zone']} has {unvisited} households without a recent visit and "
                            f"only {visits_7d} visits in the last 7 days."
                        ),
                        "recommended_action": "Prioritize a supervisor review and redeploy workers this week.",
                    }
                )
            else:
                predictions.append(
                    {
                        "zone": item["zone"],
                        "risk_level": "normal",
                        "reason": "Coverage is within expected range.",
                        "recommended_action": "Continue routine monitoring.",
                    }
                )
        return predictions

    def execute(self):
        try:
            now = datetime.utcnow()
            cutoff_7 = now - timedelta(days=7)
            cutoff_14 = now - timedelta(days=14)
            cutoff_30 = now - timedelta(days=30)

            zone_rows = (
                self.session.query(Household.zone)
                .distinct()
                .order_by(Household.zone.asc())
                .all()
            )

            zone_metrics = []
            summary_lines = []
            for (zone,) in zone_rows:
                household_ids = [item[0] for item in self.session.query(Household.id).filter(Household.zone == zone).all()]
                visits_7d = self.session.query(func.count(Visit.id)).filter(
                    Visit.household_id.in_(household_ids),
                    Visit.visit_date >= cutoff_7,
                ).scalar() or 0
                visits_14d = self.session.query(func.count(Visit.id)).filter(
                    Visit.household_id.in_(household_ids),
                    Visit.visit_date >= cutoff_14,
                ).scalar() or 0
                visits_30d = self.session.query(func.count(Visit.id)).filter(
                    Visit.household_id.in_(household_ids),
                    Visit.visit_date >= cutoff_30,
                ).scalar() or 0
                unvisited = self.session.query(func.count(Household.id)).filter(
                    Household.zone == zone,
                    (
                        (Household.last_visit_date.is_(None))
                        | (Household.last_visit_date < cutoff_30)
                    ),
                ).scalar() or 0

                metric = {
                    "zone": zone,
                    "visits_7d": int(visits_7d),
                    "visits_14d": int(visits_14d),
                    "visits_30d": int(visits_30d),
                    "unvisited_households": int(unvisited),
                }
                zone_metrics.append(metric)
                summary_lines.append(
                    f"Zone: {zone}, Visits last 7d: {visits_7d}, 14d: {visits_14d}, 30d: {visits_30d}, "
                    f"Unvisited households: {unvisited}"
                )

            system_prompt = (
                "You are a public health analytics AI. Analyze the following zone data and identify "
                'which zones are at risk of becoming underserved. Return ONLY a JSON array with this exact '
                'format: [{"zone": "string", "risk_level": "normal|high|critical", "reason": "string", '
                '"recommended_action": "string"}]'
            )
            ai_result = get_gemini_response(system_prompt, "\n".join(summary_lines), json_mode=True)
            predictions = ai_result if isinstance(ai_result, list) else self._fallback_prediction(zone_metrics)

            zone_lookup = {item["zone"]: item for item in predictions if isinstance(item, dict) and item.get("zone")}
            if not zone_lookup:
                predictions = self._fallback_prediction(zone_metrics)
                zone_lookup = {item["zone"]: item for item in predictions}

            for metric in zone_metrics:
                zone = metric["zone"]
                prediction = zone_lookup.get(zone) or {
                    "zone": zone,
                    "risk_level": "normal",
                    "reason": "Coverage is within expected range.",
                    "recommended_action": "Continue routine monitoring.",
                }
                risk_level = prediction.get("risk_level", "normal")
                self.session.query(Household).filter(Household.zone == zone).update(
                    {"risk_level": risk_level},
                    synchronize_session=False,
                )
                if risk_level != "normal":
                    alert_type = "outbreak_risk" if risk_level == "critical" else "missed_area"
                    existing_alert = (
                        self.session.query(Alert)
                        .filter(
                            Alert.zone == zone,
                            Alert.alert_type == alert_type,
                            Alert.is_resolved.is_(False),
                        )
                        .first()
                    )
                    if not existing_alert:
                        self.session.add(
                            Alert(
                                visit_id=None,
                                alert_type=alert_type,
                                severity="critical" if risk_level == "critical" else "high",
                                message=prediction.get("reason", "Zone requires attention."),
                                zone=zone,
                                is_resolved=False,
                            )
                        )

            self.session.commit()
            return predictions
        except Exception as exc:
            self.session.rollback()
            return [{"zone": "unknown", "risk_level": "high", "reason": str(exc), "recommended_action": "Inspect prediction inputs."}]
        finally:
            self._close()
