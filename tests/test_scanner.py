import unittest
from datetime import date

from pasajes_accesibles_cnrt.client import CnrtClient
from pasajes_accesibles_cnrt.models import Locality


AVAILABLE = """
<html><body><div id='id_1'>EMPRESA PRUEBA
<div><label for='100_10:00'>Sale 10:00 - Llega 12:00<br>Categoría: Semicama<br>Solicitados: 0<br>Cupo Total: 4</label></div>
<div><input id='100_10:00' type='radio' name='servicioARealizar_horario' value='100_10:00'></div>
</div></body></html>
"""
NO_AVAILABLE = "<html><body><div class='alert alert-danger'>NO DISPONIBLE - CUPO CUBIERTO</div></body></html>"


class FakeClient(CnrtClient):
    def __init__(self):
        self.calls = []

    def _ensure_session(self):
        return None

    def allowed_date_range(self, now=None):
        return date(2026, 10, 1), date(2026, 10, 5)

    def _post_search(self, origin, destination, day, quantity):
        self.calls.append(day)
        return AVAILABLE if day in {date(2026, 10, 2), date(2026, 10, 4)} else NO_AVAILABLE


class ScannerTests(unittest.TestCase):
    def test_scans_every_date_and_collects_only_available(self):
        c = FakeClient()
        result = c.scan_availability(
            Locality('1', 'ORIGEN'),
            Locality('2', 'DESTINO'),
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 5),
            delay_seconds=0,
        )
        self.assertEqual(result.scanned_dates, 5)
        self.assertEqual(len(c.calls), 5)
        self.assertEqual(result.available_dates, 2)
        self.assertEqual([s.date for s in result.services], [date(2026, 10, 2), date(2026, 10, 4)])


if __name__ == '__main__':
    unittest.main()
