from __future__ import annotations

import os
import re
import sys
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from .errors import AvailabilityChangedError, CnrtError, LoginError, SessionExpiredError, StructureChangedError
from .models import ConfirmationSummary, Locality, Profile, RequestRecord, ScanResult, SearchConstraints, Service
from .parsers import is_confirmed, parse_alerts, parse_available_services, parse_confirmation_summary, parse_constraints, parse_request_records
from .storage import LocalityCache

BASE_URL = "https://reservapasajes.cnrt.gob.ar"
LOGIN_URL = f"{BASE_URL}/web/ingresar"


def _configure_bundled_playwright_browser() -> None:
    """Hace visible Chromium incluido junto al ejecutable oficial."""
    if not getattr(sys, "frozen", False):
        return
    bundled = Path(sys.executable).resolve().parent / "ms-playwright"
    if bundled.is_dir():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(bundled))


class CnrtClient:
    """Cliente de alto nivel. Debe usarse siempre desde el mismo hilo."""

    def __init__(self, headless: bool = True, slow_mo: int = 0):
        self.headless = headless
        self.slow_mo = slow_mo
        self._pw: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.search_url: Optional[str] = None
        self.requests_url: Optional[str] = None
        self.info_url: Optional[str] = None
        self.locality_cache = LocalityCache()
        self._last_constraints = SearchConstraints()

    def start(self):
        if self.page is not None:
            return
        _configure_bundled_playwright_browser()
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
        self.context = self.browser.new_context(locale="es-AR")
        self.page = self.context.new_page()
        self.page.set_default_timeout(20000)
        self.page.goto(LOGIN_URL, wait_until="domcontentloaded")
        self._assert_login_structure()

    def close(self):
        try:
            if self.context:
                self.context.close()
        finally:
            try:
                if self.browser:
                    self.browser.close()
            finally:
                if self._pw:
                    self._pw.stop()
        self._pw = None
        self.browser = None
        self.context = None
        self.page = None

    def login(
        self,
        document_type: str,
        document_number: str,
        credential_type: str,
        credential_number: str = "",
        sex: str = "1",
    ) -> str:
        self._ensure_started()
        p = self.page
        assert p is not None
        p.goto(LOGIN_URL, wait_until="domcontentloaded")
        self._assert_login_structure()
        p.select_option("#documentoOpciones", document_type)
        p.fill("#nroDocumento", document_number.strip())
        p.check(f"input[name='tipoCredencial'][value='{credential_type}']")
        if credential_type == "MUNICIPAL":
            if p.locator("#sexo").count():
                p.select_option("#sexo", sex)
        else:
            p.fill("#nroCredencial", credential_number.strip())
        p.locator("#ingreso button[type='submit']").click()
        p.wait_for_load_state("domcontentloaded")
        html = p.content()
        if p.locator("#ingreso").count() and not p.locator("a[href*='buscarServicios']").count():
            alerts = parse_alerts(html)
            detail = "; ".join(alerts) if alerts else "CNRT no aceptó los datos de ingreso."
            raise LoginError(detail)
        self._capture_navigation_urls()
        self._refresh_constraints()
        return "Sesión iniciada correctamente."

    def logout(self):
        self._ensure_session()
        p = self.page
        assert p is not None
        link = p.locator("a[href='/web/ingresar']")
        if link.count():
            link.first.click()
            p.wait_for_load_state("domcontentloaded")
        else:
            p.goto(LOGIN_URL, wait_until="domcontentloaded")
        self.search_url = self.requests_url = self.info_url = None

    def get_constraints(self) -> SearchConstraints:
        self._ensure_session()
        self._refresh_constraints()
        return self._last_constraints

    def allowed_date_range(self, now: Optional[datetime] = None) -> tuple[date, date]:
        constraints = self.get_constraints()
        now = now or datetime.now()
        start = (now + timedelta(hours=constraints.min_hours)).date()
        end = (now + timedelta(days=constraints.max_days)).date()
        if end < start:
            end = start
        return start, end

    def search_localities(self, query: str, max_pages: int = 4) -> list[Locality]:
        self._ensure_session()
        query = query.strip()
        if not query:
            return []
        cached = self.locality_cache.search(query, limit=40)
        found = {x.id: x for x in cached}
        assert self.context is not None
        for page_no in range(1, max_pages + 1):
            response = self.context.request.get(
                f"{BASE_URL}/web/getLocalidades",
                params={"q": query, "page": str(page_no)},
                fail_on_status_code=False,
            )
            if response.status in (401, 403):
                raise SessionExpiredError("La sesión de CNRT venció.")
            if response.status >= 400:
                raise CnrtError(f"CNRT respondió HTTP {response.status} al buscar localidades.")
            try:
                payload = response.json()
            except Exception as exc:
                raise StructureChangedError("CNRT no devolvió la lista de localidades en formato JSON.") from exc
            items = payload.get("items", []) if isinstance(payload, dict) else []
            batch: list[Locality] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                loc_id = str(item.get("id", "")).strip()
                text = str(item.get("text", item.get("nombre", ""))).strip()
                if loc_id and text:
                    loc = Locality(loc_id, text)
                    found[loc.id] = loc
                    batch.append(loc)
            if batch:
                self.locality_cache.add_many(batch)
            if len(items) < 30:
                break
        return sorted(found.values(), key=lambda x: x.text.casefold())[:100]

    def scan_availability(
        self,
        origin: Locality,
        destination: Locality,
        quantity: int = 1,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        delay_seconds: float = 0.9,
        progress: Optional[Callable[[int, int, date, int], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> ScanResult:
        self._ensure_session()
        min_date, max_date = self.allowed_date_range()
        start_date = max(start_date or min_date, min_date)
        end_date = min(end_date or max_date, max_date)
        if end_date < start_date:
            raise ValueError("El rango de fechas no se encuentra dentro del período permitido por CNRT.")
        total = (end_date - start_date).days + 1
        result = ScanResult()
        current = start_date
        for idx in range(total):
            if cancel_event and cancel_event.is_set():
                result.cancelled = True
                break
            try:
                html = self._post_search(origin, destination, current, quantity)
                services = parse_available_services(html, current)
                result.services.extend(services)
            except Exception as exc:
                result.errors.append(f"{current.strftime('%d/%m/%Y')}: {exc}")
                services = []
            result.scanned_dates += 1
            if progress:
                progress(idx + 1, total, current, len(services))
            current += timedelta(days=1)
            if idx + 1 < total and delay_seconds > 0:
                time.sleep(max(0.0, delay_seconds))
        result.services.sort(key=lambda s: (s.date, s.departure, s.company.casefold()))
        return result

    def prepare_reservation(
        self,
        origin: Locality,
        destination: Locality,
        service: Service,
        quantity: int,
        preference: str = "1",
        preference_reason: str = "",
    ) -> ConfirmationSummary:
        self._ensure_session()
        # Revalidación en vivo antes de tocar el formulario de reserva.
        live_html = self._post_search(origin, destination, service.date, quantity)
        live = {s.radio_value: s for s in parse_available_services(live_html, service.date)}
        if service.radio_value not in live:
            raise AvailabilityChangedError(
                "El servicio seleccionado ya no aparece disponible. Vuelva a escanear la fecha."
            )
        self._open_search_page()
        p = self.page
        assert p is not None
        self._set_select2("#origen", origin)
        self._set_select2("#destino", destination)
        p.fill("#fechaSalida", service.date.strftime("%d-%m-%Y"))
        qty_value = "dos" if quantity == 2 else "uno"
        p.check(f"input[name='cantidadPasajes'][value='{qty_value}']")
        p.locator("#reservar button[type='submit']").click()
        p.wait_for_load_state("domcontentloaded")
        selector = f"input[name='servicioARealizar_horario'][value='{service.radio_value}']"
        if not p.locator(selector).count():
            raise AvailabilityChangedError("El servicio dejó de estar disponible durante la selección.")
        p.check(selector)
        if p.locator("input[name='preferenciaViaje']").count():
            target = p.locator(f"input[name='preferenciaViaje'][value='{preference}']")
            if target.count():
                target.check()
        if p.locator("#motivoPreferencia").count():
            p.fill("#motivoPreferencia", preference_reason[:30])
        if p.locator("#enviarDatos").count():
            p.locator("#enviarDatos").click()
        else:
            p.locator("#reservar").evaluate("form => form.submit()")
        p.wait_for_load_state("domcontentloaded")
        html = p.content()
        if not p.locator("form[action*='confirmarReserva']").count():
            alerts = parse_alerts(html)
            raise StructureChangedError(
                "; ".join(alerts) if alerts else "CNRT no mostró la pantalla esperada de confirmación."
            )
        return parse_confirmation_summary(html)

    def confirm_reservation(self, email: str) -> ConfirmationSummary:
        self._ensure_session()
        p = self.page
        assert p is not None
        if not p.locator("form[action*='confirmarReserva']").count():
            raise StructureChangedError("No está abierta la pantalla de confirmación de una reserva.")
        email = email.strip()
        p.fill("#mail", email)
        p.fill("#mail2", email)
        p.locator("form[action*='confirmarReserva'] button[type='submit']").click()
        p.wait_for_load_state("domcontentloaded")
        html = p.content()
        if not is_confirmed(html):
            alerts = parse_alerts(html)
            raise CnrtError("; ".join(alerts) if alerts else "CNRT no confirmó la solicitud.")
        return parse_confirmation_summary(html)

    def get_profile(self) -> Profile:
        self._ensure_session()
        self._open_info_page()
        p = self.page
        assert p is not None
        phone = p.locator("#nroTelefono").input_value() if p.locator("#nroTelefono").count() else ""
        email = p.locator("#email").input_value() if p.locator("#email").count() else ""
        return Profile(phone=phone, email=email)

    def update_profile(self, phone: str, email: str) -> Profile:
        self._ensure_session()
        self._open_info_page()
        p = self.page
        assert p is not None
        if not p.locator("#informacion").count():
            raise StructureChangedError("No se encontró el formulario Mi Información.")
        p.fill("#nroTelefono", phone.strip())
        current_email = p.locator("#email").input_value() if p.locator("#email").count() else ""
        p.fill("#email", email.strip())
        if email.strip() != current_email.strip() and p.locator("#verifica_email").count():
            # El campo se muestra al enfocar el correo; Playwright puede completarlo aunque esté oculto si forzamos fill vía JS.
            p.locator("#verifica_email").evaluate("(el, value) => { el.value=value; }", email.strip())
        p.locator("#informacion button[type='submit']").click()
        p.wait_for_load_state("domcontentloaded")
        html = p.content()
        if "Los datos fueron actualizados correctamente" not in BeautifulSoup(html, "html.parser").get_text(" ", strip=True):
            alerts = parse_alerts(html)
            if alerts:
                raise CnrtError("; ".join(alerts))
        return self.get_profile()

    def list_requests(self) -> list[RequestRecord]:
        self._ensure_session()
        if not self.requests_url:
            raise StructureChangedError("CNRT no publicó el enlace Mis Solicitudes.")
        p = self.page
        assert p is not None
        p.goto(self.requests_url, wait_until="domcontentloaded")
        if p.locator("#ingreso").count():
            raise SessionExpiredError("La sesión de CNRT venció.")
        records = parse_request_records(p.content(), BASE_URL)
        if not records and p.locator("table#reservar").count():
            # Tabla válida pero sin filas: simplemente no hay solicitudes.
            return []
        if not records:
            raise StructureChangedError("No se pudo interpretar la tabla Mis Solicitudes de CNRT.")
        return records

    def modify_request_email(self, record: RequestRecord, new_email: str) -> str:
        self._ensure_session()
        if not record.modify_email_url:
            raise StructureChangedError("CNRT no permite modificar el correo de esta solicitud.")
        email = new_email.strip()
        if not email or "@" not in email:
            raise ValueError("Ingrese un correo electrónico válido.")
        p = self.page
        assert p is not None
        p.goto(record.modify_email_url, wait_until="domcontentloaded")
        if not p.locator("#email_email").count() or not p.locator("#email_save").count():
            raise StructureChangedError("Cambió la pantalla Modificar Email de CNRT.")
        p.fill("#email_email", email)
        p.locator("#email_save").click()
        p.wait_for_load_state("domcontentloaded")
        alerts = parse_alerts(p.content())
        if alerts:
            raise CnrtError("; ".join(alerts))

        # Verificación independiente contra Mis Solicitudes.
        refreshed = self.list_requests()
        current = self._find_request(refreshed, record)
        if current and current.email.casefold() == email.casefold():
            return "El correo de la solicitud fue actualizado y verificado en Mis Solicitudes."
        if current:
            raise CnrtError("CNRT procesó el formulario, pero Mis Solicitudes todavía no muestra el nuevo correo.")
        return "CNRT procesó el cambio de correo. La solicitud ya no apareció con el mismo identificador al verificarla."

    def modify_request_preference(self, record: RequestRecord, preference: str, reason: str = "") -> str:
        self._ensure_session()
        if not record.modify_preference_url:
            raise StructureChangedError("CNRT no permite modificar la preferencia de esta solicitud.")
        if preference not in {"1", "2"}:
            raise ValueError("La preferencia debe ser planta baja o planta alta.")
        p = self.page
        assert p is not None
        p.goto(record.modify_preference_url, wait_until="domcontentloaded")
        if not p.locator("form#preferencia").count():
            raise StructureChangedError("Cambió la pantalla Modificar Preferencia Viaje de CNRT.")
        target = p.locator(f"input[name='preferenciaViaje'][value='{preference}']")
        if not target.count():
            raise StructureChangedError("CNRT no mostró las opciones de planta baja/alta esperadas.")
        target.check()
        if p.locator("#motivoPreferencia").count():
            p.fill("#motivoPreferencia", reason[:30])
        p.locator("form#preferencia button[type='submit']").click()
        p.wait_for_load_state("domcontentloaded")
        alerts = parse_alerts(p.content())
        if alerts:
            raise CnrtError("; ".join(alerts))

        # Reabrimos la pantalla oficial y comprobamos qué radio deja marcado CNRT.
        p.goto(record.modify_preference_url, wait_until="domcontentloaded")
        selected = p.locator(f"input[name='preferenciaViaje'][value='{preference}']")
        if selected.count() and selected.is_checked():
            label = "planta baja" if preference == "1" else "planta alta"
            return f"La preferencia fue actualizada y verificada como {label}."
        raise CnrtError("CNRT procesó el formulario, pero no fue posible verificar la nueva preferencia.")

    def cancel_request(self, record: RequestRecord) -> str:
        self._ensure_session()
        if not record.cancel_url:
            raise StructureChangedError("CNRT no permite anular esta solicitud.")
        p = self.page
        assert p is not None
        # El href oficial es la acción que ejecuta CNRT; la confirmación humana se realiza en la interfaz propia.
        p.goto(record.cancel_url, wait_until="domcontentloaded")
        alerts = parse_alerts(p.content())
        if alerts:
            raise CnrtError("; ".join(alerts))
        refreshed = self.list_requests()
        current = self._find_request(refreshed, record)
        if current is None:
            return "La solicitud dejó de aparecer en Mis Solicitudes después de la anulación."
        state = current.status.casefold()
        if "anulad" in state or "cancelad" in state or not current.cancel_url:
            return f"La anulación fue verificada en CNRT. Estado: {current.status or 'sin acción Anular disponible'}."
        raise CnrtError(f"CNRT respondió a la anulación, pero la solicitud todavía figura como {current.status or 'activa'}.")

    @staticmethod
    def _find_request(records: list[RequestRecord], previous: RequestRecord) -> RequestRecord | None:
        if previous.reservation_id:
            for r in records:
                if r.reservation_id == previous.reservation_id:
                    return r
        # Respaldo para registros históricos sin identificador visible.
        for r in records:
            if (r.origin, r.destination, r.date_text, r.departure, r.company) == (
                previous.origin, previous.destination, previous.date_text, previous.departure, previous.company
            ):
                return r
        return None

    # ----------------- internos -----------------

    def _post_search(self, origin: Locality, destination: Locality, day: date, quantity: int) -> str:
        self._ensure_session()
        token, beneficiary = self._session_form_values()
        assert self.context is not None
        form = {
            "token": token,
            "beneficiarioCnrtId": beneficiary,
            "origen": origin.id,
            "destino": destination.id,
            "fechaSalida": day.strftime("%d-%m-%Y"),
            "cantidadPasajes": "dos" if quantity == 2 else "uno",
        }
        response = self.context.request.post(
            f"{BASE_URL}/web/buscarServicios", form=form, fail_on_status_code=False
        )
        if response.status in (401, 403):
            raise SessionExpiredError("La sesión de CNRT venció durante el escaneo.")
        if response.status >= 400:
            raise CnrtError(f"CNRT respondió HTTP {response.status} para {day.strftime('%d/%m/%Y')}.")
        text = response.text()
        if "id=\"ingreso\"" in text and "Número de Documento" in text:
            raise SessionExpiredError("La sesión de CNRT venció durante el escaneo.")
        return text

    def _session_form_values(self) -> tuple[str, str]:
        self._open_search_page()
        p = self.page
        assert p is not None
        token = p.locator("#token").input_value() if p.locator("#token").count() else ""
        beneficiary = p.locator("#beneficiarioCnrtId").input_value() if p.locator("#beneficiarioCnrtId").count() else ""
        if not token or not beneficiary:
            raise SessionExpiredError("No se pudieron recuperar los datos de la sesión de CNRT.")
        return token, beneficiary

    def _refresh_constraints(self):
        self._open_search_page()
        assert self.page is not None
        self._last_constraints = parse_constraints(self.page.content())

    def _open_search_page(self):
        self._ensure_session()
        p = self.page
        assert p is not None
        if not self.search_url:
            self._capture_navigation_urls()
        if not self.search_url:
            raise SessionExpiredError("No se encontró el enlace Solicitar Pasaje.")
        if "/web/buscarServicios" not in p.url or not p.locator("#reservar").count():
            p.goto(self.search_url, wait_until="domcontentloaded")
        if p.locator("#ingreso").count():
            raise SessionExpiredError("La sesión de CNRT venció.")

    def _open_info_page(self):
        self._ensure_session()
        p = self.page
        assert p is not None
        if not self.info_url:
            self._capture_navigation_urls()
        if not self.info_url:
            raise StructureChangedError("CNRT no publicó el enlace Mi información.")
        p.goto(self.info_url, wait_until="domcontentloaded")

    def _capture_navigation_urls(self):
        p = self.page
        assert p is not None
        for href in p.locator("a").evaluate_all("els => els.map(e => ({href:e.href,text:(e.innerText||'').trim()}))"):
            text = href.get("text", "").casefold()
            url = href.get("href", "")
            if "solicitar pasaje" in text and "buscarServicios" in url:
                self.search_url = url
            elif "mis solicitudes" in text or "/web/consultar" in url:
                self.requests_url = url
            elif "mi información" in text or "mi informacion" in text or "/web/miInformacion" in url:
                self.info_url = url
        if not self.search_url:
            loc = p.locator("a[href*='buscarServicios']")
            if loc.count():
                self.search_url = urljoin(p.url, loc.first.get_attribute("href"))

    def _set_select2(self, selector: str, locality: Locality):
        p = self.page
        assert p is not None
        p.evaluate(
            """([selector, id, text]) => {
                const sel = document.querySelector(selector);
                if (!sel) throw new Error('select no encontrado: ' + selector);
                sel.innerHTML = '';
                const option = new Option(text, id, true, true);
                sel.appendChild(option);
                if (window.jQuery) window.jQuery(sel).trigger('change');
                else sel.dispatchEvent(new Event('change', {bubbles:true}));
            }""",
            [selector, locality.id, locality.text],
        )

    def _assert_login_structure(self):
        p = self.page
        assert p is not None
        required = ["#ingreso", "#documentoOpciones", "#nroDocumento", "input[name='tipoCredencial']"]
        missing = [sel for sel in required if not p.locator(sel).count()]
        if missing:
            raise StructureChangedError(
                "La pantalla de ingreso de CNRT cambió. Faltan controles esperados: " + ", ".join(missing)
            )

    def _ensure_started(self):
        if self.page is None:
            self.start()

    def _ensure_session(self):
        self._ensure_started()
        if not self.search_url and self.page and self.page.locator("#ingreso").count():
            raise SessionExpiredError("Primero debe iniciar sesión en CNRT.")


def _node_label(tag) -> str:
    if tag.name == "input":
        return str(tag.get("value", ""))
    return tag.get_text(" ", strip=True)
