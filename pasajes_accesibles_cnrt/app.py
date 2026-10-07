from __future__ import annotations

import ctypes
import sys
import threading
import time
import uuid
from datetime import date, datetime, timedelta

import wx

from . import __version__
from .models import Locality, Profile, RequestRecord, ScanResult, Service
from .reservation_tracking import (
    ReservationLifecycleTracker,
    event_name_for_state,
    normalize_travel_date,
)
from .storage import CredentialStore
from .telemetry import TelemetryClient, collect_technical_properties
from .updater import GitHubUpdateService, UpdateError, UpdateInfo
from .worker import CnrtWorker

DOC_TYPES = [
    ("Documento Nacional de Identidad", "1"),
    ("Documento Nacional de Identidad -X-", "5"),
    ("Libreta Cívica", "3"),
    ("Libreta de Enrolamiento", "4"),
    ("Pasaporte", "2"),
]
CRED_TYPES = [
    ("Credencial CUD", "CUD"),
    ("Credencial INCUCAI", "INCUCAI"),
    ("Credencial Municipal/Provincial", "MUNICIPAL"),
]

# Paleta visual v1.2.1 orientada también a baja visión. Los tonos secundarios
# se oscurecieron para superar con margen el contraste mínimo de WCAG 2.2.
# WCAG 3.0 todavía no define el algoritmo final de contraste, por eso los
# valores numéricos se siguen verificando con WCAG 2.2 mientras se adoptan
# las recomendaciones del Editor's Draft de WCAG 3 (02-10-2026).
COLOR_BG = wx.Colour(245, 247, 250)          # #F5F7FA
COLOR_SURFACE = wx.Colour(255, 255, 255)     # #FFFFFF
COLOR_TEXT = wx.Colour(31, 41, 55)           # #1F2937
COLOR_MUTED = wx.Colour(71, 85, 105)         # #475569, 7.06:1 sobre COLOR_BG
COLOR_PRIMARY = wx.Colour(37, 99, 235)       # #2563EB, blanco 5.17:1
COLOR_PRIMARY_HOVER = wx.Colour(29, 78, 216) # #1D4ED8
COLOR_BORDER = wx.Colour(100, 116, 139)       # #64748B, 4.76:1 sobre blanco
COLOR_STATUS = wx.Colour(226, 232, 240)       # #E2E8F0
COLOR_SUCCESS = wx.Colour(22, 101, 52)        # #166534
COLOR_SUCCESS_BG = wx.Colour(220, 252, 231)   # #DCFCE7
COLOR_DANGER = wx.Colour(153, 27, 27)         # #991B1B
COLOR_DANGER_HOVER = wx.Colour(127, 29, 29)   # #7F1D1D
COLOR_DANGER_BG = wx.Colour(254, 226, 226)    # #FEE2E2
COLOR_WARNING = wx.Colour(146, 64, 14)        # #92400E
COLOR_WARNING_BG = wx.Colour(254, 243, 199)   # #FEF3C7
COLOR_WHITE = wx.Colour(255, 255, 255)


def _windows_high_contrast_enabled() -> bool:
    """Devuelve True si Windows tiene activado un tema de alto contraste."""
    if sys.platform != "win32":
        return False
    try:
        class HIGHCONTRASTW(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("dwFlags", ctypes.c_uint),
                ("lpszDefaultScheme", ctypes.c_wchar_p),
            ]

        info = HIGHCONTRASTW()
        info.cbSize = ctypes.sizeof(HIGHCONTRASTW)
        SPI_GETHIGHCONTRAST = 0x0042
        HCF_HIGHCONTRASTON = 0x00000001
        ok = ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETHIGHCONTRAST, info.cbSize, ctypes.byref(info), 0
        )
        return bool(ok and (info.dwFlags & HCF_HIGHCONTRASTON))
    except Exception:
        return False


class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Pasajes Accesibles CNRT", size=(900, 720))
        self.SetMinSize((760, 600))
        self.credential_store = CredentialStore()
        self.high_contrast = _windows_high_contrast_enabled()
        self.visual_config = wx.Config("Pasajes Accesibles CNRT")
        try:
            saved_scale = float(self.visual_config.Read("visual/text_scale", "1.0"))
        except (TypeError, ValueError):
            saved_scale = 1.0
        self.text_scale = min(2.0, max(1.0, round(saved_scale * 4) / 4))
        consent_value = self.visual_config.Read("telemetry/consent", "").strip().lower()
        self.telemetry_consent: bool | None = True if consent_value == "yes" else False if consent_value == "no" else None
        installation_id = self.visual_config.Read("telemetry/installation_id", "").strip()
        self.telemetry = TelemetryClient(
            installation_id=installation_id,
            enabled=self.telemetry_consent is True,
        )
        self.update_service = GitHubUpdateService()
        self.update_in_progress = False
        self.reservation_tracker = ReservationLifecycleTracker()
        self.worker = CnrtWorker(self._dispatch, headless=True)
        self.worker.start()
        self.scan_cancel_event: threading.Event | None = None
        self.origin_results: list[Locality] = []
        self.destination_results: list[Locality] = []
        self.scan_services: list[Service] = []
        self.requests: list[RequestRecord] = []
        self.selected_origin: Locality | None = None
        self.selected_destination: Locality | None = None
        self.pending_service: Service | None = None
        self.selected_quantity: int = 1
        self.profile = Profile()
        self.last_scan_result: ScanResult | None = None
        self.allowed_min_date: date = (datetime.now() + timedelta(hours=48)).date()
        self.allowed_max_date: date = (datetime.now() + timedelta(days=30)).date()
        self._locality_later = {"origin": None, "destination": None}
        self._locality_nav_index = {"origin": -1, "destination": -1}
        self._locality_updating = {"origin": False, "destination": False}
        self._accept_locality_after_search = {"origin": False, "destination": False}

        self.panel = wx.Panel(self)
        self.panel.SetBackgroundColour(self._colour("bg"))
        base_font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        base_font.SetPointSize(max(11, base_font.GetPointSize()))
        self.panel.SetFont(base_font)
        self.root = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.root)
        self.content = wx.ScrolledWindow(self.panel, style=wx.VSCROLL | wx.HSCROLL)
        self.content.SetScrollRate(12, 20)
        self.content.SetBackgroundColour(self._colour("bg"))
        self.content_sizer = wx.BoxSizer(wx.VERTICAL)
        self.content.SetSizer(self.content_sizer)
        self.root.Add(self.content, 1, wx.EXPAND | wx.ALL, 14)

        self.status_label = wx.StaticText(self.panel, label="Estado — Información")
        status_font = self.status_label.GetFont()
        status_font.MakeBold()
        self.status_label.SetFont(status_font)
        self.status_label.SetForegroundColour(self._colour("muted"))
        self.root.Add(self.status_label, 0, wx.LEFT | wx.RIGHT, 14)
        self.status = wx.TextCtrl(
            self.panel,
            style=wx.TE_READONLY | wx.TE_MULTILINE,
            size=(-1, 100),
            name="Estado de la aplicación",
        )
        self.status.SetBackgroundColour(self._colour("status"))
        self.status.SetForegroundColour(self._colour("text"))
        self.root.Add(self.status, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 14)

        self._build_view_menu()
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        self.Bind(wx.EVT_SYS_COLOUR_CHANGED, self.on_system_colour_changed)
        self._show_login()
        self.Centre()
        self._announce("Aplicación iniciada. Complete los datos para ingresar a CNRT.")
        wx.CallAfter(self._initialize_startup_services)

    def _dispatch(self, callback, result, error):
        wx.CallAfter(callback, result, error)

    def _colour(self, role: str) -> wx.Colour:
        if self.high_contrast:
            system = {
                "bg": wx.SYS_COLOUR_WINDOW,
                "surface": wx.SYS_COLOUR_WINDOW,
                "text": wx.SYS_COLOUR_WINDOWTEXT,
                "muted": wx.SYS_COLOUR_WINDOWTEXT,
                "primary": wx.SYS_COLOUR_HIGHLIGHT,
                "primary_hover": wx.SYS_COLOUR_HIGHLIGHT,
                "border": wx.SYS_COLOUR_WINDOWTEXT,
                "status": wx.SYS_COLOUR_WINDOW,
                "success": wx.SYS_COLOUR_WINDOWTEXT,
                "success_bg": wx.SYS_COLOUR_WINDOW,
                "danger": wx.SYS_COLOUR_WINDOWTEXT,
                "danger_hover": wx.SYS_COLOUR_WINDOWTEXT,
                "danger_bg": wx.SYS_COLOUR_WINDOW,
                "warning": wx.SYS_COLOUR_WINDOWTEXT,
                "warning_bg": wx.SYS_COLOUR_WINDOW,
                "white": wx.SYS_COLOUR_HIGHLIGHTTEXT,
                "button_bg": wx.SYS_COLOUR_BTNFACE,
                "button_text": wx.SYS_COLOUR_BTNTEXT,
            }
            return wx.SystemSettings.GetColour(system[role])

        palette = {
            "bg": COLOR_BG,
            "surface": COLOR_SURFACE,
            "text": COLOR_TEXT,
            "muted": COLOR_MUTED,
            "primary": COLOR_PRIMARY,
            "primary_hover": COLOR_PRIMARY_HOVER,
            "border": COLOR_BORDER,
            "status": COLOR_STATUS,
            "success": COLOR_SUCCESS,
            "success_bg": COLOR_SUCCESS_BG,
            "danger": COLOR_DANGER,
            "danger_hover": COLOR_DANGER_HOVER,
            "danger_bg": COLOR_DANGER_BG,
            "warning": COLOR_WARNING,
            "warning_bg": COLOR_WARNING_BG,
            "white": COLOR_WHITE,
            "button_bg": COLOR_SURFACE,
            "button_text": COLOR_TEXT,
        }
        return palette[role]

    def _build_view_menu(self):
        menu_bar = wx.MenuBar()
        view_menu = wx.Menu()
        increase = view_menu.Append(wx.ID_ANY, "Aumentar tamaño de texto (Ctrl + +)")
        decrease = view_menu.Append(wx.ID_ANY, "Reducir tamaño de texto (Ctrl + -)")
        reset = view_menu.Append(wx.ID_ANY, "Restablecer tamaño de texto (Ctrl + 0)")
        view_menu.AppendSeparator()
        self.text_scale_item = view_menu.Append(wx.ID_ANY, self._text_scale_menu_label())
        self.text_scale_item.Enable(False)
        self.Bind(wx.EVT_MENU, lambda e: self._change_text_scale(0.25), increase)
        self.Bind(wx.EVT_MENU, lambda e: self._change_text_scale(-0.25), decrease)
        self.Bind(wx.EVT_MENU, lambda e: self._set_text_scale(1.0), reset)
        menu_bar.Append(view_menu, "&Vista")

        help_menu = wx.Menu()
        about = help_menu.Append(wx.ID_ABOUT, "&Acerca de\tAlt+A")
        contact = help_menu.Append(wx.ID_ANY, "Contáctate &conmigo\tAlt+C")
        help_menu.AppendSeparator()
        check_updates = help_menu.Append(wx.ID_ANY, "&Buscar actualizaciones...")
        privacy = help_menu.Append(wx.ID_ANY, "&Privacidad y estadísticas")
        self.Bind(wx.EVT_MENU, self._show_about, about)
        self.Bind(wx.EVT_MENU, self._contact_me, contact)
        self.Bind(wx.EVT_MENU, self._manual_check_updates, check_updates)
        self.Bind(wx.EVT_MENU, self._manage_telemetry_consent, privacy)
        menu_bar.Append(help_menu, "A&yuda")

        self.SetMenuBar(menu_bar)

    def _show_about(self, event=None):
        message = (
            "Pasajes Accesibles CNRT es una aplicación independiente (no oficial) hecha para que "
            "reservar pasajes mediante el CUD en la CNRT sea fácil y accesible de hacer.\n\n"
            f"Versión: {__version__}.\n\n"
            "Lo que sí podés hacer con el software: usarlo, copiarlo, cambiarlo, estudiarlo "
            "y compartirlo gratis para cualquier uso que no sea comercial.\n\n"
            "Lo que no podés hacer con el programa: venderlo, cobrar por pasarlo a otros o "
            "usarlo para hacer cualquier negocio sin mi permiso. Recordá que usarlo fuera "
            "de lo permitido incumple los derechos de autor y puede derivar en acciones "
            "legales (civiles y penales).\n\n"
            "Licencia: PolyForm Noncommercial 1.0.0.\n\n"
            "© Copyright 2026, Martín Ortiz, derechos reservados."
        )
        wx.MessageBox(
            message,
            "Acerca de Pasajes Accesibles CNRT",
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

    def _contact_me(self, event=None):
        mailto = "mailto:martinortiz4362@gmail.com"
        if wx.LaunchDefaultBrowser(mailto):
            self._announce("Abriendo un nuevo mensaje de correo para contactar a Martín Ortiz.")
            return
        wx.MessageBox(
            "No se pudo abrir el programa de correo predeterminado.",
            "Contáctate conmigo",
            wx.OK | wx.ICON_ERROR,
            self,
        )

    def _manual_check_updates(self, event=None):
        self._start_update_check(manual=True)

    def _auto_check_updates(self):
        if not self.update_service.configured or self.update_in_progress:
            return
        try:
            last_check = float(self.visual_config.Read("updates/last_check_epoch", "0") or 0)
        except (TypeError, ValueError):
            last_check = 0.0
        if time.time() - last_check < 24 * 60 * 60:
            return
        self._start_update_check(manual=False)

    def _start_update_check(self, manual: bool):
        if self.update_in_progress:
            if manual:
                self._announce("Ya se está buscando una actualización.")
            return
        if not self.update_service.configured:
            if manual:
                wx.MessageBox(
                    "Este ejecutable todavía no tiene configurado un repositorio de actualizaciones. "
                    "La compilación oficial creada desde GitHub Actions lo configura automáticamente.",
                    "Buscar actualizaciones",
                    wx.OK | wx.ICON_INFORMATION,
                    self,
                )
            return
        self.update_in_progress = True
        if manual:
            self._announce("Buscando actualizaciones en GitHub...")

        def work():
            info = None
            error = None
            try:
                info = self.update_service.latest()
            except Exception as exc:
                error = exc
            wx.CallAfter(self._finish_update_check, info, error, manual)

        threading.Thread(target=work, name="PasajesUpdateCheck", daemon=True).start()

    def _finish_update_check(self, info: UpdateInfo | None, error: Exception | None, manual: bool):
        self.update_in_progress = False
        self.visual_config.Write("updates/last_check_epoch", str(time.time()))
        self.visual_config.Flush()
        if error is not None:
            if manual:
                detail = str(error) if isinstance(error, UpdateError) else "No se pudo comprobar si hay una actualización."
                wx.MessageBox(detail, "Buscar actualizaciones", wx.OK | wx.ICON_ERROR, self)
                self._announce("No se pudo comprobar si hay una actualización.")
            return
        if info is None:
            if manual:
                wx.MessageBox(
                    f"Ya tenés la versión más reciente: {__version__}.",
                    "Buscar actualizaciones",
                    wx.OK | wx.ICON_INFORMATION,
                    self,
                )
                self._announce("No hay actualizaciones disponibles.")
            return
        # Tanto la comprobación automática como la manual deben avisar con un
        # diálogo cuando exista una versión nueva. La comprobación automática
        # se ejecuta como máximo una vez cada 24 horas para no insistir en cada
        # inicio del programa.
        notes = info.notes.strip()
        if len(notes) > 1600:
            notes = notes[:1600].rstrip() + "…"
        message = (
            f"Está disponible Pasajes Accesibles CNRT {info.version}.\n\n"
            f"Versión instalada: {__version__}.\n\n"
        )
        if notes:
            message += f"Cambios publicados:\n{notes}\n\n"
        package_label = "paquete portable" if info.channel == "portable" else "instalador"
        message += (
            f"¿Querés descargarla ahora? El {package_label} se verificará mediante SHA-256 antes de aplicarse."
        )
        answer = wx.MessageBox(
            message,
            "Actualización disponible",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_INFORMATION,
            self,
        )
        if answer == wx.YES:
            self._download_update(info)
        else:
            self._announce(f"Actualización {info.version} disponible. Se pospuso la descarga.")

    def _download_update(self, info: UpdateInfo):
        if self.update_in_progress:
            return
        self.update_in_progress = True
        self._announce(f"Descargando Pasajes Accesibles CNRT {info.version}...")

        def work():
            path = None
            error = None
            try:
                path = self.update_service.download(info)
                if info.channel == "portable":
                    path = self.update_service.prepare_portable_update(path, info)
            except Exception as exc:
                error = exc
            wx.CallAfter(self._finish_update_download, info, path, error)

        threading.Thread(target=work, name="PasajesUpdateDownload", daemon=True).start()

    def _finish_update_download(self, info: UpdateInfo, path, error: Exception | None):
        self.update_in_progress = False
        if error is not None or path is None:
            detail = str(error) if isinstance(error, UpdateError) else "No se pudo descargar la actualización."
            wx.MessageBox(detail, "Actualización", wx.OK | wx.ICON_ERROR, self)
            self._announce("La actualización no pudo descargarse o verificarse.")
            return
        portable = info.channel == "portable"
        if portable:
            action_text = (
                "Al continuar, esta ventana se cerrará y un actualizador auxiliar reemplazará "
                "la carpeta portable por la nueva versión. Después volverá a abrir el programa. "
                "Tus preferencias y datos guardados en AppData no se eliminan.\n\n"
                "¿Actualizar ahora?"
            )
            title = "Actualización portable lista"
        else:
            action_text = (
                "Al continuar se abrirá el instalador y esta ventana se cerrará. "
                "Tus preferencias y datos guardados en AppData no se eliminan.\n\n"
                "¿Instalar ahora?"
            )
            title = "Actualización lista para instalar"
        answer = wx.MessageBox(
            f"Pasajes Accesibles CNRT {info.version} se descargó y su SHA-256 fue verificado.\n\n"
            + action_text,
            title,
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_INFORMATION,
            self,
        )
        if answer != wx.YES:
            self._announce(f"Actualización {info.version} descargada. Aplicación pospuesta.")
            return
        try:
            if portable:
                self.update_service.launch_portable_update(path)
            else:
                self.update_service.launch_installer(path)
        except UpdateError as exc:
            wx.MessageBox(str(exc), "Actualización", wx.OK | wx.ICON_ERROR, self)
            self._announce("Windows no pudo iniciar la aplicación de la actualización.")
            return
        self._announce(
            "Aplicando la actualización portable." if portable else "Abriendo el instalador de la actualización."
        )
        wx.CallAfter(self.Close)

    @staticmethod
    def _telemetry_consent_text() -> str:
        return (
            "¿Querés ayudar a mejorar Pasajes Accesibles CNRT compartiendo estadísticas de uso?\n\n"
            "Si elegís Sí, estas estadísticas se enviarán a PostHog y se procesarán en su región de Estados Unidos. "
            "El conjunto de estadísticas anónimas o pseudónimas incluye:\n"
            "• datos técnicos generales del equipo: versión del programa, Windows y compilación, arquitectura, "
            "CPU y memoria en rangos, idioma, zona horaria, resolución, DPI y escala de texto;\n"
            "• funciones de accesibilidad detectadas: NVDA, JAWS, Narrador, Lupa de Windows, alto contraste, "
            "Teclas especiales, Teclas filtro, Teclas de alternancia y Teclas de mouse;\n"
            "• cuando una reserva se confirma o CNRT muestra su estado: empresa, origen, destino, fecha del viaje "
            "y estado de la solicitud (por ejemplo Activa, Pasaje Emitido o anulada/cancelada);\n"
            "• ubicación aproximada derivada por el servicio de estadísticas a partir de la conexión, "
            "como país, región o ciudad.\n\n"
            "Nunca se enviarán nombre, apellido, DNI, número de CUD, correo electrónico, teléfono, "
            "código de reserva ni las credenciales usadas para ingresar a CNRT.\n\n"
            "Las estadísticas técnicas pueden usar un identificador aleatorio de instalación para contar equipos. "
            "Cada reserva usa un identificador aleatorio propio, separado del identificador de instalación. Ese ID "
            "solo permite seguir los cambios de estado de esa reserva y no identifica a la persona ni usa el código real de CNRT.\n\n"
            "Podés cambiar esta decisión en cualquier momento desde Ayuda > Privacidad y estadísticas. "
            "Desactivarlo detiene futuros envíos; no elimina estadísticas que ya se hayan enviado.\n\n"
            "¿Querés compartir estas estadísticas?"
        )

    def _initialize_startup_services(self):
        # El consentimiento puede abrir un diálogo modal. La comprobación de
        # actualizaciones se agenda únicamente después de que ese diálogo termine.
        self._initialize_telemetry_consent()
        wx.CallLater(2500, self._auto_check_updates)

    def _ensure_installation_id(self) -> str:
        installation_id = self.visual_config.Read("telemetry/installation_id", "").strip()
        if not installation_id:
            installation_id = str(uuid.uuid4())
            self.visual_config.Write("telemetry/installation_id", installation_id)
            self.visual_config.Flush()
        return installation_id

    def _set_telemetry_consent(self, enabled: bool):
        self.telemetry_consent = bool(enabled)
        self.visual_config.Write("telemetry/consent", "yes" if enabled else "no")
        installation_id = self._ensure_installation_id() if enabled else self.visual_config.Read("telemetry/installation_id", "").strip()
        self.visual_config.Flush()
        self.telemetry.configure(enabled=enabled, installation_id=installation_id)
        if enabled:
            self._capture_startup_telemetry()

    def _ask_telemetry_consent(self, title: str = "Privacidad y estadísticas") -> bool:
        dialog = wx.MessageDialog(
            self,
            self._telemetry_consent_text(),
            title,
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_INFORMATION,
        )
        try:
            try:
                dialog.SetYesNoLabels("Sí, compartir", "No, no compartir")
            except Exception:
                pass
            return dialog.ShowModal() == wx.ID_YES
        finally:
            dialog.Destroy()

    def _initialize_telemetry_consent(self):
        if not self.telemetry.configured:
            return
        if self.telemetry_consent is None:
            self._set_telemetry_consent(self._ask_telemetry_consent())
        elif self.telemetry_consent:
            self.telemetry.configure(enabled=True, installation_id=self._ensure_installation_id())
            self._capture_startup_telemetry()

    def _manage_telemetry_consent(self, event=None):
        if not self.telemetry.configured:
            wx.MessageBox(
                "Las estadísticas todavía no están conectadas a un proyecto de PostHog. "
                "No se está enviando ningún dato.",
                "Privacidad y estadísticas",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        current = "activado" if self.telemetry_consent else "desactivado"
        enabled = self._ask_telemetry_consent(f"Privacidad y estadísticas — actualmente {current}")
        self._set_telemetry_consent(enabled)
        self._announce(
            "Envío de estadísticas activado." if enabled else "Envío de estadísticas desactivado."
        )

    def _capture_startup_telemetry(self):
        if not self.telemetry_consent:
            return
        try:
            size = wx.GetDisplaySize()
            screen_size = (size.GetWidth(), size.GetHeight())
        except Exception:
            screen_size = None
        try:
            dpi_value = self.GetDPI()
            dpi = (dpi_value.GetWidth(), dpi_value.GetHeight())
        except Exception:
            dpi = None
        properties = collect_technical_properties(
            high_contrast=self.high_contrast,
            app_text_scale=self.text_scale,
            screen_size=screen_size,
            dpi=dpi,
        )
        self.telemetry.capture_technical(properties)

    def _text_scale_menu_label(self) -> str:
        mode = " · colores del sistema" if self.high_contrast else ""
        return f"Tamaño de texto actual: {int(self.text_scale * 100)}%{mode}"

    def _set_text_scale(self, scale: float):
        scale = min(2.0, max(1.0, round(scale * 4) / 4))
        if scale == self.text_scale:
            return
        self.text_scale = scale
        self.visual_config.Write("visual/text_scale", f"{scale:.2f}")
        self.visual_config.Flush()
        self._refresh_visual_preferences()
        self._announce(f"Tamaño de texto: {int(scale * 100)} por ciento.")

    def _change_text_scale(self, delta: float):
        self._set_text_scale(self.text_scale + delta)

    def _apply_font_scale(self, parent):
        for child in parent.GetChildren():
            if not isinstance(child, (wx.Panel, wx.ScrolledWindow)):
                font = child.GetFont()
                if font.IsOk():
                    if not hasattr(child, "_cnrt_base_point_size"):
                        child._cnrt_base_point_size = max(1, font.GetPointSize())
                    font.SetPointSize(max(1, round(child._cnrt_base_point_size * self.text_scale)))
                    child.SetFont(font)
                    try:
                        child.InvalidateBestSize()
                    except Exception:
                        pass
            if isinstance(child, wx.Button):
                child.SetMinSize((-1, max(44, round(44 * self.text_scale))))
            if child is self.status:
                child.SetMinSize((-1, max(100, round(100 * self.text_scale))))
            if child.GetChildren():
                self._apply_font_scale(child)

    def _refresh_visual_preferences(self):
        if hasattr(self, "text_scale_item"):
            self.text_scale_item.SetItemLabel(self._text_scale_menu_label())
        self.panel.SetBackgroundColour(self._colour("bg"))
        self.content.SetBackgroundColour(self._colour("bg"))
        self.status_label.SetForegroundColour(self._colour("muted"))
        self._apply_control_theme()
        self._apply_font_scale(self.panel)
        self.panel.Layout()
        self.content.Layout()
        self.content.FitInside()
        self.Refresh()

    def on_system_colour_changed(self, event):
        was_high_contrast = self.high_contrast
        self.high_contrast = _windows_high_contrast_enabled()
        wx.CallAfter(self._refresh_visual_preferences)
        if was_high_contrast != self.high_contrast:
            message = (
                "Modo de alto contraste de Windows activado. Se usan colores del sistema."
                if self.high_contrast
                else "Modo de alto contraste de Windows desactivado. Se restauró el tema visual de Pasajes Accesibles CNRT."
            )
            wx.CallAfter(self._announce, message)
        event.Skip()

    def _clear_content(self):
        for later in getattr(self, "_locality_later", {}).values():
            try:
                if later is not None and later.IsRunning():
                    later.Stop()
            except Exception:
                pass
        for child in self.content.GetChildren():
            child.Destroy()
        self.content_sizer.Clear()

    def _heading(self, text: str, accessible_text: str | None = None):
        spoken = (accessible_text or text).strip()
        header = wx.Panel(self.content, name=spoken)
        header._pasajes_accesibles_cnrt_visual_header = True
        header.SetBackgroundColour(self._colour("primary"))
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        label = wx.StaticText(header, label=text)
        font = label.GetFont()
        font.SetPointSize(font.GetPointSize() + 5)
        font.MakeBold()
        label.SetFont(font)
        label.SetForegroundColour(self._colour("white"))
        label.SetBackgroundColour(self._colour("primary"))
        header_sizer.Add(label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 14)
        header.SetSizer(header_sizer)
        self.content_sizer.Add(header, 0, wx.EXPAND | wx.BOTTOM, 16)
        return label

    def _style_button(self, button: wx.Button, role: str = "secondary"):
        button._cnrt_visual_role = role
        font = button.GetFont()
        if role in ("primary", "danger", "success"):
            font.MakeBold()
        button.SetFont(font)
        button.SetMinSize((-1, max(44, button.GetMinSize().GetHeight())))

        if self.high_contrast:
            palettes = {
                "primary": (self._colour("button_bg"), self._colour("button_text"), self._colour("button_bg")),
                "danger": (self._colour("button_bg"), self._colour("button_text"), self._colour("button_bg")),
                "success": (self._colour("button_bg"), self._colour("button_text"), self._colour("button_bg")),
                "secondary": (self._colour("button_bg"), self._colour("button_text"), self._colour("button_bg")),
            }
        else:
            palettes = {
                "primary": (self._colour("primary"), self._colour("white"), self._colour("primary_hover")),
                "danger": (self._colour("danger"), self._colour("white"), self._colour("danger_hover")),
                "success": (self._colour("success"), self._colour("white"), self._colour("success")),
                "secondary": (self._colour("surface"), self._colour("text"), self._colour("status")),
            }
        bg, fg, hover = palettes.get(role, palettes["secondary"])
        button.SetBackgroundColour(bg)
        button.SetForegroundColour(fg)

        if not getattr(button, "_cnrt_hover_bound", False):
            button._cnrt_hover_bound = True
            button.Bind(wx.EVT_ENTER_WINDOW, lambda e, b=button: self._button_hover(e, b, True))
            button.Bind(wx.EVT_LEAVE_WINDOW, lambda e, b=button: self._button_hover(e, b, False))

    def _button_hover(self, event, button: wx.Button, entering: bool):
        if button.IsEnabled():
            role = getattr(button, "_cnrt_visual_role", "secondary")
            if self.high_contrast:
                colour = self._colour("button_bg")
            elif entering:
                colour = {
                    "primary": self._colour("primary_hover"),
                    "danger": self._colour("danger_hover"),
                    "success": self._colour("success"),
                    "secondary": self._colour("status"),
                }.get(role, self._colour("status"))
            else:
                colour = {
                    "primary": self._colour("primary"),
                    "danger": self._colour("danger"),
                    "success": self._colour("success"),
                    "secondary": self._colour("surface"),
                }.get(role, self._colour("surface"))
            button.SetBackgroundColour(colour)
            button.Refresh()
        event.Skip()

    def _apply_control_theme(self, parent=None):
        is_root = parent is None
        parent = parent or self.content
        for child in parent.GetChildren():
            if isinstance(child, wx.Panel) and getattr(child, "_pasajes_accesibles_cnrt_visual_header", False):
                child.SetBackgroundColour(self._colour("primary"))
                for header_child in child.GetChildren():
                    if isinstance(header_child, wx.StaticText):
                        header_child.SetBackgroundColour(self._colour("primary"))
                        header_child.SetForegroundColour(self._colour("white"))
                continue

            if isinstance(child, wx.Panel):
                child.SetBackgroundColour(self._colour("bg"))
            elif isinstance(child, wx.StaticText):
                role = getattr(child, "_cnrt_text_role", "normal")
                if role == "muted":
                    child.SetForegroundColour(self._colour("muted"))
                elif role == "warning":
                    child.SetForegroundColour(self._colour("warning"))
                elif role == "danger":
                    child.SetForegroundColour(self._colour("danger"))
                elif role == "success":
                    child.SetForegroundColour(self._colour("success"))
                else:
                    child.SetForegroundColour(self._colour("text"))
                child.SetBackgroundColour(child.GetParent().GetBackgroundColour())
            elif isinstance(child, (wx.TextCtrl, wx.ComboBox, wx.Choice, wx.ListBox, wx.SpinCtrlDouble)):
                child.SetBackgroundColour(self._colour("surface"))
                child.SetForegroundColour(self._colour("text"))
            elif isinstance(child, (wx.RadioButton, wx.CheckBox, wx.RadioBox)):
                child.SetBackgroundColour(child.GetParent().GetBackgroundColour())
                child.SetForegroundColour(self._colour("text"))
            elif isinstance(child, wx.StaticBox):
                child.SetForegroundColour(self._colour("text") if self.high_contrast else self._colour("primary"))
                child.SetBackgroundColour(child.GetParent().GetBackgroundColour())
            elif isinstance(child, wx.Button):
                self._style_button(child, getattr(child, "_cnrt_visual_role", "secondary"))

            if child.GetChildren():
                self._apply_control_theme(child)

        if is_root:
            self._apply_font_scale(self.panel)
            self.content.Layout()
            self.content.FitInside()
            self.panel.Layout()

    def _set_status_visual(self, message: str):
        lower = message.casefold()
        if "éxito" in lower or "confirmada por cnrt" in lower or "actualizados" in lower:
            role = "Éxito"
            bg, fg = self._colour("success_bg"), self._colour("success")
        elif "error" in lower or "no se pudo" in lower:
            role = "Error"
            bg, fg = self._colour("danger_bg"), self._colour("danger")
        elif "cancel" in lower or "aviso" in lower:
            role = "Aviso"
            bg, fg = self._colour("warning_bg"), self._colour("warning")
        else:
            role = "Información"
            bg, fg = self._colour("status"), self._colour("text")

        if self.high_contrast:
            bg, fg = self._colour("status"), self._colour("text")
        self.status_label.SetLabel(f"Estado — {role}")
        self.status.SetBackgroundColour(bg)
        self.status.SetForegroundColour(fg)
        self.status.Refresh()

    def _announce(self, message: str):
        old = self.status.GetValue().strip()
        lines = ([old] if old else []) + [message]
        text = "\n".join(lines[-8:])
        self.status.SetValue(text)
        self._set_status_visual(message)

    def _busy(self, message: str):
        # No deshabilitamos toda la ventana: durante un escaneo el botón Cancelar debe seguir accesible.
        self._announce(message)

    def _done(self):
        pass

    # ---------------- Login ----------------
    def _show_login(self):
        self._clear_content()
        self._heading("Ingresar al sistema de CNRT")
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=12)
        grid.AddGrowableCol(1, 1)

        grid.Add(wx.StaticText(self.content, label="Tipo de documento"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.doc_type = wx.Choice(self.content, choices=[x[0] for x in DOC_TYPES], name="Tipo de documento")
        self.doc_type.SetSelection(0)
        grid.Add(self.doc_type, 1, wx.EXPAND)

        grid.Add(wx.StaticText(self.content, label="Número de documento"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.doc_number = wx.TextCtrl(self.content, name="Número de documento")
        grid.Add(self.doc_number, 1, wx.EXPAND)

        grid.Add(wx.StaticText(self.content, label="Tipo de credencial"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.cred_type = wx.Choice(self.content, choices=[x[0] for x in CRED_TYPES], name="Tipo de credencial")
        self.cred_type.SetSelection(0)
        self.cred_type.Bind(wx.EVT_CHOICE, self._update_credential_controls)
        grid.Add(self.cred_type, 1, wx.EXPAND)

        grid.Add(wx.StaticText(self.content, label="Número de credencial"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.cred_number = wx.TextCtrl(self.content, name="Número de credencial")
        grid.Add(self.cred_number, 1, wx.EXPAND)

        grid.Add(wx.StaticText(self.content, label="Sexo (solo credencial municipal/provincial)"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.sex = wx.Choice(self.content, choices=["Masculino", "Femenino"], name="Sexo")
        self.sex.SetSelection(0)
        self.sex.Enable(False)
        grid.Add(self.sex, 1, wx.EXPAND)

        self.content_sizer.Add(grid, 0, wx.EXPAND | wx.BOTTOM, 10)
        self.remember = wx.CheckBox(self.content, label="Recordar credenciales de forma cifrada en este usuario de Windows")
        self.content_sizer.Add(self.remember, 0, wx.BOTTOM, 10)
        row = wx.WrapSizer(wx.HORIZONTAL)
        login = wx.Button(self.content, label="&Ingresar", name="Ingresar")
        login.Bind(wx.EVT_BUTTON, self.on_login)
        self._style_button(login, "primary")
        row.Add(login, 0, wx.RIGHT, 8)
        clear = wx.Button(self.content, label="Olvidar credenciales guardadas")
        clear.Bind(wx.EVT_BUTTON, self.on_clear_credentials)
        row.Add(clear, 0)
        self.content_sizer.Add(row, 0)
        self._load_credentials()
        self._apply_control_theme()
        self.content.Layout()
        self.doc_number.SetFocus()

    def _update_credential_controls(self, event=None):
        municipal = CRED_TYPES[self.cred_type.GetSelection()][1] == "MUNICIPAL"
        self.cred_number.Enable(not municipal)
        self.sex.Enable(municipal)

    def _load_credentials(self):
        try:
            data = self.credential_store.load()
        except Exception as exc:
            self._announce(f"No se pudieron leer las credenciales guardadas: {exc}")
            return
        if not data:
            return
        self.doc_number.SetValue(data.get("document_number", ""))
        self.cred_number.SetValue(data.get("credential_number", ""))
        self._select_value(self.doc_type, DOC_TYPES, data.get("document_type", "1"))
        self._select_value(self.cred_type, CRED_TYPES, data.get("credential_type", "CUD"))
        self.sex.SetSelection(0 if data.get("sex", "1") == "1" else 1)
        self.remember.SetValue(True)
        self._update_credential_controls()

    @staticmethod
    def _select_value(choice, pairs, value):
        for i, (_, v) in enumerate(pairs):
            if v == value:
                choice.SetSelection(i)
                return

    def on_clear_credentials(self, event):
        self.credential_store.clear()
        self.remember.SetValue(False)
        self._announce("Credenciales guardadas eliminadas.")

    def on_login(self, event):
        doc = self.doc_number.GetValue().strip()
        cred_type = CRED_TYPES[self.cred_type.GetSelection()][1]
        cred = self.cred_number.GetValue().strip()
        if not doc:
            wx.MessageBox("Ingrese el número de documento.", "Falta un dato", wx.OK | wx.ICON_WARNING)
            self.doc_number.SetFocus()
            return
        if cred_type != "MUNICIPAL" and not cred:
            wx.MessageBox("Ingrese el número de credencial.", "Falta un dato", wx.OK | wx.ICON_WARNING)
            self.cred_number.SetFocus()
            return
        payload = {
            "document_type": DOC_TYPES[self.doc_type.GetSelection()][1],
            "document_number": doc,
            "credential_type": cred_type,
            "credential_number": cred,
            "sex": "1" if self.sex.GetSelection() == 0 else "2",
        }
        if self.remember.GetValue():
            try:
                self.credential_store.save(payload)
            except Exception as exc:
                wx.MessageBox(f"No se pudieron guardar las credenciales de forma segura: {exc}", "Aviso", wx.OK | wx.ICON_WARNING)
        else:
            self.credential_store.clear()
        self._busy("Ingresando a CNRT...")
        self.worker.submit("login", callback=self._after_login, **payload)

    def _after_login(self, result, error):
        self._done()
        if error:
            wx.MessageBox(str(error), "No se pudo iniciar sesión", wx.OK | wx.ICON_ERROR)
            self._announce(f"Error de ingreso: {error}")
            return
        self._announce(str(result))
        self._show_main_menu()

    # ---------------- Menú ----------------
    def _show_main_menu(self):
        self._clear_content()
        self._heading(
            "Pasajes Accesibles CNRT",
            "Reserva, consulta y gestión accesible de pasajes",
        )
        subtitle = wx.StaticText(self.content, label="Reserva, consulta y gestión accesible de pasajes")
        subtitle._cnrt_text_role = "muted"
        subtitle_font = subtitle.GetFont()
        subtitle_font.SetPointSize(subtitle_font.GetPointSize() + 1)
        subtitle.SetFont(subtitle_font)
        self.content_sizer.Add(subtitle, 0, wx.BOTTOM, 14)
        for index, (label, handler) in enumerate([
            ("&Buscar pasajes", self._show_search),
            ("&Mis solicitudes", self.on_requests),
            ("Mi &información", self.on_profile),
            ("Cerrar sesión", self.on_logout),
        ]):
            b = wx.Button(self.content, label=label, size=(-1, 46))
            b.Bind(wx.EVT_BUTTON, handler)
            self._style_button(b, "primary" if index == 0 else "secondary")
            self.content_sizer.Add(b, 0, wx.EXPAND | wx.BOTTOM, 10)
        self._apply_control_theme()
        self.content.Layout()
        self.content.GetChildren()[1].SetFocus() if len(self.content.GetChildren()) > 1 else None

    # ---------------- Búsqueda ----------------
    def _show_search(self, event=None):
        self._clear_content()
        self._heading("Buscar pasajes")

        self.content_sizer.Add(wx.StaticText(self.content, label="Origen"), 0)
        self.origin_combo = wx.ComboBox(
            self.content,
            choices=[],
            name="Origen, cuadro combinado editable",
            style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER,
        )
        self.origin_combo.SetHint("Escriba para filtrar localidades")
        self.origin_combo.Bind(wx.EVT_TEXT, lambda e: self._on_locality_combo_text("origin", e))
        self.origin_combo.Bind(wx.EVT_TEXT_ENTER, lambda e: self._on_locality_combo_enter("origin"))
        self.origin_combo.Bind(wx.EVT_COMBOBOX, lambda e: self._on_locality_combo_selected("origin", e))
        self.origin_combo.Bind(wx.EVT_KEY_DOWN, lambda e: self._on_locality_combo_key("origin", e))
        self.content_sizer.Add(self.origin_combo, 0, wx.EXPAND | wx.BOTTOM, 10)

        self.content_sizer.Add(wx.StaticText(self.content, label="Destino"), 0)
        self.destination_combo = wx.ComboBox(
            self.content,
            choices=[],
            name="Destino, cuadro combinado editable",
            style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER,
        )
        self.destination_combo.SetHint("Escriba para filtrar localidades")
        self.destination_combo.Bind(wx.EVT_TEXT, lambda e: self._on_locality_combo_text("destination", e))
        self.destination_combo.Bind(wx.EVT_TEXT_ENTER, lambda e: self._on_locality_combo_enter("destination"))
        self.destination_combo.Bind(wx.EVT_COMBOBOX, lambda e: self._on_locality_combo_selected("destination", e))
        self.destination_combo.Bind(wx.EVT_KEY_DOWN, lambda e: self._on_locality_combo_key("destination", e))
        self.content_sizer.Add(self.destination_combo, 0, wx.EXPAND | wx.BOTTOM, 10)

        opts = wx.WrapSizer(wx.HORIZONTAL)
        opts.Add(wx.StaticText(self.content, label="Cantidad de pasajes"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.quantity = wx.Choice(self.content, choices=["1", "2"], name="Cantidad de pasajes")
        self.quantity.SetSelection(0)
        opts.Add(self.quantity, 0, wx.RIGHT, 20)
        opts.Add(wx.StaticText(self.content, label="Pausa entre consultas (segundos)"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.delay = wx.SpinCtrlDouble(self.content, min=0.5, max=5.0, inc=0.1, initial=0.9, name="Pausa entre consultas")
        opts.Add(self.delay, 0)
        self.content_sizer.Add(opts, 0, wx.BOTTOM, 12)

        mode_box = wx.StaticBoxSizer(wx.VERTICAL, self.content, "Modo de búsqueda")
        self.mode_specific = wx.RadioButton(
            mode_box.GetStaticBox(),
            label="Buscar fecha e&specífica",
            style=wx.RB_GROUP,
            name="Buscar fecha específica",
        )
        self.mode_range = wx.RadioButton(
            mode_box.GetStaticBox(),
            label="Buscar &rango de fechas",
            name="Buscar rango de fechas",
        )
        self.mode_all = wx.RadioButton(
            mode_box.GetStaticBox(),
            label="Escanear todas las fechas disponibl&es",
            name="Escanear todas las fechas disponibles",
        )
        self.mode_specific.SetValue(True)
        self.mode_specific.Bind(wx.EVT_RADIOBUTTON, self._on_search_mode_change)
        self.mode_range.Bind(wx.EVT_RADIOBUTTON, self._on_search_mode_change)
        self.mode_all.Bind(wx.EVT_RADIOBUTTON, self._on_search_mode_change)
        mode_box.Add(self.mode_specific, 0, wx.BOTTOM, 4)
        mode_box.Add(self.mode_range, 0, wx.BOTTOM, 4)
        mode_box.Add(self.mode_all, 0)
        self.content_sizer.Add(mode_box, 0, wx.EXPAND | wx.BOTTOM, 8)

        self.specific_panel = wx.Panel(self.content, name="Fecha específica")
        self.specific_sizer = wx.BoxSizer(wx.VERTICAL)
        self.specific_panel.SetSizer(self.specific_sizer)
        self._build_date_editor(self.specific_sizer, "Fecha", "travel", parent=self.specific_panel)
        self.content_sizer.Add(self.specific_panel, 0, wx.EXPAND | wx.BOTTOM, 8)

        self.range_panel = wx.Panel(self.content, name="Rango de fechas")
        self.range_sizer = wx.BoxSizer(wx.VERTICAL)
        self.range_panel.SetSizer(self.range_sizer)
        self._build_date_editor(self.range_sizer, "Desde", "from", parent=self.range_panel)
        self._build_date_editor(self.range_sizer, "Hasta", "to", parent=self.range_panel)
        self.content_sizer.Add(self.range_panel, 0, wx.EXPAND | wx.BOTTOM, 8)
        self.range_panel.Hide()

        row = wx.WrapSizer(wx.HORIZONTAL)
        self.search_dates_button = wx.Button(self.content, label="Buscar &fecha", name="Buscar fecha")
        self.search_dates_button.Bind(wx.EVT_BUTTON, self.on_search_dates)
        self._style_button(self.search_dates_button, "primary")
        row.Add(self.search_dates_button, 0, wx.RIGHT, 8)
        cancel = wx.Button(self.content, label="&Cancelar búsqueda")
        cancel.Bind(wx.EVT_BUTTON, self.on_cancel_scan)
        row.Add(cancel, 0, wx.RIGHT, 8)
        back = wx.Button(self.content, label="Volver al menú")
        back.Bind(wx.EVT_BUTTON, lambda e: self._show_main_menu())
        row.Add(back, 0)
        self.content_sizer.Add(row, 0)

        self._populate_date_choices()
        self._set_date_value("travel", self.allowed_min_date)
        self._set_date_value("from", self.allowed_min_date)
        self._set_date_value("to", self._clamp_allowed_date(self.allowed_min_date + timedelta(days=1)))
        self._on_search_mode_change(None, move_focus=False)
        self._apply_control_theme()
        self.content.Layout()
        self.origin_combo.SetFocus()

        # CNRT publica los límites reales en su página. Los pedimos después de
        # dibujar la ventana para que la interfaz aparezca de inmediato.
        self.worker.submit("allowed_date_range", callback=self._after_allowed_date_range)

    # ----- Localidades: cuadro combinado editable con búsqueda dinámica -----
    def _locality_combo(self, which: str):
        return self.origin_combo if which == "origin" else self.destination_combo

    def _locality_items(self, which: str) -> list[Locality]:
        return self.origin_results if which == "origin" else self.destination_results

    def _set_locality_items(self, which: str, items: list[Locality]):
        if which == "origin":
            self.origin_results = items
        else:
            self.destination_results = items

    def _set_selected_locality(self, which: str, item: Locality | None):
        if which == "origin":
            self.selected_origin = item
        else:
            self.selected_destination = item

    def _replace_locality_choices(self, which: str, items: list[Locality]):
        combo = self._locality_combo(which)
        value = combo.GetValue()
        try:
            insertion = combo.GetInsertionPoint()
        except Exception:
            insertion = len(value)
        self._locality_updating[which] = True
        try:
            combo.Freeze()
            combo.Clear()
            if items:
                combo.AppendItems([item.text for item in items])
            combo.ChangeValue(value)
            combo.SetInsertionPoint(min(insertion, len(value)))
        finally:
            try:
                combo.Thaw()
            except Exception:
                pass
            self._locality_updating[which] = False
        self._locality_nav_index[which] = -1

    def _on_locality_combo_text(self, which: str, event):
        if self._locality_updating.get(which):
            event.Skip()
            return
        combo = self._locality_combo(which)
        query = combo.GetValue().strip()
        items = self._locality_items(which)
        selected_index = combo.GetSelection()
        if selected_index != wx.NOT_FOUND and 0 <= selected_index < len(items):
            candidate = items[selected_index]
            if query == candidate.text:
                self._locality_nav_index[which] = selected_index
                self._set_selected_locality(which, candidate)
                event.Skip()
                return

        selected = self.selected_origin if which == "origin" else self.selected_destination
        if selected is not None and query == selected.text:
            event.Skip()
            return

        self._set_selected_locality(which, None)
        self._set_locality_items(which, [])
        self._replace_locality_choices(which, [])

        later = self._locality_later.get(which)
        if later is not None and later.IsRunning():
            later.Stop()
        if query:
            self._locality_later[which] = wx.CallLater(350, self._search_locality, which, query)
        event.Skip()

    def _on_locality_combo_enter(self, which: str):
        combo = self._locality_combo(which)
        query = combo.GetValue().strip()
        if not query:
            wx.MessageBox("Escriba una parte del nombre de la localidad.", "Buscar localidad", wx.OK | wx.ICON_INFORMATION)
            return

        selected = self.selected_origin if which == "origin" else self.selected_destination
        if selected is not None and query == selected.text:
            self._accept_locality(which, selected)
            return

        items = self._locality_items(which)
        idx = combo.GetSelection()
        if idx == wx.NOT_FOUND:
            idx = self._locality_nav_index.get(which, -1)
        if items and 0 <= idx < len(items):
            self._accept_locality(which, items[idx])
            return
        if items:
            self._accept_locality(which, items[0])
            return

        self._accept_locality_after_search[which] = True
        self._search_locality(which, query)

    def _on_locality_combo_key(self, which: str, event):
        key = event.GetKeyCode()
        if key not in (wx.WXK_UP, wx.WXK_DOWN):
            event.Skip()
            return

        items = self._locality_items(which)
        if not items:
            event.Skip()
            return

        combo = self._locality_combo(which)
        current = self._locality_nav_index.get(which, -1)
        if key == wx.WXK_DOWN:
            current = 0 if current < 0 else min(current + 1, len(items) - 1)
        else:
            current = len(items) - 1 if current < 0 else max(current - 1, 0)

        self._locality_nav_index[which] = current
        item = items[current]
        self._locality_updating[which] = True
        try:
            combo.SetSelection(current)
            combo.ChangeValue(item.text)
            combo.SetInsertionPointEnd()
        finally:
            self._locality_updating[which] = False
        self._set_selected_locality(which, item)
        self._announce(item.text)

    def _on_locality_combo_selected(self, which: str, event):
        if self._locality_updating.get(which):
            return
        combo = self._locality_combo(which)
        items = self._locality_items(which)
        idx = combo.GetSelection()
        if idx != wx.NOT_FOUND and 0 <= idx < len(items):
            item = items[idx]
            self._locality_nav_index[which] = idx
            self._set_selected_locality(which, item)
            self._announce(f"{('Origen' if which == 'origin' else 'Destino')} seleccionado: {item.text}.")
        event.Skip()

    def _search_locality(self, which: str, query: str | None = None):
        combo = self._locality_combo(which)
        query = (query if query is not None else combo.GetValue()).strip()
        if not query:
            return
        self.worker.submit(
            "search_localities",
            query,
            callback=lambda r, e, q=query: self._after_locality(which, q, r, e),
        )

    def _after_locality(self, which: str, query: str, result, error):
        try:
            combo = self._locality_combo(which)
            current_query = combo.GetValue().strip()
        except (AttributeError, RuntimeError):
            return
        # Si el usuario siguió escribiendo, una respuesta anterior ya no sirve.
        if current_query != query:
            return
        if error:
            self._accept_locality_after_search[which] = False
            self._announce(f"Error al buscar localidades: {error}")
            return

        items = result or []
        self._set_locality_items(which, items)
        self._replace_locality_choices(which, items)
        self._announce(f"{query}: {len(items)} localidades encontradas.")

        if self._accept_locality_after_search.get(which):
            self._accept_locality_after_search[which] = False
            if items:
                self._accept_locality(which, items[0])
            else:
                wx.Bell()

    def _focus_after_locality(self, which: str):
        if which == "origin":
            self.destination_combo.SetFocus()
            return
        if self.mode_specific.GetValue():
            self.travel_date.SetFocus()
        elif self.mode_range.GetValue():
            self.from_date.SetFocus()
        else:
            self.search_dates_button.SetFocus()

    def _accept_locality(self, which: str, selected: Locality | None = None):
        combo = self._locality_combo(which)
        items = self._locality_items(which)
        if selected is None:
            idx = combo.GetSelection()
            if idx == wx.NOT_FOUND:
                idx = self._locality_nav_index.get(which, -1)
            if idx == wx.NOT_FOUND or idx < 0 or idx >= len(items):
                wx.Bell()
                return
            selected = items[idx]

        self._locality_updating[which] = True
        try:
            idx = next((i for i, item in enumerate(items) if item.id == selected.id), wx.NOT_FOUND)
            if idx != wx.NOT_FOUND:
                combo.SetSelection(idx)
                self._locality_nav_index[which] = idx
            combo.ChangeValue(selected.text)
            combo.SetInsertionPointEnd()
        finally:
            self._locality_updating[which] = False

        self._set_selected_locality(which, selected)
        self._announce(f"{('Origen' if which == 'origin' else 'Destino')} seleccionado: {selected.text}.")
        self._focus_after_locality(which)

    def _resolve_locality(self, which: str) -> Locality | None:
        selected = self.selected_origin if which == "origin" else self.selected_destination
        combo = self._locality_combo(which)
        value = combo.GetValue().strip()
        if selected is not None and value == selected.text:
            return selected
        for item in self._locality_items(which):
            if value == item.text:
                return item
        return None

    # ----- Fechas: edición + día/mes/año -----
    def _build_date_editor(self, container_sizer, label: str, prefix: str, parent=None):
        parent = parent or self.content
        box = wx.StaticBoxSizer(wx.VERTICAL, parent, label)
        text_row = wx.WrapSizer(wx.HORIZONTAL)
        text_row.Add(wx.StaticText(parent, label=f"{label} (DD-MM-AAAA)"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        text = wx.TextCtrl(parent, name=f"{label}, fecha editable", style=wx.TE_PROCESS_ENTER, size=(165, -1))
        text.Bind(wx.EVT_KEY_DOWN, lambda e, p=prefix: self._on_date_text_key(p, e))
        text.Bind(wx.EVT_TEXT, lambda e, p=prefix: self._sync_choices_from_text(p, e))
        setattr(self, f"{prefix}_date", text)
        text_row.Add(text, 0)
        box.Add(text_row, 0, wx.EXPAND | wx.BOTTOM, 5)

        choices = wx.WrapSizer(wx.HORIZONTAL)
        choices.Add(wx.StaticText(parent, label="Día"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        day = wx.Choice(parent, choices=[f"{n:02d}" for n in range(1, 32)], name=f"{label}, día")
        setattr(self, f"{prefix}_day", day)
        choices.Add(day, 0, wx.RIGHT, 10)
        choices.Add(wx.StaticText(parent, label="Mes"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        month_names = [
            "01 - enero", "02 - febrero", "03 - marzo", "04 - abril", "05 - mayo", "06 - junio",
            "07 - julio", "08 - agosto", "09 - septiembre", "10 - octubre", "11 - noviembre", "12 - diciembre",
        ]
        month = wx.Choice(parent, choices=month_names, name=f"{label}, mes")
        setattr(self, f"{prefix}_month", month)
        choices.Add(month, 0, wx.RIGHT, 10)
        choices.Add(wx.StaticText(parent, label="Año"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        year = wx.Choice(parent, name=f"{label}, año")
        setattr(self, f"{prefix}_year", year)
        choices.Add(year, 0)
        for c in (day, month, year):
            c.Bind(wx.EVT_CHOICE, lambda e, p=prefix: self._on_date_choice(p, e))
        box.Add(choices, 0, wx.EXPAND)
        container_sizer.Add(box, 0, wx.EXPAND | wx.BOTTOM, 8)

    def _populate_date_choices(self):
        years = [str(y) for y in range(self.allowed_min_date.year, self.allowed_max_date.year + 1)]
        for prefix in ("travel", "from", "to"):
            year = getattr(self, f"{prefix}_year", None)
            if year is not None:
                current = year.GetStringSelection()
                year.Set(years)
                if current in years:
                    year.SetStringSelection(current)

    def _clamp_allowed_date(self, value: date) -> date:
        return min(max(value, self.allowed_min_date), self.allowed_max_date)

    def _set_date_value(self, prefix: str, value: date):
        value = self._clamp_allowed_date(value)
        text = getattr(self, f"{prefix}_date")
        day = getattr(self, f"{prefix}_day")
        month = getattr(self, f"{prefix}_month")
        year = getattr(self, f"{prefix}_year")
        text.ChangeValue(value.strftime("%d-%m-%Y"))
        day.SetSelection(value.day - 1)
        month.SetSelection(value.month - 1)
        years = [year.GetString(i) for i in range(year.GetCount())]
        if str(value.year) in years:
            year.SetStringSelection(str(value.year))

    def _date_from_text(self, prefix: str) -> date | None:
        text = getattr(self, f"{prefix}_date").GetValue().strip()
        try:
            return datetime.strptime(text, "%d-%m-%Y").date()
        except ValueError:
            return None

    def _on_date_text_key(self, prefix: str, event):
        key = event.GetKeyCode()
        if key in (wx.WXK_UP, wx.WXK_DOWN):
            current = self._date_from_text(prefix) or self.allowed_min_date
            delta = 1 if key == wx.WXK_UP else -1
            self._set_date_value(prefix, current + timedelta(days=delta))
            return
        event.Skip()

    def _sync_choices_from_text(self, prefix: str, event):
        value = self._date_from_text(prefix)
        if value is not None and self.allowed_min_date <= value <= self.allowed_max_date:
            day = getattr(self, f"{prefix}_day")
            month = getattr(self, f"{prefix}_month")
            year = getattr(self, f"{prefix}_year")
            day.SetSelection(value.day - 1)
            month.SetSelection(value.month - 1)
            if year.FindString(str(value.year)) != wx.NOT_FOUND:
                year.SetStringSelection(str(value.year))
        event.Skip()

    def _on_date_choice(self, prefix: str, event):
        import calendar
        day_ctrl = getattr(self, f"{prefix}_day")
        month_ctrl = getattr(self, f"{prefix}_month")
        year_ctrl = getattr(self, f"{prefix}_year")
        if day_ctrl.GetSelection() == wx.NOT_FOUND or month_ctrl.GetSelection() == wx.NOT_FOUND or not year_ctrl.GetStringSelection():
            return
        y = int(year_ctrl.GetStringSelection())
        m = month_ctrl.GetSelection() + 1
        d = day_ctrl.GetSelection() + 1
        d = min(d, calendar.monthrange(y, m)[1])
        self._set_date_value(prefix, date(y, m, d))
        event.Skip()

    def _after_allowed_date_range(self, result, error):
        try:
            # GetValue también confirma que el control sigue vivo; una respuesta
            # tardía debe ignorarse si el usuario ya salió de esta pantalla.
            self.travel_date.GetValue()
        except (AttributeError, RuntimeError):
            return
        if error or not result:
            if error:
                self._announce(f"No se pudieron actualizar los límites de fechas de CNRT: {error}")
            return
        previous_min = self.allowed_min_date
        self.allowed_min_date, self.allowed_max_date = result
        self._populate_date_choices()

        travel_current = self._date_from_text("travel")
        from_current = self._date_from_text("from")
        to_current = self._date_from_text("to")

        self._set_date_value(
            "travel",
            self.allowed_min_date if travel_current is None or travel_current <= previous_min else travel_current,
        )
        self._set_date_value(
            "from",
            self.allowed_min_date if from_current is None or from_current <= previous_min else from_current,
        )
        default_to = self._clamp_allowed_date(self.allowed_min_date + timedelta(days=1))
        if to_current is None or to_current <= previous_min + timedelta(days=1):
            self._set_date_value("to", default_to)
        else:
            self._set_date_value("to", to_current)

        self._announce(
            f"CNRT admite fechas desde {self.allowed_min_date.strftime('%d/%m/%Y')} "
            f"hasta {self.allowed_max_date.strftime('%d/%m/%Y')}."
        )

    def _on_search_mode_change(self, event, move_focus=True):
        specific = self.mode_specific.GetValue()
        ranged = self.mode_range.GetValue()
        scan_all = self.mode_all.GetValue()

        self.specific_panel.Show(specific)
        self.range_panel.Show(ranged)

        if specific:
            self.search_dates_button.SetLabel("Buscar &fecha")
            self.search_dates_button.SetName("Buscar fecha")
        elif ranged:
            self.search_dates_button.SetLabel("Buscar &fechas")
            self.search_dates_button.SetName("Buscar fechas")
        else:
            self.search_dates_button.SetLabel("Escanear todas las &fechas disponibles")
            self.search_dates_button.SetName("Escanear todas las fechas disponibles")

        self._apply_control_theme()
        self.content.Layout()
        self.panel.Layout()
        if move_focus:
            selected_mode = (
                self.mode_specific if specific else
                self.mode_range if ranged else
                self.mode_all
            )
            wx.CallAfter(selected_mode.SetFocus)
        if event is not None:
            event.Skip()

    def _validated_date(self, prefix: str, label: str) -> date | None:
        value = self._date_from_text(prefix)
        if value is None:
            wx.MessageBox(f"Ingrese {label} con formato DD-MM-AAAA.", "Fecha inválida", wx.OK | wx.ICON_WARNING)
            getattr(self, f"{prefix}_date").SetFocus()
            return None
        if value < self.allowed_min_date or value > self.allowed_max_date:
            wx.MessageBox(
                f"{label.capitalize()} debe estar entre {self.allowed_min_date.strftime('%d-%m-%Y')} y "
                f"{self.allowed_max_date.strftime('%d-%m-%Y')}.",
                "Fecha fuera del período permitido",
                wx.OK | wx.ICON_WARNING,
            )
            getattr(self, f"{prefix}_date").SetFocus()
            return None
        return value

    def _validate_search_common(self) -> tuple[Locality, Locality] | None:
        origin = self._resolve_locality("origin")
        destination = self._resolve_locality("destination")
        if origin is None or destination is None:
            wx.MessageBox(
                "Seleccione un origen y un destino en sus cuadros combinados editables. Escriba para filtrar, use flechas arriba y abajo y pulse Enter para elegir.",
                "Faltan datos",
                wx.OK | wx.ICON_WARNING,
            )
            return None
        if origin.id == destination.id:
            wx.MessageBox("Origen y destino deben ser diferentes.", "Revise la búsqueda", wx.OK | wx.ICON_WARNING)
            return None
        self.selected_origin = origin
        self.selected_destination = destination
        self.selected_quantity = int(self.quantity.GetStringSelection())
        return origin, destination

    def on_search_dates(self, event):
        common = self._validate_search_common()
        if common is None:
            return
        if self.mode_specific.GetValue():
            chosen = self._validated_date("travel", "la fecha")
            if chosen is None:
                return
            self._start_scan(chosen, chosen)
            return

        if self.mode_all.GetValue():
            self._start_scan(None, None)
            return

        start_date = self._validated_date("from", "la fecha desde")
        if start_date is None:
            return
        end_date = self._validated_date("to", "la fecha hasta")
        if end_date is None:
            return
        if end_date < start_date:
            wx.MessageBox("La fecha Hasta no puede ser anterior a Desde.", "Rango inválido", wx.OK | wx.ICON_WARNING)
            self.to_date.SetFocus()
            return
        self._start_scan(start_date, end_date)

    # Compatibilidad con nombres usados por versiones anteriores.
    def on_search_selected_date(self, event):
        self.mode_specific.SetValue(True)
        self.mode_range.SetValue(False)
        self.mode_all.SetValue(False)
        self.on_search_dates(event)

    def on_scan_all_dates(self, event):
        self.mode_specific.SetValue(False)
        self.mode_range.SetValue(False)
        self.mode_all.SetValue(True)
        self.on_search_dates(event)

    def _start_scan(self, start_date: date | None, end_date: date | None):
        self.scan_cancel_event = threading.Event()
        kwargs = dict(
            origin=self.selected_origin,
            destination=self.selected_destination,
            quantity=self.selected_quantity,
            delay_seconds=float(self.delay.GetValue()),
            progress=self._scan_progress,
            cancel_event=self.scan_cancel_event,
        )
        if start_date is not None:
            kwargs["start_date"] = start_date
        if end_date is not None:
            kwargs["end_date"] = end_date
        self._busy("Comenzando la búsqueda de pasajes...")
        self.worker.submit("scan_availability", callback=self._after_scan, **kwargs)

    # Compatibilidad con llamadas antiguas y pruebas externas.
    def on_scan(self, event):
        self.on_search_dates(event)

    def _scan_progress(self, current, total, day, found):
        wx.CallAfter(self._announce, f"{current} de {total}: {day.strftime('%d/%m/%Y')}, {found} servicios disponibles.")

    def on_cancel_scan(self, event):
        if self.scan_cancel_event:
            self.scan_cancel_event.set()
            self._announce("Se solicitó cancelar la búsqueda.")

    def _after_scan(self, result: ScanResult | None, error):
        self._done()
        if error:
            wx.MessageBox(str(error), "Error durante la búsqueda", wx.OK | wx.ICON_ERROR)
            self._announce(f"Error de búsqueda: {error}")
            return
        assert result is not None
        self.scan_services = result.services
        self.last_scan_result = result
        self._show_results(result)

    def _show_results(self, result: ScanResult):
        self._clear_content()
        self._heading("Resultados de búsqueda")
        summary = f"Fechas revisadas: {result.scanned_dates}. Fechas con disponibilidad: {result.available_dates}. Servicios disponibles: {len(result.services)}."
        if result.cancelled:
            summary += " La búsqueda fue cancelada antes de terminar."
        self.content_sizer.Add(wx.StaticText(self.content, label=summary), 0, wx.BOTTOM, 8)
        self.results_list = wx.ListBox(self.content, choices=[s.display_text() for s in result.services], name="Servicios disponibles")
        self.content_sizer.Add(self.results_list, 1, wx.EXPAND | wx.BOTTOM, 10)
        row = wx.WrapSizer(wx.HORIZONTAL)
        reserve = wx.Button(self.content, label="&Reservar servicio seleccionado")
        reserve.Bind(wx.EVT_BUTTON, self.on_reserve_selected)
        self._style_button(reserve, "primary")
        row.Add(reserve, 0, wx.RIGHT, 8)
        again = wx.Button(self.content, label="Nueva búsqueda")
        again.Bind(wx.EVT_BUTTON, self._show_search)
        row.Add(again, 0, wx.RIGHT, 8)
        menu = wx.Button(self.content, label="Volver al menú")
        menu.Bind(wx.EVT_BUTTON, lambda e: self._show_main_menu())
        row.Add(menu, 0)
        self.content_sizer.Add(row, 0)
        if result.errors:
            self.content_sizer.Add(wx.StaticText(self.content, label=f"Hubo {len(result.errors)} fechas con error. Revise el cuadro Estado."), 0, wx.TOP, 8)
            for err in result.errors[:5]:
                self._announce(err)
        self._apply_control_theme()
        self.content.Layout()
        if result.services:
            self.results_list.SetSelection(0)
            self.results_list.SetFocus()
            wx.Bell()
        self._announce(summary)

    # ---------------- Reserva ----------------
    def on_reserve_selected(self, event):
        idx = self.results_list.GetSelection()
        if idx == wx.NOT_FOUND:
            wx.MessageBox("Seleccione un servicio.", "Reserva", wx.OK | wx.ICON_INFORMATION)
            return
        self.pending_service = self.scan_services[idx]
        self._show_preference()

    def _show_preference(self):
        self._clear_content()
        self._heading("Preferencia y preparación de la reserva")
        self.content_sizer.Add(wx.StaticText(self.content, label=self.pending_service.display_text()), 0, wx.BOTTOM, 10)
        self.content_sizer.Add(wx.StaticText(self.content, label="Preferencia de viaje"), 0)
        self.preference = wx.RadioBox(self.content, choices=["Planta baja", "Planta alta"], majorDimension=1, style=wx.RA_SPECIFY_ROWS, name="Preferencia de viaje")
        self.content_sizer.Add(self.preference, 0, wx.BOTTOM, 8)
        self.content_sizer.Add(wx.StaticText(self.content, label="Motivo de preferencia, opcional, máximo 30 caracteres"), 0)
        self.reason = wx.TextCtrl(self.content, name="Motivo de preferencia")
        self.reason.SetMaxLength(30)
        self.content_sizer.Add(self.reason, 0, wx.EXPAND | wx.BOTTOM, 10)
        row = wx.WrapSizer(wx.HORIZONTAL)
        prepare = wx.Button(self.content, label="Preparar reserva")
        prepare.Bind(wx.EVT_BUTTON, self.on_prepare)
        self._style_button(prepare, "primary")
        row.Add(prepare, 0, wx.RIGHT, 8)
        back = wx.Button(self.content, label="Volver a resultados")
        back.Bind(wx.EVT_BUTTON, lambda e: self._show_results(self.last_scan_result or ScanResult(services=self.scan_services)))
        row.Add(back, 0)
        self.content_sizer.Add(row, 0)
        self._apply_control_theme()
        self.content.Layout()
        self.preference.SetFocus()

    def on_prepare(self, event):
        if not (self.selected_origin and self.selected_destination and self.pending_service):
            return
        # CNRT mantiene la reserva pendiente en la página /confirmarReserva.
        # Cualquier navegación posterior (por ejemplo, abrir Mi información para
        # obtener el correo) abandona esa pantalla y hace imposible confirmar.
        # Por eso obtenemos el perfil ANTES de preparar la reserva.
        preference = "1" if self.preference.GetSelection() == 0 else "2"
        reason = self.reason.GetValue()
        self._busy("Leyendo el correo y revalidando el servicio...")
        self.worker.submit(
            "get_profile",
            callback=lambda profile, err: self._after_profile_for_prepare(
                profile if not err else Profile(),
                preference,
                reason,
                err,
            ),
        )

    def _after_profile_for_prepare(self, profile: Profile, preference: str, reason: str, profile_error):
        if profile_error:
            # El correo también puede escribirse manualmente en la pantalla final.
            # Continuamos porque prepare_reservation abre de nuevo la búsqueda y,
            # desde ese momento, no habrá más navegaciones hasta confirmar/cancelar.
            self._announce(f"No se pudo leer el correo guardado: {profile_error}. Podrá ingresarlo manualmente.")
        self._busy("Revalidando el servicio y preparando la pantalla de confirmación...")
        self.worker.submit(
            "prepare_reservation",
            self.selected_origin,
            self.selected_destination,
            self.pending_service,
            self.selected_quantity,
            preference,
            reason,
            callback=lambda summary, err: self._after_prepare(summary, err, profile),
        )

    def _after_prepare(self, summary, error, profile: Profile):
        self._done()
        if error:
            wx.MessageBox(str(error), "No se pudo preparar la reserva", wx.OK | wx.ICON_ERROR)
            self._announce(f"No se pudo preparar la reserva: {error}")
            return
        # No navegar desde aquí: CNRT debe permanecer en /confirmarReserva
        # hasta que el usuario confirme o cancele.
        self._show_confirmation(summary, profile)

    def _show_confirmation(self, summary, profile: Profile):
        self.profile = profile
        self._clear_content()
        self._heading("Confirmación final")
        self.content_sizer.Add(wx.StaticText(self.content, label=summary.spoken_summary() or summary.raw_text[:1000]), 0, wx.EXPAND | wx.BOTTOM, 10)
        self.content_sizer.Add(wx.StaticText(self.content, label="Correo donde la empresa enviará el pasaje"), 0)
        self.confirm_email = wx.TextCtrl(self.content, value=profile.email, name="Correo para recibir el pasaje")
        self.content_sizer.Add(self.confirm_email, 0, wx.EXPAND | wx.BOTTOM, 10)
        warning = wx.StaticText(self.content, label="El siguiente botón realiza la solicitud definitiva en CNRT.")
        warning._cnrt_text_role = "warning"
        warning_font = warning.GetFont()
        warning_font.MakeBold()
        warning.SetFont(warning_font)
        self.content_sizer.Add(warning, 0, wx.BOTTOM, 10)
        row = wx.WrapSizer(wx.HORIZONTAL)
        final = wx.Button(self.content, label="Confirmar y enviar solicitud")
        final.Bind(wx.EVT_BUTTON, self.on_final_confirm)
        self._style_button(final, "primary")
        row.Add(final, 0, wx.RIGHT, 8)
        cancel = wx.Button(self.content, label="No reservar")
        cancel.Bind(wx.EVT_BUTTON, lambda e: self._show_main_menu())
        row.Add(cancel, 0)
        self.content_sizer.Add(row, 0)
        self._apply_control_theme()
        self.content.Layout()
        self.confirm_email.SetFocus()
        self._announce("Reserva preparada. Revise el resumen antes de confirmar.")

    def on_final_confirm(self, event):
        email = self.confirm_email.GetValue().strip()
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            wx.MessageBox("Ingrese una dirección de correo válida.", "Correo", wx.OK | wx.ICON_WARNING)
            return
        self._busy("Enviando la solicitud definitiva a CNRT...")
        self.worker.submit("confirm_reservation", email, callback=self._after_final_confirm)

    def _after_final_confirm(self, summary, error):
        self._done()
        if error:
            wx.MessageBox(str(error), "CNRT no confirmó la solicitud", wx.OK | wx.ICON_ERROR)
            self._announce(f"Error al confirmar: {error}")
            return
        if (
            self.telemetry.enabled
            and self.telemetry.configured
            and self.selected_origin
            and self.selected_destination
            and self.pending_service
        ):
            tracking_id = self.reservation_tracker.register_created(
                company=self.pending_service.company,
                origin=self.selected_origin.text,
                destination=self.selected_destination.text,
                travel_date=self.pending_service.date.isoformat(),
                departure=self.pending_service.departure,
                quantity=str(self.selected_quantity),
            )
            self.telemetry.capture_reservation(
                "reservation_created",
                tracking_id=tracking_id,
                company=self.pending_service.company,
                origin=self.selected_origin.text,
                destination=self.selected_destination.text,
                travel_date=self.pending_service.date.isoformat(),
                state="created",
            )
        self._clear_content()
        self._heading("Solicitud confirmada")
        self.content_sizer.Add(wx.StaticText(self.content, label=summary.spoken_summary() or summary.raw_text[:1200]), 0, wx.EXPAND | wx.BOTTOM, 12)
        b = wx.Button(self.content, label="Volver al menú")
        b.Bind(wx.EVT_BUTTON, lambda e: self._show_main_menu())
        self.content_sizer.Add(b, 0)
        self._apply_control_theme()
        self.content.Layout()
        b.SetFocus()
        wx.Bell()
        self._announce("Reserva realizada con éxito. Solicitud confirmada por CNRT.")
        wx.MessageBox(
            "La reserva se realizó correctamente y CNRT confirmó la solicitud.",
            "Reserva realizada con éxito",
            wx.OK | wx.ICON_INFORMATION,
        )

    # ---------------- Perfil ----------------
    def on_profile(self, event):
        self._busy("Leyendo Mi información...")
        self.worker.submit("get_profile", callback=self._after_profile)

    def _after_profile(self, profile, error):
        self._done()
        if error:
            wx.MessageBox(str(error), "Mi información", wx.OK | wx.ICON_ERROR)
            return
        self.profile = profile
        self._clear_content()
        self._heading("Mi información")
        self.content_sizer.Add(wx.StaticText(self.content, label="Teléfono"), 0)
        self.profile_phone = wx.TextCtrl(self.content, value=profile.phone, name="Teléfono")
        self.content_sizer.Add(self.profile_phone, 0, wx.EXPAND | wx.BOTTOM, 8)
        self.content_sizer.Add(wx.StaticText(self.content, label="Correo electrónico"), 0)
        self.profile_email = wx.TextCtrl(self.content, value=profile.email, name="Correo electrónico")
        self.content_sizer.Add(self.profile_email, 0, wx.EXPAND | wx.BOTTOM, 8)
        row = wx.WrapSizer(wx.HORIZONTAL)
        save = wx.Button(self.content, label="Guardar cambios")
        save.Bind(wx.EVT_BUTTON, self.on_save_profile)
        self._style_button(save, "primary")
        row.Add(save, 0, wx.RIGHT, 8)
        back = wx.Button(self.content, label="Volver al menú")
        back.Bind(wx.EVT_BUTTON, lambda e: self._show_main_menu())
        row.Add(back, 0)
        self.content_sizer.Add(row, 0)
        self._apply_control_theme()
        self.content.Layout()
        self.profile_phone.SetFocus()

    def on_save_profile(self, event):
        self._busy("Actualizando Mi información...")
        self.worker.submit("update_profile", self.profile_phone.GetValue(), self.profile_email.GetValue(), callback=self._after_save_profile)

    def _after_save_profile(self, profile, error):
        self._done()
        if error:
            wx.MessageBox(str(error), "No se pudo actualizar", wx.OK | wx.ICON_ERROR)
            return
        self.profile = profile
        self._announce("Los datos fueron actualizados.")
        wx.MessageBox("Los datos fueron actualizados correctamente.", "Mi información", wx.OK | wx.ICON_INFORMATION)

    # ---------------- Solicitudes ----------------
    def on_requests(self, event):
        self._busy("Consultando Mis solicitudes...")
        self.worker.submit("list_requests", callback=self._after_requests)

    def _after_requests(self, records, error):
        self._done()
        if error:
            wx.MessageBox(str(error), "Mis solicitudes", wx.OK | wx.ICON_ERROR)
            return
        self.requests = records or []
        self._capture_request_status_telemetry(self.requests)
        self._clear_content()
        self._heading("Mis solicitudes")
        if not self.requests:
            self.content_sizer.Add(wx.StaticText(self.content, label="No hay solicitudes para mostrar."), 0, wx.BOTTOM, 10)
        self.requests_list = wx.ListBox(self.content, choices=[r.text for r in self.requests], name="Lista de solicitudes")
        self.requests_list.Bind(wx.EVT_LISTBOX, self.on_request_selected)
        self.content_sizer.Add(self.requests_list, 1, wx.EXPAND | wx.BOTTOM, 8)
        self.request_details = wx.TextCtrl(
            self.content, style=wx.TE_READONLY | wx.TE_MULTILINE, size=(-1, 85), name="Detalles de la solicitud seleccionada"
        )
        self.content_sizer.Add(self.request_details, 0, wx.EXPAND | wx.BOTTOM, 10)

        actions = wx.WrapSizer(wx.HORIZONTAL)
        self.request_email_button = wx.Button(self.content, label="Modificar &correo")
        self.request_email_button.Bind(wx.EVT_BUTTON, self.on_modify_request_email)
        actions.Add(self.request_email_button, 0, wx.RIGHT, 8)
        self.request_pref_button = wx.Button(self.content, label="Modificar &preferencia")
        self.request_pref_button.Bind(wx.EVT_BUTTON, self.on_modify_request_preference)
        actions.Add(self.request_pref_button, 0, wx.RIGHT, 8)
        self.request_cancel_button = wx.Button(self.content, label="&Anular solicitud")
        self.request_cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel_request)
        self._style_button(self.request_cancel_button, "danger")
        actions.Add(self.request_cancel_button, 0, wx.RIGHT, 8)
        self.content_sizer.Add(actions, 0, wx.BOTTOM, 8)

        row = wx.WrapSizer(wx.HORIZONTAL)
        refresh = wx.Button(self.content, label="Actualizar")
        refresh.Bind(wx.EVT_BUTTON, self.on_requests)
        row.Add(refresh, 0, wx.RIGHT, 8)
        back = wx.Button(self.content, label="Volver al menú")
        back.Bind(wx.EVT_BUTTON, lambda e: self._show_main_menu())
        row.Add(back, 0)
        self.content_sizer.Add(row, 0)
        self._apply_control_theme()
        self.content.Layout()
        if self.requests:
            self.requests_list.SetSelection(0)
            self.on_request_selected(None)
            self.requests_list.SetFocus()
        else:
            self._set_request_action_state(None)
        self._announce(f"Mis solicitudes: {len(self.requests)} elementos.")

    def _capture_request_status_telemetry(self, records: list[RequestRecord]):
        if not self.telemetry.enabled or not self.telemetry.configured:
            return
        occurrences: dict[tuple[str, str, str, str, str, str], int] = {}
        for record in records:
            key = (
                record.company.casefold(),
                record.origin.casefold(),
                record.destination.casefold(),
                normalize_travel_date(record.date_text),
                record.departure.casefold(),
                record.quantity.casefold(),
            )
            occurrence = occurrences.get(key, 0)
            occurrences[key] = occurrence + 1
            try:
                observation = self.reservation_tracker.observe(record, occurrence=occurrence)
                if observation is None:
                    continue
                self.telemetry.capture_reservation(
                    event_name_for_state(observation.state),
                    tracking_id=observation.tracking_id,
                    company=record.company,
                    origin=record.origin,
                    destination=record.destination,
                    travel_date=normalize_travel_date(record.date_text),
                    state=observation.state,
                    extra={"first_observed": observation.first_observed},
                )
            except Exception:
                # Las estadísticas nunca deben impedir mostrar Mis solicitudes.
                continue

    def _selected_request(self):
        idx = self.requests_list.GetSelection() if hasattr(self, "requests_list") else wx.NOT_FOUND
        if idx == wx.NOT_FOUND or idx < 0 or idx >= len(self.requests):
            return None
        return self.requests[idx]

    def _set_request_action_state(self, record):
        if hasattr(self, "request_email_button"):
            self.request_email_button.Enable(bool(record and record.can_modify_email))
            self.request_pref_button.Enable(bool(record and record.can_modify_preference))
            self.request_cancel_button.Enable(bool(record and record.cancellable))

    def on_request_selected(self, event):
        record = self._selected_request()
        self._set_request_action_state(record)
        if hasattr(self, "request_details"):
            self.request_details.SetValue(record.spoken_details() if record else "")

    def on_modify_request_email(self, event):
        record = self._selected_request()
        if not record or not record.can_modify_email:
            wx.MessageBox("CNRT no permite modificar el correo de esta solicitud.", "Modificar correo", wx.OK | wx.ICON_INFORMATION)
            return
        dlg = wx.TextEntryDialog(self, record.spoken_details() + "\n\nNuevo correo:", "Modificar correo de la solicitud", value=record.email)
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            email = dlg.GetValue().strip()
        finally:
            dlg.Destroy()
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            wx.MessageBox("Ingrese una dirección de correo válida.", "Correo", wx.OK | wx.ICON_WARNING)
            return
        answer = wx.MessageBox(
            f"¿Confirma cambiar el correo de esta solicitud a {email}?",
            "Confirmar cambio de correo", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        )
        if answer != wx.YES:
            return
        self._busy("Modificando el correo de la solicitud...")
        self.worker.submit("modify_request_email", record, email, callback=self._after_request_change)

    def on_modify_request_preference(self, event):
        record = self._selected_request()
        if not record or not record.can_modify_preference:
            wx.MessageBox("CNRT no permite modificar la preferencia de esta solicitud.", "Modificar preferencia", wx.OK | wx.ICON_INFORMATION)
            return
        dlg = wx.SingleChoiceDialog(self, record.spoken_details() + "\n\nSeleccione la nueva preferencia:", "Modificar preferencia", ["Planta baja", "Planta alta"])
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            selection = dlg.GetSelection()
        finally:
            dlg.Destroy()
        reason_dlg = wx.TextEntryDialog(self, "Motivo de la preferencia (opcional, máximo 30 caracteres):", "Motivo de preferencia")
        try:
            if reason_dlg.ShowModal() != wx.ID_OK:
                return
            reason = reason_dlg.GetValue()[:30]
        finally:
            reason_dlg.Destroy()
        preference = "1" if selection == 0 else "2"
        label = "planta baja" if preference == "1" else "planta alta"
        answer = wx.MessageBox(
            f"¿Confirma cambiar la preferencia a {label}?",
            "Confirmar preferencia", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        )
        if answer != wx.YES:
            return
        self._busy("Modificando la preferencia de viaje...")
        self.worker.submit("modify_request_preference", record, preference, reason, callback=self._after_request_change)

    def _after_request_change(self, result, error):
        self._done()
        if error:
            wx.MessageBox(str(error), "No se pudo modificar la solicitud", wx.OK | wx.ICON_ERROR)
            self._announce(f"Error: {error}")
            return
        wx.MessageBox(str(result), "Solicitud actualizada", wx.OK | wx.ICON_INFORMATION)
        self._announce(str(result))
        self.on_requests(None)

    def on_cancel_request(self, event):
        record = self._selected_request()
        if not record or not record.cancellable:
            wx.MessageBox("CNRT no ofrece la acción Anular para esta solicitud.", "Anular", wx.OK | wx.ICON_INFORMATION)
            return
        answer = wx.MessageBox(
            record.spoken_details() + "\n\n¿Confirma que desea ANULAR esta solicitud en CNRT?",
            "Confirmar anulación", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING
        )
        if answer != wx.YES:
            return
        self._busy("Enviando la anulación a CNRT...")
        self.worker.submit(
            "cancel_request",
            record,
            callback=lambda result, error: self._after_cancel_request(result, error, record),
        )

    def _after_cancel_request(self, result, error, record: RequestRecord):
        self._done()
        if error:
            wx.MessageBox(str(error), "No se pudo anular", wx.OK | wx.ICON_ERROR)
            self._announce(f"Error al anular: {error}")
            return
        if self.telemetry.enabled and self.telemetry.configured:
            try:
                observation = self.reservation_tracker.mark_cancelled(record)
                if observation is not None:
                    self.telemetry.capture_reservation(
                        "reservation_cancelled",
                        tracking_id=observation.tracking_id,
                        company=record.company,
                        origin=record.origin,
                        destination=record.destination,
                        travel_date=normalize_travel_date(record.date_text),
                        state=observation.state,
                        extra={"first_observed": observation.first_observed},
                    )
            except Exception:
                pass
        self._announce("Reserva anulada con éxito. La anulación fue verificada por CNRT.")
        wx.MessageBox(
            "La reserva fue anulada correctamente y CNRT confirmó la anulación.",
            "Reserva anulada con éxito",
            wx.OK | wx.ICON_INFORMATION,
        )
        self.on_requests(None)

    # ---------------- sesión/ventana ----------------
    def on_logout(self, event):
        self._busy("Cerrando sesión...")
        self.worker.submit("logout", callback=self._after_logout)

    def _after_logout(self, result, error):
        self._done()
        self._show_login()
        self._announce("Sesión cerrada.")

    def on_char_hook(self, event):
        key = event.GetKeyCode()
        if event.ControlDown():
            if key in (ord("+"), ord("="), wx.WXK_NUMPAD_ADD):
                self._change_text_scale(0.25)
                return
            if key in (ord("-"), wx.WXK_NUMPAD_SUBTRACT):
                self._change_text_scale(-0.25)
                return
            if key in (ord("0"), wx.WXK_NUMPAD0):
                self._set_text_scale(1.0)
                return
        if key == wx.WXK_F6:
            self.status.SetFocus()
            return
        event.Skip()

    def on_close(self, event):
        if self.scan_cancel_event:
            self.scan_cancel_event.set()
        try:
            self.worker.stop()
        except Exception:
            pass
        try:
            self.telemetry.shutdown()
        except Exception:
            pass
        self.Destroy()


class PasajesAccesiblesCnrtApp(wx.App):
    def OnInit(self):
        frame = MainFrame()
        frame.Show()
        return True


def main():
    app = PasajesAccesiblesCnrtApp(False)
    app.MainLoop()


if __name__ == "__main__":
    main()
