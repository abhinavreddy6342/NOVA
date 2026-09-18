"""
NOVA Analytics Service.

Provides operational intelligence calculations over real NOVA data sources:
    - Primary: NOVA Audit Trail (AuditStore)
    - Secondary: Sovereignty Center telemetry (sovereignty_service)
    - Secondary: Model Engine state & network ledger

No synthetic or fake data is ever generated. If no real data exists for
a metric or window, real empty states/zeros are returned.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.services.audit.service import audit_service
from app.services.sovereignty.service import sovereignty_service


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


def _parse_iso(timestamp_str: Optional[str]) -> Optional[datetime]:
    if not timestamp_str:
        return None
    try:
        clean = str(timestamp_str).strip()
        if clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        return datetime.fromisoformat(clean).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _percentile(values: List[float], p: float) -> Optional[float]:
    if not values:
        return None
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(sorted_vals[int(k)], 2)
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return round(d0 + d1, 2)


class AnalyticsService:
    """
    Core Analytics Calculation Layer for NOVA.
    """

    def __init__(self) -> None:
        pass

    # ---------------------------------------------------------------------
    # DATE RANGE RESOLUTION
    # ---------------------------------------------------------------------

    def resolve_date_range(
        self,
        range_key: str = "24h",
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None,
    ) -> tuple[Optional[datetime], Optional[datetime], str]:
        """
        Resolve date range selection into (start_dt, end_dt, range_name).
        """
        now = _utc_now()
        key = (range_key or "24h").lower().strip()

        if key == "1h":
            start_dt = now - timedelta(hours=1)
            return start_dt, now, "1h"
        elif key == "24h":
            start_dt = now - timedelta(hours=24)
            return start_dt, now, "24h"
        elif key == "7d":
            start_dt = now - timedelta(days=7)
            return start_dt, now, "7d"
        elif key == "30d":
            start_dt = now - timedelta(days=30)
            return start_dt, now, "30d"
        elif key == "custom":
            start_dt = _parse_iso(custom_start)
            end_dt = _parse_iso(custom_end) or now
            return start_dt, end_dt, "custom"
        else:
            # Default to 24h
            start_dt = now - timedelta(hours=24)
            return start_dt, now, "24h"

    # ---------------------------------------------------------------------
    # FETCH FILTERED EVENTS FROM AUDIT STORE
    # ---------------------------------------------------------------------

    def _get_filtered_events(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        action: Optional[str] = None,
        service: Optional[str] = None,
        status: Optional[str] = None,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        start_str = start_dt.isoformat().replace("+00:00", "Z") if start_dt else None
        end_str = end_dt.isoformat().replace("+00:00", "Z") if end_dt else None

        result = audit_service.list_events(
            query=query,
            category=category,
            action=action,
            service=service,
            status=status,
            model=model,
            task_type=task_type,
            start_time=start_str,
            end_time=end_str,
            limit=10000,
            offset=0,
        )
        return result.get("events", [])

    # ---------------------------------------------------------------------
    # SUMMARY / KPI CENTER
    # ---------------------------------------------------------------------

    def get_summary(
        self,
        range_key: str = "24h",
        query: Optional[str] = None,
        category: Optional[str] = None,
        service: Optional[str] = None,
        status: Optional[str] = None,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None,
    ) -> Dict[str, Any]:
        start_dt, end_dt, active_range = self.resolve_date_range(
            range_key, custom_start, custom_end
        )
        events = self._get_filtered_events(
            query=query,
            category=category,
            service=service,
            status=status,
            model=model,
            task_type=task_type,
            start_dt=start_dt,
            end_dt=end_dt,
        )

        total_events = len(events)
        successful_events = 0
        failed_events = 0
        running_events = 0
        external_events = 0

        models_used = set()
        services_used = set()
        categories_used = set()
        actions_used = set()

        durations: List[float] = []

        mission_count = 0
        mission_completed = 0
        mission_failed = 0

        knowledge_ops = 0
        artifacts_generated = 0

        for event in events:
            cat = str(event.get("category", "")).lower()
            act = str(event.get("action", "")).lower()
            srv = str(event.get("service", "")).lower()
            st = str(event.get("status", "")).lower()
            mdl = event.get("model")
            dur = event.get("duration_ms")

            if cat:
                categories_used.add(cat)
            if act:
                actions_used.add(act)
            if srv:
                services_used.add(srv)
            if mdl and str(mdl).strip():
                models_used.add(str(mdl).strip())

            if st in {"success", "successful", "completed", "complete", "pass", "passed"}:
                successful_events += 1
            elif st in {"failed", "failure", "error"}:
                failed_events += 1
            elif st in {"running", "started", "in_progress", "pending"}:
                running_events += 1

            if cat in {"external_api", "cloud_upload", "network", "sovereignty"} or act in {
                "network_request",
                "cloud_sync",
                "external_call",
            }:
                external_events += 1

            if dur is not None and isinstance(dur, (int, float)) and float(dur) >= 0:
                durations.append(float(dur))

            # Subsystem heuristics from actual events
            if cat in {"mission", "agent"} or srv in {"agent_executor", "planner", "mission"}:
                mission_count += 1
                if st in {"success", "completed"}:
                    mission_completed += 1
                elif st in {"failed", "error"}:
                    mission_failed += 1

            if cat == "knowledge" or srv in {"vector_store", "knowledge", "extractor"}:
                knowledge_ops += 1

            if cat == "artifact" or act in {"artifact_generation", "generate_artifact"}:
                artifacts_generated += 1

        success_rate = (
            round((successful_events / total_events) * 100.0, 1)
            if total_events > 0
            else 0.0
        )

        avg_latency = (
            round(sum(durations) / len(durations), 2) if durations else None
        )
        min_latency = round(min(durations), 2) if durations else None
        max_latency = round(max(durations), 2) if durations else None
        median_latency = _percentile(durations, 50)
        p95_latency = _percentile(durations, 95)

        return {
            "total_events": total_events,
            "successful_events": successful_events,
            "failed_events": failed_events,
            "running_events": running_events,
            "success_rate_percent": success_rate,
            "total_operations": len(actions_used),
            "external_events": external_events,
            "models_used_count": len(models_used),
            "models_used_list": sorted(list(models_used)),
            "services_used_count": len(services_used),
            "categories_used_count": len(categories_used),
            "latency": {
                "measured_count": len(durations),
                "avg_ms": avg_latency,
                "min_ms": min_latency,
                "max_ms": max_latency,
                "median_ms": median_latency,
                "p95_ms": p95_latency,
            },
            "subsystems": {
                "missions_count": mission_count,
                "missions_completed": mission_completed,
                "missions_failed": mission_failed,
                "knowledge_ops": knowledge_ops,
                "artifacts_generated": artifacts_generated,
            },
            "active_range": active_range,
            "updated_at": _iso_now(),
        }

    # ---------------------------------------------------------------------
    # TIME SERIES TREND ANALYTICS
    # ---------------------------------------------------------------------

    def get_activity_trends(
        self,
        range_key: str = "24h",
        query: Optional[str] = None,
        category: Optional[str] = None,
        service: Optional[str] = None,
        status: Optional[str] = None,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None,
    ) -> Dict[str, Any]:
        start_dt, end_dt, active_range = self.resolve_date_range(
            range_key, custom_start, custom_end
        )
        events = self._get_filtered_events(
            query=query,
            category=category,
            service=service,
            status=status,
            model=model,
            task_type=task_type,
            start_dt=start_dt,
            end_dt=end_dt,
        )

        now = end_dt or _utc_now()

        # Determine buckets
        if active_range == "1h":
            # 30 buckets of 2 minutes
            bucket_delta = timedelta(minutes=2)
            num_buckets = 30
            fmt = "%H:%M"
        elif active_range == "24h":
            # 24 buckets of 1 hour
            bucket_delta = timedelta(hours=1)
            num_buckets = 24
            fmt = "%H:00"
        elif active_range == "7d":
            # 7 buckets of 1 day
            bucket_delta = timedelta(days=1)
            num_buckets = 7
            fmt = "%b %d"
        elif active_range == "30d":
            # 30 buckets of 1 day
            bucket_delta = timedelta(days=1)
            num_buckets = 30
            fmt = "%b %d"
        else:
            # Custom range calculation
            if start_dt and end_dt:
                total_sec = (end_dt - start_dt).total_seconds()
                if total_sec <= 3600:
                    bucket_delta = timedelta(minutes=2)
                    num_buckets = max(1, int(total_sec // 120))
                    fmt = "%H:%M"
                elif total_sec <= 86400 * 2:
                    bucket_delta = timedelta(hours=1)
                    num_buckets = max(1, int(total_sec // 3600))
                    fmt = "%H:00"
                else:
                    bucket_delta = timedelta(days=1)
                    num_buckets = max(1, int(total_sec // 86400))
                    fmt = "%b %d"
            else:
                bucket_delta = timedelta(hours=1)
                num_buckets = 24
                fmt = "%H:00"

        # Initialize bucket timelines
        buckets: List[Dict[str, Any]] = []
        eff_start = start_dt or (now - bucket_delta * num_buckets)

        for i in range(num_buckets):
            b_start = eff_start + (bucket_delta * i)
            b_end = b_start + bucket_delta
            buckets.append(
                {
                    "start_iso": b_start.isoformat().replace("+00:00", "Z"),
                    "end_iso": b_end.isoformat().replace("+00:00", "Z"),
                    "label": b_start.strftime(fmt),
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "running": 0,
                    "durations": [],
                }
            )

        # Place events into buckets
        for event in events:
            ev_dt = _parse_iso(event.get("timestamp"))
            if not ev_dt:
                continue

            st = str(event.get("status", "")).lower()
            dur = event.get("duration_ms")

            for b in buckets:
                b_s = _parse_iso(b["start_iso"])
                b_e = _parse_iso(b["end_iso"])
                if b_s and b_e and b_s <= ev_dt < b_e:
                    b["total"] += 1
                    if st in {"success", "successful", "completed", "complete", "pass", "passed"}:
                        b["success"] += 1
                    elif st in {"failed", "failure", "error"}:
                        b["failed"] += 1
                    elif st in {"running", "started", "in_progress", "pending"}:
                        b["running"] += 1

                    if dur is not None and isinstance(dur, (int, float)) and float(dur) >= 0:
                        b["durations"].append(float(dur))
                    break

        # Calculate final bucket stats
        trend_series = []
        for b in buckets:
            durs = b.pop("durations", [])
            avg_d = round(sum(durs) / len(durs), 2) if durs else None
            trend_series.append(
                {
                    "label": b["label"],
                    "timestamp": b["start_iso"],
                    "total": b["total"],
                    "success": b["success"],
                    "failed": b["failed"],
                    "running": b["running"],
                    "avg_duration_ms": avg_d,
                }
            )

        return {
            "range": active_range,
            "series": trend_series,
            "total_events": len(events),
        }

    # ---------------------------------------------------------------------
    # BREAKDOWNS (CATEGORIES, SERVICES, MODELS, TASK TYPES, STATUSES)
    # ---------------------------------------------------------------------

    def get_categories_breakdown(
        self,
        range_key: str = "24h",
        query: Optional[str] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_dt, end_dt, _ = self.resolve_date_range(range_key, custom_start, custom_end)
        events = self._get_filtered_events(query=query, start_dt=start_dt, end_dt=end_dt)

        counts: Dict[str, int] = {}
        total = len(events)

        for ev in events:
            cat = str(ev.get("category", "unknown")).lower()
            counts[cat] = counts.get(cat, 0) + 1

        result = []
        for cat, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            pct = round((cnt / total) * 100.0, 1) if total > 0 else 0.0
            result.append(
                {
                    "category": cat,
                    "count": cnt,
                    "percentage": pct,
                }
            )

        return result

    def get_services_breakdown(
        self,
        range_key: str = "24h",
        query: Optional[str] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_dt, end_dt, _ = self.resolve_date_range(range_key, custom_start, custom_end)
        events = self._get_filtered_events(query=query, start_dt=start_dt, end_dt=end_dt)

        stats: Dict[str, Dict[str, Any]] = {}

        for ev in events:
            srv = str(ev.get("service", "unknown")).lower()
            st = str(ev.get("status", "")).lower()
            dur = ev.get("duration_ms")

            if srv not in stats:
                stats[srv] = {
                    "service": srv,
                    "count": 0,
                    "success": 0,
                    "failed": 0,
                    "durations": [],
                }

            s = stats[srv]
            s["count"] += 1

            if st in {"success", "successful", "completed", "complete", "pass", "passed"}:
                s["success"] += 1
            elif st in {"failed", "failure", "error"}:
                s["failed"] += 1

            if dur is not None and isinstance(dur, (int, float)) and float(dur) >= 0:
                s["durations"].append(float(dur))

        result = []
        for srv, s in sorted(stats.items(), key=lambda x: x[1]["count"], reverse=True):
            durs = s["durations"]
            avg_dur = round(sum(durs) / len(durs), 2) if durs else None
            result.append(
                {
                    "service": srv,
                    "count": s["count"],
                    "success": s["success"],
                    "failed": s["failed"],
                    "avg_duration_ms": avg_dur,
                }
            )

        return result

    def get_models_breakdown(
        self,
        range_key: str = "24h",
        query: Optional[str] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_dt, end_dt, _ = self.resolve_date_range(range_key, custom_start, custom_end)
        events = self._get_filtered_events(query=query, start_dt=start_dt, end_dt=end_dt)

        stats: Dict[str, Dict[str, Any]] = {}

        for ev in events:
            mdl = ev.get("model")
            if not mdl or not str(mdl).strip():
                continue

            mdl_name = str(mdl).strip()
            st = str(ev.get("status", "")).lower()
            dur = ev.get("duration_ms")
            ts = ev.get("timestamp")

            if mdl_name not in stats:
                stats[mdl_name] = {
                    "model": mdl_name,
                    "request_count": 0,
                    "success_count": 0,
                    "failed_count": 0,
                    "durations": [],
                    "last_used": ts,
                }

            s = stats[mdl_name]
            s["request_count"] += 1

            if st in {"success", "successful", "completed", "complete", "pass", "passed"}:
                s["success_count"] += 1
            elif st in {"failed", "failure", "error"}:
                s["failed_count"] += 1

            if dur is not None and isinstance(dur, (int, float)) and float(dur) >= 0:
                s["durations"].append(float(dur))

            if ts and (not s["last_used"] or str(ts) > str(s["last_used"])):
                s["last_used"] = ts

        result = []
        for mdl, s in sorted(stats.items(), key=lambda x: x[1]["request_count"], reverse=True):
            durs = s["durations"]
            avg_lat = round(sum(durs) / len(durs), 2) if durs else None
            result.append(
                {
                    "model": mdl,
                    "request_count": s["request_count"],
                    "success_count": s["success_count"],
                    "failed_count": s["failed_count"],
                    "avg_latency_ms": avg_lat,
                    "last_used": s["last_used"],
                }
            )

        return result

    def get_task_types_breakdown(
        self,
        range_key: str = "24h",
        query: Optional[str] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_dt, end_dt, _ = self.resolve_date_range(range_key, custom_start, custom_end)
        events = self._get_filtered_events(query=query, start_dt=start_dt, end_dt=end_dt)

        stats: Dict[str, Dict[str, Any]] = {}

        for ev in events:
            tt = ev.get("task_type")
            if not tt or not str(tt).strip():
                tt_name = "unspecified"
            else:
                tt_name = str(tt).strip().lower()

            st = str(ev.get("status", "")).lower()
            dur = ev.get("duration_ms")

            if tt_name not in stats:
                stats[tt_name] = {
                    "task_type": tt_name,
                    "count": 0,
                    "success": 0,
                    "failed": 0,
                    "durations": [],
                }

            s = stats[tt_name]
            s["count"] += 1

            if st in {"success", "successful", "completed", "complete", "pass", "passed"}:
                s["success"] += 1
            elif st in {"failed", "failure", "error"}:
                s["failed"] += 1

            if dur is not None and isinstance(dur, (int, float)) and float(dur) >= 0:
                s["durations"].append(float(dur))

        result = []
        for tt, s in sorted(stats.items(), key=lambda x: x[1]["count"], reverse=True):
            durs = s["durations"]
            avg_dur = round(sum(durs) / len(durs), 2) if durs else None
            result.append(
                {
                    "task_type": tt,
                    "count": s["count"],
                    "success": s["success"],
                    "failed": s["failed"],
                    "avg_duration_ms": avg_dur,
                }
            )

        return result

    def get_statuses_breakdown(
        self,
        range_key: str = "24h",
        query: Optional[str] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_dt, end_dt, _ = self.resolve_date_range(range_key, custom_start, custom_end)
        events = self._get_filtered_events(query=query, start_dt=start_dt, end_dt=end_dt)

        counts: Dict[str, int] = {}
        total = len(events)

        for ev in events:
            st = str(ev.get("status", "unknown")).lower()
            counts[st] = counts.get(st, 0) + 1

        result = []
        for st, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            pct = round((cnt / total) * 100.0, 1) if total > 0 else 0.0
            result.append(
                {
                    "status": st,
                    "count": cnt,
                    "percentage": pct,
                }
            )

        return result

    # ---------------------------------------------------------------------
    # LATENCY & PERFORMANCE ANALYTICS
    # ---------------------------------------------------------------------

    def get_latency_analytics(
        self,
        range_key: str = "24h",
        query: Optional[str] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None,
    ) -> Dict[str, Any]:
        start_dt, end_dt, active_range = self.resolve_date_range(
            range_key, custom_start, custom_end
        )
        events = self._get_filtered_events(query=query, start_dt=start_dt, end_dt=end_dt)

        all_durations: List[float] = []
        by_service: Dict[str, List[float]] = {}
        by_model: Dict[str, List[float]] = {}
        by_task_type: Dict[str, List[float]] = {}
        by_category: Dict[str, List[float]] = {}

        for ev in events:
            dur = ev.get("duration_ms")
            if dur is None or not isinstance(dur, (int, float)) or float(dur) < 0:
                continue

            val = float(dur)
            all_durations.append(val)

            srv = str(ev.get("service", "unknown")).lower()
            by_service.setdefault(srv, []).append(val)

            mdl = ev.get("model")
            if mdl and str(mdl).strip():
                by_model.setdefault(str(mdl).strip(), []).append(val)

            tt = ev.get("task_type")
            if tt and str(tt).strip():
                by_task_type.setdefault(str(tt).strip().lower(), []).append(val)

            cat = str(ev.get("category", "unknown")).lower()
            by_category.setdefault(cat, []).append(val)

        overall = {
            "measured_operations": len(all_durations),
            "avg_ms": round(sum(all_durations) / len(all_durations), 2) if all_durations else None,
            "min_ms": round(min(all_durations), 2) if all_durations else None,
            "max_ms": round(max(all_durations), 2) if all_durations else None,
            "median_ms": _percentile(all_durations, 50),
            "p95_ms": _percentile(all_durations, 95),
        }

        def build_stat_list(d: Dict[str, List[float]], key_name: str) -> List[Dict[str, Any]]:
            res = []
            for name, vals in d.items():
                res.append(
                    {
                        key_name: name,
                        "sample_count": len(vals),
                        "avg_ms": round(sum(vals) / len(vals), 2),
                        "min_ms": round(min(vals), 2),
                        "max_ms": round(max(vals), 2),
                        "p95_ms": _percentile(vals, 95),
                    }
                )
            return sorted(res, key=lambda x: x["avg_ms"], reverse=True)

        return {
            "overall": overall,
            "by_service": build_stat_list(by_service, "service"),
            "by_model": build_stat_list(by_model, "model"),
            "by_task_type": build_stat_list(by_task_type, "task_type"),
            "by_category": build_stat_list(by_category, "category"),
        }

    # ---------------------------------------------------------------------
    # SUBSYSTEM ANALYTICS (MISSIONS, KNOWLEDGE, ARTIFACTS, NETWORK, SYSTEM)
    # ---------------------------------------------------------------------

    def get_missions_analytics(
        self,
        range_key: str = "24h",
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None,
    ) -> Dict[str, Any]:
        start_dt, end_dt, _ = self.resolve_date_range(range_key, custom_start, custom_end)
        events = self._get_filtered_events(start_dt=start_dt, end_dt=end_dt)

        mission_events = [
            e for e in events
            if str(e.get("category", "")).lower() in {"mission", "agent"}
            or str(e.get("service", "")).lower() in {"agent_executor", "planner", "mission"}
        ]

        started = 0
        completed = 0
        failed = 0
        stopped = 0
        agent_runs = 0
        durations: List[float] = []

        for ev in mission_events:
            st = str(ev.get("status", "")).lower()
            act = str(ev.get("action", "")).lower()
            dur = ev.get("duration_ms")

            if st in {"started", "running"}:
                started += 1
            elif st in {"success", "completed", "complete"}:
                completed += 1
            elif st in {"failed", "error"}:
                failed += 1
            elif st in {"stopped", "cancelled", "cancel"}:
                stopped += 1

            if act in {"agent_run", "execute_step", "run_agent", "execution"}:
                agent_runs += 1

            if dur is not None and isinstance(dur, (int, float)) and float(dur) >= 0:
                durations.append(float(dur))

        avg_dur = round(sum(durations) / len(durations), 2) if durations else None

        return {
            "total_mission_events": len(mission_events),
            "started": started,
            "completed": completed,
            "failed": failed,
            "stopped": stopped,
            "agent_runs": agent_runs,
            "avg_mission_duration_ms": avg_dur,
            "latest_events": mission_events[:10],
        }

    def get_knowledge_analytics(
        self,
        range_key: str = "24h",
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None,
    ) -> Dict[str, Any]:
        start_dt, end_dt, _ = self.resolve_date_range(range_key, custom_start, custom_end)
        events = self._get_filtered_events(start_dt=start_dt, end_dt=end_dt)

        k_events = [
            e for e in events
            if str(e.get("category", "")).lower() == "knowledge"
            or str(e.get("service", "")).lower() in {"vector_store", "knowledge", "extractor"}
        ]

        indexing_ops = 0
        file_uploads = 0
        file_additions = 0
        file_deletions = 0
        reindex_ops = 0

        for ev in k_events:
            act = str(ev.get("action", "")).lower()
            if "index" in act:
                indexing_ops += 1
            if "upload" in act:
                file_uploads += 1
            if "add" in act:
                file_additions += 1
            if "delete" in act or "remove" in act:
                file_deletions += 1
            if "reindex" in act:
                reindex_ops += 1

        return {
            "total_knowledge_events": len(k_events),
            "indexing_operations": indexing_ops,
            "file_uploads": file_uploads,
            "file_additions": file_additions,
            "file_deletions": file_deletions,
            "reindex_operations": reindex_ops,
            "latest_events": k_events[:10],
        }

    def get_artifacts_analytics(
        self,
        range_key: str = "24h",
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None,
    ) -> Dict[str, Any]:
        start_dt, end_dt, _ = self.resolve_date_range(range_key, custom_start, custom_end)
        events = self._get_filtered_events(start_dt=start_dt, end_dt=end_dt)

        art_events = [
            e for e in events
            if str(e.get("category", "")).lower() == "artifact"
            or "artifact" in str(e.get("action", "")).lower()
        ]

        type_counts: Dict[str, int] = {}
        for ev in art_events:
            meta = ev.get("metadata") or {}
            art_type = meta.get("artifact_type") or meta.get("type") or "general"
            type_counts[str(art_type)] = type_counts.get(str(art_type), 0) + 1

        return {
            "total_artifact_events": len(art_events),
            "artifacts_generated": len(art_events),
            "by_type": [
                {"type": k, "count": v}
                for k, v in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
            ],
            "latest_events": art_events[:10],
        }

    def get_network_analytics(self) -> Dict[str, Any]:
        """
        Integrates real Sovereignty Center network ledger snapshot.
        """
        snapshot = sovereignty_service.get_snapshot()
        network_info = snapshot.get("network", {})

        ledger_summary = network_info.get("ledger_summary", {})
        allowed_count = ledger_summary.get("allowed_request_count", 0)
        blocked_count = ledger_summary.get("blocked_request_count", 0)
        external_count = ledger_summary.get("external_request_count", 0)
        tracking_mode = network_info.get("tracking", "application_level")

        return {
            "tracking_scope": "application_level",
            "tracking_mode": tracking_mode,
            "allowed_requests": allowed_count,
            "blocked_requests": blocked_count,
            "external_requests": external_count,
            "recent_entries": network_info.get("recent_entries", []),
            "disclaimer": "Application-level network tracking (local workspace scope)",
        }

    def get_resource_analytics(self) -> Dict[str, Any]:
        """
        Integrates real Sovereignty Center telemetry.
        """
        snapshot = sovereignty_service.get_snapshot()

        hardware = snapshot.get("hardware", {})
        runtime = snapshot.get("runtime", {})

        return {
            "timestamp": snapshot.get("timestamp"),
            "cpu": hardware.get("cpu", {}),
            "memory": hardware.get("memory", {}),
            "gpu": hardware.get("gpu", {}),
            "model_runtime": runtime,
            "storage": snapshot.get("storage", {}),
        }
    def get_recent_activity(
        self,
        limit: int = 20,
        query: Optional[str] = None,
        category: Optional[str] = None,
        service: Optional[str] = None,
        status: Optional[str] = None,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_dt, end_dt, _ = self.resolve_date_range("custom", custom_start, custom_end)
        events = self._get_filtered_events(
            query=query,
            category=category,
            service=service,
            status=status,
            model=model,
            task_type=task_type,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        return events[: max(1, min(limit, 100))]

    def get_top_actions(
        self,
        limit: int = 10,
        range_key: str = "24h",
        query: Optional[str] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_dt, end_dt, _ = self.resolve_date_range(range_key, custom_start, custom_end)
        events = self._get_filtered_events(query=query, start_dt=start_dt, end_dt=end_dt)

        counts: Dict[str, int] = {}
        for ev in events:
            act = str(ev.get("action", "unknown")).lower()
            counts[act] = counts.get(act, 0) + 1

        result = []
        for act, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]:
            result.append({"action": act, "count": cnt})

        return result

    # ---------------------------------------------------------------------
    # FULL DASHBOARD PAYLOAD (SINGLE FLIGHT REFRESH)
    # ---------------------------------------------------------------------

    def get_full_dashboard(
        self,
        range_key: str = "24h",
        query: Optional[str] = None,
        category: Optional[str] = None,
        service: Optional[str] = None,
        status: Optional[str] = None,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Return the complete Analytics Center snapshot in a single backend call.
        """
        start_dt, end_dt, active_range = self.resolve_date_range(
            range_key, custom_start, custom_end
        )

        summary = self.get_summary(
            range_key=active_range,
            query=query,
            category=category,
            service=service,
            status=status,
            model=model,
            task_type=task_type,
            custom_start=custom_start,
            custom_end=custom_end,
        )

        trends = self.get_activity_trends(
            range_key=active_range,
            query=query,
            category=category,
            service=service,
            status=status,
            model=model,
            task_type=task_type,
            custom_start=custom_start,
            custom_end=custom_end,
        )

        categories = self.get_categories_breakdown(
            range_key=active_range, query=query, custom_start=custom_start, custom_end=custom_end
        )

        services = self.get_services_breakdown(
            range_key=active_range, query=query, custom_start=custom_start, custom_end=custom_end
        )

        models = self.get_models_breakdown(
            range_key=active_range, query=query, custom_start=custom_start, custom_end=custom_end
        )

        task_types = self.get_task_types_breakdown(
            range_key=active_range, query=query, custom_start=custom_start, custom_end=custom_end
        )

        statuses = self.get_statuses_breakdown(
            range_key=active_range, query=query, custom_start=custom_start, custom_end=custom_end
        )

        latency = self.get_latency_analytics(
            range_key=active_range, query=query, custom_start=custom_start, custom_end=custom_end
        )

        missions = self.get_missions_analytics(
            range_key=active_range, custom_start=custom_start, custom_end=custom_end
        )

        knowledge = self.get_knowledge_analytics(
            range_key=active_range, custom_start=custom_start, custom_end=custom_end
        )

        artifacts = self.get_artifacts_analytics(
            range_key=active_range, custom_start=custom_start, custom_end=custom_end
        )

        network = self.get_network_analytics()
        resources = self.get_resource_analytics()

        recent_activity = self.get_recent_activity(
            limit=25,
            query=query,
            category=category,
            service=service,
            status=status,
            model=model,
            task_type=task_type,
            custom_start=custom_start,
            custom_end=custom_end,
        )

        top_actions = self.get_top_actions(
            limit=10,
            range_key=active_range,
            query=query,
            custom_start=custom_start,
            custom_end=custom_end,
        )

        return {
            "summary": summary,
            "trends": trends,
            "categories": categories,
            "services": services,
            "models": models,
            "task_types": task_types,
            "statuses": statuses,
            "latency": latency,
            "missions": missions,
            "knowledge": knowledge,
            "artifacts": artifacts,
            "network": network,
            "resources": resources,
            "recent_activity": recent_activity,
            "top_actions": top_actions,
            "active_filters": {
                "range_key": active_range,
                "query": query,
                "category": category,
                "service": service,
                "status": status,
                "model": model,
                "task_type": task_type,
                "custom_start": custom_start,
                "custom_end": custom_end,
            },
            "timestamp": _iso_now(),
        }


analytics_service = AnalyticsService()

__all__ = [
    "AnalyticsService",
    "analytics_service",
]

