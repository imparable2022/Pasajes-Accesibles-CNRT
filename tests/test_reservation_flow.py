import re
import unittest
from pathlib import Path


class ReservationFlowRegressionTests(unittest.TestCase):
    def test_profile_is_read_before_prepare_and_not_after(self):
        source = (Path(__file__).resolve().parents[1] / "pasajes_accesibles_cnrt" / "app.py").read_text(encoding="utf-8")

        on_prepare = re.search(
            r"    def on_prepare\(self, event\):(?P<body>.*?)(?=\n    def _after_profile_for_prepare)",
            source,
            re.S,
        )
        self.assertIsNotNone(on_prepare)
        self.assertIn('"get_profile"', on_prepare.group("body"))

        after_profile = re.search(
            r"    def _after_profile_for_prepare\(.*?\):(?P<body>.*?)(?=\n    def _after_prepare)",
            source,
            re.S,
        )
        self.assertIsNotNone(after_profile)
        self.assertIn('"prepare_reservation"', after_profile.group("body"))

        after_prepare = re.search(
            r"    def _after_prepare\(.*?\):(?P<body>.*?)(?=\n    def _show_confirmation)",
            source,
            re.S,
        )
        self.assertIsNotNone(after_prepare)
        self.assertNotIn('"get_profile"', after_prepare.group("body"))
        self.assertIn("self._show_confirmation(summary, profile)", after_prepare.group("body"))

    def test_datepicker_is_closed_before_quantity_and_quantity_uses_force(self):
        client = (Path(__file__).resolve().parents[1] / "pasajes_accesibles_cnrt" / "client.py").read_text(encoding="utf-8")
        self.assertIn('p.fill("#fechaSalida"', client)
        self.assertIn('data("DateTimePicker")', client)
        self.assertIn('picker.hide()', client)
        self.assertIn('qty.check(force=True)', client)
        self.assertIn('"CNRT no mostró la opción esperada para la cantidad de pasajes."', client)

    def test_two_passage_reservation_sends_and_verifies_companion(self):
        client = (Path(__file__).resolve().parents[1] / "pasajes_accesibles_cnrt" / "client.py").read_text(encoding="utf-8")
        self.assertIn("companion: Optional[Companion] = None", client)
        self.assertIn('p.select_option("#documentoOpciones"', client)
        self.assertIn('p.fill("#nroDocumento"', client)
        self.assertIn('p.fill("#apellido"', client)
        self.assertIn('p.fill("#nombre"', client)
        self.assertIn("expected_companion = {", client)
        self.assertIn("CNRT abrió la confirmación pero no conservó todos los datos del acompañante.", client)

    def test_companion_storage_is_separate_from_login_credentials(self):
        storage = (Path(__file__).resolve().parents[1] / "pasajes_accesibles_cnrt" / "storage.py").read_text(encoding="utf-8")
        self.assertIn("class CompanionStore(CredentialStore):", storage)
        self.assertIn('APP_DIR / "acompanante.dat"', storage)
        self.assertIn('APP_DIR / "credenciales.dat"', storage)

    def test_final_reservation_has_no_extra_confirmation_dialog_and_shows_success(self):
        source = (Path(__file__).resolve().parents[1] / "pasajes_accesibles_cnrt" / "app.py").read_text(encoding="utf-8")

        final_confirm = re.search(
            r"    def on_final_confirm\(self, event\):(?P<body>.*?)(?=\n    def _after_final_confirm)",
            source,
            re.S,
        )
        self.assertIsNotNone(final_confirm)
        self.assertIn('"confirm_reservation"', final_confirm.group("body"))
        self.assertNotIn("Confirmación definitiva", final_confirm.group("body"))
        self.assertNotIn("wx.YES_NO", final_confirm.group("body"))

        after_confirm = re.search(
            r"    def _after_final_confirm\(.*?\):(?P<body>.*?)(?=\n    # ---------------- Perfil)",
            source,
            re.S,
        )
        self.assertIsNotNone(after_confirm)
        self.assertIn("Reserva realizada con éxito", after_confirm.group("body"))
        self.assertIn("wx.MessageBox", after_confirm.group("body"))


if __name__ == "__main__":
    unittest.main()
