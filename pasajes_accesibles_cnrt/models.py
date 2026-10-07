from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class Locality:
    id: str
    text: str

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True)
class SearchConstraints:
    min_hours: int = 48
    max_days: int = 30


@dataclass(frozen=True)
class Service:
    date: date
    company: str
    departure: str
    arrival: str
    category: str
    requested: Optional[int]
    total_quota: Optional[int]
    service_id: str
    radio_value: str
    info: str = ""

    @property
    def free_quota(self) -> Optional[int]:
        if self.requested is None or self.total_quota is None:
            return None
        return max(self.total_quota - self.requested, 0)

    def display_text(self) -> str:
        free = ""
        if self.free_quota is not None:
            free = f", cupo libre estimado {self.free_quota}"
        return (
            f"{self.date.strftime('%d/%m/%Y')} - {self.company}. "
            f"Sale {self.departure}, llega {self.arrival}. {self.category}{free}."
        )


@dataclass
class ScanResult:
    services: list[Service] = field(default_factory=list)
    scanned_dates: int = 0
    errors: list[str] = field(default_factory=list)
    cancelled: bool = False

    @property
    def available_dates(self) -> int:
        return len({s.date for s in self.services})


@dataclass(frozen=True)
class ConfirmationSummary:
    origin: str = ""
    destination: str = ""
    date_text: str = ""
    departure: str = ""
    quantity: str = ""
    company: str = ""
    preference: str = ""
    raw_text: str = ""

    def spoken_summary(self) -> str:
        parts = [
            self.origin,
            self.destination,
            self.date_text,
            self.departure,
            self.company,
            self.quantity,
            self.preference,
        ]
        return ". ".join(p for p in parts if p)


@dataclass(frozen=True)
class Profile:
    phone: str = ""
    email: str = ""


@dataclass(frozen=True)
class RequestRecord:
    reservation_id: str = ""
    origin: str = ""
    destination: str = ""
    company: str = ""
    date_text: str = ""
    departure: str = ""
    email: str = ""
    quantity: str = ""
    status: str = ""
    modify_email_url: str = ""
    modify_preference_url: str = ""
    cancel_url: str = ""
    raw_text: str = ""

    @property
    def cancellable(self) -> bool:
        return bool(self.cancel_url)

    @property
    def can_modify_email(self) -> bool:
        return bool(self.modify_email_url)

    @property
    def can_modify_preference(self) -> bool:
        return bool(self.modify_preference_url)

    @property
    def text(self) -> str:
        parts = [
            f"{self.origin} → {self.destination}" if self.origin or self.destination else "Solicitud",
            self.date_text,
            self.departure,
            self.company,
            f"{self.quantity} pasaje{'s' if self.quantity != '1' else ''}" if self.quantity else "",
            f"Estado: {self.status}" if self.status else "",
        ]
        return ". ".join(x for x in parts if x)

    def spoken_details(self) -> str:
        parts = [self.text, f"Correo: {self.email}" if self.email else ""]
        return ". ".join(x for x in parts if x)
