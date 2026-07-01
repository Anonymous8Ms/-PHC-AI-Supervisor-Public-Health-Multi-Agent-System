from datetime import datetime, timedelta

from sqlalchemy import func

from config import get_gemini_response
from database import SessionLocal
from models import Alert, ChatLog, HealthWorker, Household, Visit


class SupervisorAgent:
    GREETING_TERMS = ["hi", "hello", "hey", "namaste", "good morning", "good evening"]
    ROLE_TERMS = ["what is your work", "what do you do", "who are you", "your work", "kaam", "kya karte", "tum kya", "aap kya"]
    SUPPORTED_TERMS = [
        "worker",
        "visit",
        "alert",
        "fake",
        "fraud",
        "zone",
        "risk",
        "critical",
        "report",
        "attendance",
        "query",
        "area",
        "issue",
        "problem",
        "underserved",
        "kaisi hai",
        "report kaisi",
        "coverage",
        "follow-up",
        "follow up",
        "flagged",
        "supervisor",
        "dashboard",
        "phc",
    ]

    def __init__(self, session=None):
        self.session = session or SessionLocal()
        self._owns_session = session is None

    def _close(self):
        if self._owns_session:
            self.session.close()

    def _find_worker(self, query):
        lowered = query.lower()
        workers = self.session.query(HealthWorker).all()
        for worker in workers:
            if worker.name.lower() in lowered:
                return worker
        return None

    def _worker_stats(self, worker):
        today = datetime.utcnow().date()
        total_visits = self.session.query(func.count(Visit.id)).filter(Visit.worker_id == worker.id).scalar() or 0
        visits_today = self.session.query(func.count(Visit.id)).filter(
            Visit.worker_id == worker.id,
            func.date(Visit.visit_date) == today.isoformat(),
        ).scalar() or 0
        flagged = self.session.query(func.count(Visit.id)).filter(
            Visit.worker_id == worker.id,
            Visit.status.in_(["flagged", "fake"]),
        ).scalar() or 0
        last_visit = (
            self.session.query(Visit)
            .filter(Visit.worker_id == worker.id)
            .order_by(Visit.visit_date.desc())
            .first()
        )
        recent_issue = (
            self.session.query(Alert)
            .filter(Alert.zone == worker.zone)
            .order_by(Alert.created_at.desc())
            .first()
        )
        return {
            "worker": worker,
            "total_visits": int(total_visits),
            "visits_today": int(visits_today),
            "flagged_visits": int(flagged),
            "last_visit": last_visit,
            "recent_issue": recent_issue,
        }

    def _find_worker_context(self, query):
        worker = self._find_worker(query)
        if not worker:
            return ""
        stats = self._worker_stats(worker)
        return (
            f"Worker match: {worker.name}, Zone: {worker.zone}, Language: {worker.language}, "
            f"Total visits: {stats['total_visits']}, Visits today: {stats['visits_today']}, "
            f"Flagged visits: {stats['flagged_visits']}."
        )

    def _is_supported_query(self, query):
        query_lower = query.lower().strip()
        if not query_lower:
            return False
        return (
            self._find_worker(query) is not None
            or self._matches_phrase(query_lower, self.GREETING_TERMS)
            or self._matches_phrase(query_lower, self.ROLE_TERMS)
            or any(term in query_lower for term in self.SUPPORTED_TERMS)
        )

    @staticmethod
    def _matches_phrase(query_lower, phrases):
        normalized = f" {query_lower.strip()} "
        return any(f" {phrase} " in normalized or query_lower.strip() == phrase for phrase in phrases)

    def _build_fallback_response(self, query, language, stats_text, recent_alerts):
        query_lower = query.lower()
        worker = self._find_worker(query)
        is_hindi = language.lower() == "hindi"

        if self._matches_phrase(query_lower, self.GREETING_TERMS):
            if is_hindi:
                return "Namaste. Main Supervisor Agent hoon. Main worker attendance, fake visits, alerts, aur risk zones par short updates de sakta hoon."
            return "Hello. I am the Supervisor Agent. I can help with worker attendance, fake visits, alerts, and zone risk updates."

        if self._matches_phrase(query_lower, self.ROLE_TERMS):
            if is_hindi:
                return "Mera kaam health workers ki visits monitor karna, fake visit flags dikhana, aur risky zones par supervisor ko short guidance dena hai."
            return "My job is to monitor health worker visits, surface fake-visit risks, and guide supervisors on alerts and underserved zones."

        if not self._is_supported_query(query):
            if is_hindi:
                return (
                    "Yeh query mere trained dashboard scope ke bahar hai. Built-in prompts use kijiye, "
                    "ya 'Raise Query' option se specific worker, alert, ya zone request bhejiye."
                )
            return (
                "That question is outside my trained dashboard scope. Use one of the built-in prompts, "
                "or use Raise Query for a specific worker, alert, or zone request."
            )

        critical_zones = [
            zone for (zone,) in self.session.query(Household.zone).filter(Household.risk_level == "critical").distinct().all()
        ]
        active_alerts = (
            self.session.query(Alert)
            .filter(Alert.is_resolved.is_(False))
            .order_by(Alert.created_at.desc())
            .limit(3)
            .all()
        )

        if "which worker has flagged visits" in query_lower or "flagged worker" in query_lower:
            flagged_workers = (
                self.session.query(HealthWorker.name, func.count(Visit.id).label("flagged_count"))
                .join(Visit, Visit.worker_id == HealthWorker.id)
                .filter(Visit.status.in_(["flagged", "fake"]))
                .group_by(HealthWorker.id)
                .order_by(func.count(Visit.id).desc())
                .limit(3)
                .all()
            )
            if not flagged_workers:
                return "No workers currently have flagged visits."
            summary = ", ".join(f"{name} ({count})" for name, count in flagged_workers)
            if is_hindi:
                return f"Flagged visits wale workers: {summary}. In cases ko supervisor review karna chahiye."
            return f"Workers with flagged visits: {summary}. These cases should be reviewed first."

        if "urgent follow-up" in query_lower or "needs urgent follow-up" in query_lower:
            urgent_zone = critical_zones[0] if critical_zones else "none"
            if is_hindi:
                return f"Sabse urgent follow-up zone {urgent_zone} hai. Wahan critical risk aur active alert attention chahiye."
            return f"The most urgent follow-up zone is {urgent_zone}. It has critical risk and needs immediate field attention."

        if "summarize active fake visit alerts" in query_lower or "fake visit alerts" in query_lower:
            fake_alerts = [alert for alert in active_alerts if alert.alert_type == "fake_visit"]
            if not fake_alerts:
                return "There are no active fake visit alerts right now."
            summary = "; ".join(f"{alert.zone}: {alert.message}" for alert in fake_alerts[:2])
            if is_hindi:
                return f"Active fake visit alerts: {summary}. Inhe sabse pehle verify karein."
            return f"Active fake visit alerts: {summary}. Verify these before lower-priority issues."

        if worker:
            worker_stats = self._worker_stats(worker)
            last_visit_text = (
                worker_stats["last_visit"].visit_date.strftime("%d %b %Y %I:%M %p")
                if worker_stats["last_visit"]
                else "No recorded visit"
            )
            recent_issue = worker_stats["recent_issue"].message if worker_stats["recent_issue"] else "No current alert"
            if is_hindi:
                return (
                    f"{worker.name} {worker.zone} zone me hai. Aaj {worker_stats['visits_today']} visits, total "
                    f"{worker_stats['total_visits']} visits, aur {worker_stats['flagged_visits']} flagged visits hain. "
                    f"Aakhri visit {last_visit_text}; latest issue: {recent_issue}."
                )
            return (
                f"{worker.name} is assigned to {worker.zone}. They have {worker_stats['visits_today']} visits today, "
                f"{worker_stats['total_visits']} total visits, and {worker_stats['flagged_visits']} flagged visits. "
                f"Last visit was {last_visit_text}; latest issue: {recent_issue}."
            )

        if any(keyword in query_lower for keyword in ["critical", "zone", "area", "underserved", "risk"]):
            zone_text = ", ".join(critical_zones[:4]) if critical_zones else "none"
            if is_hindi:
                return (
                    f"Critical zones abhi {zone_text} hain. Total active alerts {len(active_alerts)} top-priority cases me dikh rahe hain. "
                    "In zones me immediate field follow-up chahiye."
                )
            return (
                f"Current critical zones are {zone_text}. There are {len(active_alerts)} top-priority active alerts linked to these areas. "
                "These zones need immediate field follow-up."
            )

        if any(keyword in query_lower for keyword in ["alert", "fake", "fraud", "issue", "problem"]):
            alert_text = "; ".join(
                f"{alert.alert_type} in {alert.zone} ({alert.severity})"
                for alert in active_alerts
            ) or "No active alerts"
            if is_hindi:
                return f"Active alerts: {alert_text}. Sabse pehle fake visit aur outbreak risk cases review karein."
            return f"Active alerts: {alert_text}. Prioritize the fake visit and outbreak risk cases first."

        if is_hindi:
            return f"{stats_text} Recent alerts: {recent_alerts[:180]}. Agar aap worker ya zone ka naam poochhenge to main zyada specific jawab dunga."
        return f"{stats_text} Recent alerts: {recent_alerts[:180]}. Ask about a worker or zone name for a more specific answer."

    def _should_use_gemini(self, query):
        query_lower = query.lower().strip()
        if not self._is_supported_query(query):
            return False
        if self._matches_phrase(query_lower, self.GREETING_TERMS + self.ROLE_TERMS):
            return False
        deterministic_patterns = [
            "which worker has flagged visits",
            "flagged worker",
            "urgent follow-up",
            "needs urgent follow-up",
            "summarize active fake visit alerts",
            "fake visit alerts",
            "raise query",
        ]
        return not any(pattern in query_lower for pattern in deterministic_patterns)

    def _build_gemini_context(self, query):
        today = datetime.utcnow().date()
        recent_alerts = (
            self.session.query(Alert)
            .filter(Alert.is_resolved.is_(False))
            .order_by(Alert.created_at.desc())
            .limit(3)
            .all()
        )
        critical_zones = [zone for (zone,) in self.session.query(Household.zone).filter(Household.risk_level == "critical").distinct().limit(4).all()]
        worker = self._find_worker(query)
        worker_context = ""
        if worker:
            worker_stats = self._worker_stats(worker)
            last_visit = worker_stats["last_visit"].visit_date.isoformat() if worker_stats["last_visit"] else "none"
            issue = worker_stats["recent_issue"].message if worker_stats["recent_issue"] else "none"
            worker_context = (
                f"Worker: {worker.name}, zone {worker.zone}, language {worker.language}, visits_today {worker_stats['visits_today']}, "
                f"total_visits {worker_stats['total_visits']}, flagged_visits {worker_stats['flagged_visits']}, "
                f"last_visit {last_visit}, latest_issue {issue}."
            )
        stats = (
            f"today={today.isoformat()}, total_workers={self.session.query(func.count(HealthWorker.id)).scalar() or 0}, "
            f"visits_today={self.session.query(func.count(Visit.id)).filter(func.date(Visit.visit_date) == today.isoformat()).scalar() or 0}, "
            f"flagged_today={self.session.query(func.count(Visit.id)).filter(func.date(Visit.visit_date) == today.isoformat(), Visit.status.in_(['flagged', 'fake'])).scalar() or 0}."
        )
        alerts_context = "; ".join(
            f"{alert.alert_type} in {alert.zone} ({alert.severity}): {alert.message}"
            for alert in recent_alerts
        ) or "none"
        return (
            f"Dashboard scope only. {stats} Critical zones: {', '.join(critical_zones) or 'none'}. "
            f"Recent unresolved alerts: {alerts_context}. {worker_context}"
        ).strip()

    def execute(self, query, language="english"):
        try:
            now = datetime.utcnow()
            seven_days_ago = now - timedelta(days=7)
            today = now.date()

            alerts = (
                self.session.query(Alert)
                .filter(Alert.created_at >= seven_days_ago)
                .order_by(Alert.created_at.desc())
                .limit(5)
                .all()
            )
            recent_alerts = "; ".join(
                f"{alert.alert_type} in {alert.zone} ({alert.severity}) - {alert.message}"
                for alert in alerts
            ) or "No recent alerts."

            total_workers = self.session.query(func.count(HealthWorker.id)).scalar() or 0
            total_visits_today = self.session.query(func.count(Visit.id)).filter(
                func.date(Visit.visit_date) == today.isoformat()
            ).scalar() or 0
            flagged_today = self.session.query(func.count(Visit.id)).filter(
                func.date(Visit.visit_date) == today.isoformat(),
                Visit.status.in_(["flagged", "fake"]),
            ).scalar() or 0

            stats = (
                f"Total workers: {total_workers}, Total visits today: {total_visits_today}, "
                f"Flagged visits today: {flagged_today}."
            )
            response = None
            if self._should_use_gemini(query):
                context = self._build_gemini_context(query)
                system_prompt = (
                    "You are a website-scoped AI supervisor for a rural public health dashboard. "
                    f"Answer only in {language}. Stay within worker attendance, visit verification, alerts, supervisors, and zone coverage. "
                    "Do not answer unrelated general knowledge questions. If off-topic, tell the user to use built-in prompts or Raise Query. "
                    "Be natural but concise, maximum 2 short sentences. Do not restate the whole dashboard unless necessary. "
                    f"Context: {context}"
                )
                response = get_gemini_response(system_prompt, query)
            if not response or "temporarily unavailable" in str(response).lower():
                response = self._build_fallback_response(query, language, stats, recent_alerts)

            log = ChatLog(
                user_query=query,
                agent_response=response,
                agent_name="supervisor",
            )
            self.session.add(log)
            self.session.commit()

            return {"response": response, "agent": "supervisor"}
        except Exception as exc:
            self.session.rollback()
            return {"response": f"Unable to process request: {exc}", "agent": "supervisor"}
        finally:
            self._close()
