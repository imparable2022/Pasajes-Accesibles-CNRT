from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .models import RequestRecord
from .storage import APP_DIR

TRACKING_FILE = APP_DIR / "telemetry_reservations.json"
MAX_ENTRIES = 5000

STATE_CREATED = "created"
STATE_ACTIVE = "active"
STATE_TICKET_ISSUED = "ticket_issued"
STATE_CANCELLED = "cancelled"
STATE_OTHER = "other"

EVENT_BY_STATE = {
    STATE_ACTIVE: "reservation_active",
    STATE_TICKET_ISSUED: "reservation_ticket_issued",
    STATE_CANCELLED: "reservation_cancelled",
    STATE_OTHER: "reservation_status_other",
}


def normalize_travel_date(value: str) -> str:
    text = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return text[:32]


def normalize_cnrt_status(status: str, *, cancellable: bool = False) -> str:
    text = " ".join((status or "").casefold().split())
    if "pasaje emitido" in text:
        return STATE_TICKET_ISSUED
    if "anulad" in text or "cancelad" in text:
        return STATE_CANCELLED
    if "activa" in text or cancellable:
        return STATE_ACTIVE
    return STATE_OTHER


def event_name_for_state(state: str) -> str:
    return EVENT_BY_STATE.get(state, "reservation_status_other")


def _normalized_piece(value: str) -> str:
    return " ".join((value or "").casefold().split())


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _fingerprint(*, company: str, origin: str, destination: str, travel_date: str, departure: str = "", quantity: str = "") -> str:
    pieces = (
        _normalized_piece(company),
        _normalized_piece(origin),
        _normalized_piece(destination),
        normalize_travel_date(travel_date),
        _normalized_piece(departure),
        _normalized_piece(quantity),
    )
    return _hash_text("trip|" + "\x1f".join(pieces))


def _record_hash(record: RequestRecord, occurrence: int = 0) -> str:
    if record.reservation_id:
        return _hash_text("cnrt-id|" + record.reservation_id.strip())
    return _hash_text(
        "fallback|"
        + _fingerprint(
            company=record.company,
            origin=record.origin,
            destination=record.destination,
            travel_date=record.date_text,
            departure=record.departure,
            quantity=record.quantity,
        )
        + f"|occurrence:{max(0, int(occurrence))}"
    )


@dataclass(frozen=True)
class ReservationStatusObservation:
    tracking_id: str
    state: str
    first_observed: bool = False


class ReservationLifecycleTracker:
    """Conserva solo hashes opacos, ID aleatorio y último estado observado."""

    def __init__(self, path: Path | None = None):
        self.path = path or TRACKING_FILE
        self._lock = threading.Lock()
        self._entries = self._load()

    def _load(self) -> list[dict[str, str]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            items = raw.get("reservations", []) if isinstance(raw, dict) else []
            result: list[dict[str, str]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                tracking_id = str(item.get("tracking_id", ""))
                if not tracking_id.startswith("reservation-"):
                    continue
                result.append(
                    {
                        "tracking_id": tracking_id,
                        "pending_hash": str(item.get("pending_hash", "")),
                        "record_hash": str(item.get("record_hash", "")),
                        "last_status": str(item.get("last_status", "")),
                        "seen_states": [
                            str(x) for x in item.get("seen_states", [])
                            if isinstance(x, str) and x
                        ],
                        "updated_at": str(item.get("updated_at", "")),
                    }
                )
            return result[-MAX_ENTRIES:]
        except Exception:
            return []

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"version": 1, "reservations": self._entries[-MAX_ENTRIES:]}
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
        except Exception:
            # El seguimiento estadístico nunca debe afectar el flujo de reservas.
            pass

    @staticmethod
    def _now() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    @staticmethod
    def _new_tracking_id() -> str:
        return f"reservation-{uuid.uuid4()}"

    def register_created(
        self,
        *,
        company: str,
        origin: str,
        destination: str,
        travel_date: str,
        departure: str = "",
        quantity: str = "",
    ) -> str:
        pending_hash = _fingerprint(
            company=company,
            origin=origin,
            destination=destination,
            travel_date=travel_date,
            departure=departure,
            quantity=quantity,
        )
        entry = {
            "tracking_id": self._new_tracking_id(),
            "pending_hash": pending_hash,
            "record_hash": "",
            "last_status": STATE_CREATED,
            "seen_states": [STATE_CREATED],
            "updated_at": self._now(),
        }
        with self._lock:
            self._entries.append(entry)
            self._entries = self._entries[-MAX_ENTRIES:]
            self._save()
        return entry["tracking_id"]

    def observe(self, record: RequestRecord, occurrence: int = 0) -> ReservationStatusObservation | None:
        record_hash = _record_hash(record, occurrence)
        pending_hash = _fingerprint(
            company=record.company,
            origin=record.origin,
            destination=record.destination,
            travel_date=record.date_text,
            departure=record.departure,
            quantity=record.quantity,
        )
        state = normalize_cnrt_status(record.status, cancellable=record.cancellable)
        with self._lock:
            entry = next((x for x in self._entries if x.get("record_hash") == record_hash), None)
            first_observed = False
            if entry is None:
                entry = next(
                    (
                        x for x in self._entries
                        if not x.get("record_hash") and x.get("pending_hash") == pending_hash
                    ),
                    None,
                )
            if entry is None:
                first_observed = True
                entry = {
                    "tracking_id": self._new_tracking_id(),
                    "pending_hash": pending_hash,
                    "record_hash": record_hash,
                    "last_status": "",
                    "seen_states": [],
                    "updated_at": self._now(),
                }
                self._entries.append(entry)
            else:
                entry["record_hash"] = record_hash

            seen_states = entry.setdefault("seen_states", [])
            entry["last_status"] = state
            entry["updated_at"] = self._now()
            if state in seen_states:
                self._save()
                return None

            seen_states.append(state)
            self._entries = self._entries[-MAX_ENTRIES:]
            self._save()
            return ReservationStatusObservation(entry["tracking_id"], state, first_observed)

    def mark_cancelled(self, record: RequestRecord) -> ReservationStatusObservation | None:
        record_hash = _record_hash(record)
        pending_hash = _fingerprint(
            company=record.company,
            origin=record.origin,
            destination=record.destination,
            travel_date=record.date_text,
            departure=record.departure,
            quantity=record.quantity,
        )
        with self._lock:
            entry = next((x for x in self._entries if x.get("record_hash") == record_hash), None)
            if entry is None:
                entry = next(
                    (
                        x for x in self._entries
                        if not x.get("record_hash") and x.get("pending_hash") == pending_hash
                    ),
                    None,
                )
            first_observed = entry is None
            if entry is None:
                entry = {
                    "tracking_id": self._new_tracking_id(),
                    "pending_hash": pending_hash,
                    "record_hash": record_hash,
                    "last_status": "",
                    "seen_states": [],
                    "updated_at": self._now(),
                }
                self._entries.append(entry)
            else:
                entry["record_hash"] = record_hash

            seen_states = entry.setdefault("seen_states", [])
            entry["last_status"] = STATE_CANCELLED
            entry["updated_at"] = self._now()
            if STATE_CANCELLED in seen_states:
                self._save()
                return None

            seen_states.append(STATE_CANCELLED)
            self._entries = self._entries[-MAX_ENTRIES:]
            self._save()
            return ReservationStatusObservation(entry["tracking_id"], STATE_CANCELLED, first_observed)
