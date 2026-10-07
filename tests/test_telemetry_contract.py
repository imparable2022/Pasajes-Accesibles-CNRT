import unittest
from pathlib import Path

from pasajes_accesibles_cnrt import telemetry

ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / "pasajes_accesibles_cnrt" / "app.py").read_text(encoding="utf-8")
TELEMETRY_SOURCE = (ROOT / "pasajes_accesibles_cnrt" / "telemetry.py").read_text(encoding="utf-8")


class TelemetryContractTests(unittest.TestCase):
    def test_single_consent_explains_all_categories_and_exclusions(self):
        self.assertIn("_telemetry_consent_text", APP_SOURCE)
        self.assertIn("datos técnicos generales del equipo", APP_SOURCE)
        self.assertIn("NVDA, JAWS, Narrador, Lupa de Windows", APP_SOURCE)
        self.assertIn("empresa, origen, destino, fecha del viaje", APP_SOURCE)
        self.assertIn("Pasaje Emitido", APP_SOURCE)
        self.assertIn("ubicación aproximada", APP_SOURCE)
        self.assertIn("se enviarán a PostHog y se procesarán en su región de Estados Unidos", APP_SOURCE)
        self.assertIn("Nunca se enviarán nombre, apellido, DNI, número de CUD", APP_SOURCE)
        self.assertIn("wx.YES_NO | wx.NO_DEFAULT", APP_SOURCE)
        self.assertIn('self.visual_config.Write("telemetry/consent"', APP_SOURCE)

    def test_help_menu_allows_changing_telemetry_consent(self):
        self.assertIn('"&Privacidad y estadísticas"', APP_SOURCE)
        self.assertIn("self._manage_telemetry_consent", APP_SOURCE)
        self.assertIn("Desactivarlo detiene futuros envíos", APP_SOURCE)

    def test_reservation_lifecycle_events_are_not_linked_to_installation_id(self):
        old_token = telemetry.POSTHOG_PROJECT_TOKEN
        telemetry.POSTHOG_PROJECT_TOKEN = "phc_test"
        client = telemetry.TelemetryClient(installation_id="installation-test", enabled=True)
        captured = []
        client._enqueue = lambda event, distinct_id, properties: captured.append((event, distinct_id, properties))
        try:
            client.capture_reservation(
                "reservation_ticket_issued",
                tracking_id="reservation-test",
                company="Empresa",
                origin="Origen",
                destination="Destino",
                travel_date="2026-10-07",
                state="ticket_issued",
            )
        finally:
            client.shutdown()
            telemetry.POSTHOG_PROJECT_TOKEN = old_token
        self.assertEqual(1, len(captured))
        event, distinct_id, props = captured[0]
        self.assertEqual("reservation_ticket_issued", event)
        self.assertEqual("reservation-test", distinct_id)
        self.assertNotEqual("installation-test", distinct_id)
        self.assertNotIn("installation_id", props)
        self.assertFalse(props["$process_person_profile"])
        self.assertEqual("ticket_issued", props["reservation_state"])

    def test_telemetry_module_does_not_capture_personal_reservation_fields(self):
        forbidden = [
            "document_number",
            "credential_number",
            "reservation_id",
            "phone",
            "confirm_email",
        ]
        for token in forbidden:
            self.assertNotIn(token, TELEMETRY_SOURCE)

    def test_accessibility_detection_is_limited_to_requested_tools(self):
        self.assertIn('"nvda.exe"', TELEMETRY_SOURCE)
        self.assertIn('"jfw.exe"', TELEMETRY_SOURCE)
        self.assertIn('"narrator.exe"', TELEMETRY_SOURCE)
        self.assertIn('"magnify.exe"', TELEMETRY_SOURCE)
        self.assertIn('"sticky_keys"', TELEMETRY_SOURCE)
        self.assertIn('"filter_keys"', TELEMETRY_SOURCE)
        self.assertIn('"toggle_keys"', TELEMETRY_SOURCE)
        self.assertIn('"mouse_keys"', TELEMETRY_SOURCE)

    def test_project_token_is_required_before_consent_is_shown(self):
        self.assertIn("if not self.telemetry.configured:\n            return", APP_SOURCE)
        self.assertIn("No se está enviando ningún dato.", APP_SOURCE)

    def test_distributed_posthog_configuration_targets_us_cloud(self):
        self.assertTrue(telemetry.DEFAULT_POSTHOG_PROJECT_TOKEN.startswith("phc_"))
        self.assertEqual("https://us.i.posthog.com", telemetry.DEFAULT_POSTHOG_HOST)
        self.assertEqual("https://us.i.posthog.com", telemetry.POSTHOG_HOST)

    def test_no_event_is_enqueued_without_consent(self):
        client = telemetry.TelemetryClient(installation_id="installation-test", enabled=False)
        captured = []
        client._enqueue = lambda event, distinct_id, properties: captured.append((event, distinct_id, properties))
        try:
            client.capture_technical({"app_version": "test"})
            client.capture_reservation(
                "reservation_created",
                tracking_id="reservation-test",
                company="Empresa",
                origin="Origen",
                destination="Destino",
                travel_date="2026-10-07",
                state="created",
            )
        finally:
            client.shutdown()
        self.assertEqual([], captured)


if __name__ == "__main__":
    unittest.main()
