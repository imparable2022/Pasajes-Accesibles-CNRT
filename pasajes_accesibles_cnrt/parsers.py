from __future__ import annotations

import re
from datetime import date
from bs4 import BeautifulSoup

from .models import ConfirmationSummary, RequestRecord, SearchConstraints, Service


def _clean(text: str) -> str:
    # Los HTML copiados desde algunos visores pueden traer números de línea como líneas independientes.
    text = re.sub(r"(?m)^\s*\d+\s*$", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def parse_constraints(html: str) -> SearchConstraints:
    hours = re.search(r"cantidadHorasReserva\s*=\s*['\"](\d+)['\"]", html)
    days = re.search(r"cantidadDiasReserva\s*=\s*['\"](\d+)['\"]", html)
    return SearchConstraints(
        min_hours=int(hours.group(1)) if hours else 48,
        max_days=int(days.group(1)) if days else 30,
    )


def parse_available_services(html: str, travel_date: date) -> list[Service]:
    soup = BeautifulSoup(html, "html.parser")
    result: list[Service] = []
    for radio in soup.select("input[name='servicioARealizar_horario']"):
        value = radio.get("value", "")
        if not value:
            continue
        container = radio.find_parent(id=re.compile(r"^id_")) or radio.parent
        label = None
        radio_id = radio.get("id")
        if radio_id:
            label = soup.find("label", attrs={"for": radio_id})
        label_text = _clean(label.get_text(" ", strip=True) if label else container.get_text(" ", strip=True))
        departure = _first(label_text, r"Sale\s+(\d{1,2}:\d{2})")
        arrival = _first(label_text, r"Llega\s+(\d{1,2}:\d{2})")
        category = _first(label_text, r"Categor(?:í|&iacute;|i)a:\s*([^:]+?)(?=\s+(?:\d+\s+)*Solicitados:|\s+(?:\d+\s+)*Cupo Total:|$)") or "Sin categoría informada"
        category = re.sub(r"\s+\d+$", "", category).strip()
        requested = _int_or_none(_first(label_text, r"Solicitados:\s*(\d+)"))
        total = _int_or_none(_first(label_text, r"Cupo Total:\s*(\d+)"))

        company = "Empresa no informada"
        if container:
            # En la página real, el nombre de empresa está antes del label del servicio.
            direct_text = []
            for child in container.children:
                if getattr(child, "name", None) == "input":
                    continue
                if getattr(child, "name", None) == "div" and child.find("label"):
                    break
                if isinstance(child, str):
                    t = _clean(child)
                    if t and not t.isdigit():
                        direct_text.append(t)
                elif getattr(child, "get_text", None) and not child.find("label"):
                    t = _clean(child.get_text(" ", strip=True))
                    if t and not t.isdigit():
                        direct_text.append(t)
            if direct_text:
                company = direct_text[-1]
            else:
                text = _clean(container.get_text(" ", strip=True))
                m = re.search(r"(?:^|\s)(.+?)\s+Sale\s+\d{1,2}:\d{2}", text)
                if m:
                    candidate = _clean(m.group(1))
                    candidate = re.sub(r"^\d+\s+", "", candidate)
                    if candidate:
                        company = candidate

        info_node = container.select_one("input#infoservicio") if container else None
        info = info_node.get("value", "") if info_node else ""
        service_id = value.split("_", 1)[0]
        result.append(
            Service(
                date=travel_date,
                company=company,
                departure=departure or "--:--",
                arrival=arrival or "--:--",
                category=category.strip(),
                requested=requested,
                total_quota=total,
                service_id=service_id,
                radio_value=value,
                info=info,
            )
        )
    return result


def parse_confirmation_summary(html: str) -> ConfirmationSummary:
    soup = BeautifulSoup(html, "html.parser")
    fields: dict[str, str] = {}
    for dd in soup.find_all("dd"):
        strong = dd.find("strong")
        if not strong:
            continue
        label = _clean(strong.get_text(" ", strip=True)).rstrip(":")
        full = _clean(dd.get_text(" ", strip=True))
        value = full
        if label:
            m = re.search(re.escape(label) + r"\s*:\s*(.*)$", full, flags=re.I)
            if m:
                value = re.sub(r"\s+", " ", m.group(1)).strip()
        fields[label.casefold()] = value

    text = _clean(soup.get_text(" ", strip=True))

    def f(label: str) -> str:
        value = fields.get(label.casefold(), "")
        return f"{label}: {value}" if value else ""

    return ConfirmationSummary(
        origin=f("Origen"),
        destination=f("Destino"),
        date_text=f("Fecha de Salida"),
        departure=f("Horario de Salida"),
        quantity=f("Cantidad de Pasajes"),
        company=f("Empresa"),
        preference=f("Preferencia Viaje"),
        raw_text=text,
    )


def parse_alerts(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    alerts = []
    for node in soup.select(".alert-danger, .alert-warning"):
        text = _clean(node.get_text(" ", strip=True))
        if text and text not in alerts:
            alerts.append(text)
    return alerts


def is_confirmed(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return "Solicitud Confirmada" in soup.get_text(" ", strip=True)



def parse_request_records(html: str, base_url: str = "") -> list[RequestRecord]:
    """Parsea la tabla real de "Mis Solicitudes" de CNRT.

    No asocia acciones por posición: cada fila conserva los href que CNRT
    generó específicamente para esa reserva.
    """
    from urllib.parse import parse_qs, urljoin, urlparse

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table#reservar") or soup.find("table")
    if not table:
        return []

    headers = [_clean(th.get_text(" ", strip=True)).casefold() for th in table.select("thead th")]

    def idx(*needles: str) -> int | None:
        for i, header in enumerate(headers):
            if all(n.casefold() in header for n in needles):
                return i
        return None

    positions = {
        "origin": idx("origen"),
        "destination": idx("destino"),
        "company": idx("empresa"),
        "date_text": idx("fecha", "salida"),
        "departure": idx("horario", "salida"),
        "email": idx("email"),
        "quantity": idx("cantidad", "reservada"),
        "status": idx("estado"),
    }

    def value(cells, key: str) -> str:
        pos = positions.get(key)
        return _clean(cells[pos].get_text(" ", strip=True)) if pos is not None and pos < len(cells) else ""

    def full_url(href: str) -> str:
        return urljoin(base_url, href) if base_url else href

    def reservation_id_from(*hrefs: str) -> str:
        for href in hrefs:
            if not href:
                continue
            m = re.search(r"/(?:modificarEmail|editarPreferenciaViaje)/(\\d+)", href)
            if m:
                return m.group(1)
            try:
                br = parse_qs(urlparse(href).query).get("br", [])
                if br:
                    return br[0]
            except Exception:
                pass
        return ""

    records: list[RequestRecord] = []
    body = table.select_one("tbody")
    groups: list[list] = []
    if body:
        # HTML normal: una fila <tr> por reserva.
        for row in body.find_all("tr", recursive=False):
            cells = row.find_all("td", recursive=False) or row.find_all("td")
            if cells:
                groups.append(cells)
        # Los HTML copiados por algunos visores pierden los <tr> de filas posteriores
        # y dejan sus <td> directamente dentro de <tbody>. Los reconstruimos usando
        # la cantidad de columnas que CNRT publica en el encabezado.
        orphan = body.find_all("td", recursive=False)
        width = len(headers) or 12
        for i in range(0, len(orphan), width):
            chunk = orphan[i:i + width]
            if len(chunk) == width:
                groups.append(chunk)
    else:
        for row in table.find_all("tr"):
            cells = row.find_all("td", recursive=False) or row.find_all("td")
            if cells:
                groups.append(cells)

    def find_link(cells, selector: str):
        for cell in cells:
            node = cell.select_one(selector)
            if node:
                return node
        return None

    for cells in groups:
        modify_email = find_link(cells, "a[href*='/web/modificarEmail/']")
        modify_pref = find_link(cells, "a[href*='/web/editarPreferenciaViaje/']")
        cancel = find_link(cells, "a[href*='anular=1']")
        email_href = full_url(modify_email.get("href", "")) if modify_email else ""
        pref_href = full_url(modify_pref.get("href", "")) if modify_pref else ""
        cancel_href = full_url(cancel.get("href", "")) if cancel else ""
        rid = reservation_id_from(email_href, pref_href, cancel_href)
        raw = _clean(" ".join(c.get_text(" ", strip=True) for c in cells))

        records.append(RequestRecord(
            reservation_id=rid,
            origin=value(cells, "origin"),
            destination=value(cells, "destination"),
            company=value(cells, "company"),
            date_text=value(cells, "date_text"),
            departure=value(cells, "departure"),
            email=value(cells, "email"),
            quantity=value(cells, "quantity"),
            status=value(cells, "status"),
            modify_email_url=email_href,
            modify_preference_url=pref_href,
            cancel_url=cancel_href,
            raw_text=raw,
        ))
    return records


def _first(text: str, pattern: str) -> str:
    m = re.search(pattern, text, flags=re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _int_or_none(value: str):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _field(text: str, label: str) -> str:
    labels = [
        "Destino",
        "Origen",
        "Fecha de Salida",
        "Preferencia Viaje",
        "Horario de Salida",
        "Cantidad de Pasajes",
        "Retira el Titular",
        "Empresa",
        "Email",
    ]
    escaped = "|".join(re.escape(x) for x in labels if x != label)
    m = re.search(rf"{re.escape(label)}\s*:\s*(.+?)(?=\s+(?:{escaped})\s*:|$)", text, flags=re.I)
    if not m:
        return ""
    return f"{label}: {_clean(m.group(1))}"
