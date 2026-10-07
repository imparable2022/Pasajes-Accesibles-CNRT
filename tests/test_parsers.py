import unittest
from datetime import date

from pasajes_accesibles_cnrt.parsers import (
    is_confirmed,
    parse_available_services,
    parse_confirmation_summary,
    parse_constraints,
)


AVAILABLE = r"""
<html><body>
<form id="reservar" action="/web/seleccionarServicio" method="POST">
<div id="id_1" class="col-sm-12">
<input type="hidden" id="infoservicio" value="emp:20,serv:14367,sar:5780362,rec:5245" disabled>
<br>EMPRESA EL NORTE BIS S.R.L.<br>
<div class="col-sm-8">
<label for="5780362_18:30">
Sale 18:30 - Llega 20:35<br>Categoría: Semicama<br>Solicitados: 0<br>Cupo Total: 4
</label>
</div>
<div class="col-sm-4"><input id="5780362_18:30" type="radio" name="servicioARealizar_horario" value="5780362_18:30"/></div>
</div>
<p id="id_2"><input type="hidden" id="servicio_a_realizar" disabled value="999"><br>OTRA EMPRESA<br>
<label>Sale 20:00 - Llega 22:00<br>Categoría: Semicama<br>Solicitados: 4<br>Cupo Total: 4</label>
<div class="alert alert-danger">NO DISPONIBLE - CUPO CUBIERTO</div></p>
</form>
<script>var cantidadDiasReserva='30'; var cantidadHorasReserva='48';</script>
</body></html>
"""

CONFIRM = """
<html><body><h2>Confirmar Solicitud</h2><form action="/web/confirmarReserva">
<fieldset><legend>Usted va a realizar la siguiente solicitud</legend>
<dl><dd><strong>Destino</strong>: FLORENCIA (SANTA FE)</dd>
<dd><strong>Origen</strong>: RECONQUISTA (SANTA FE)</dd>
<dd><strong>Fecha de Salida</strong>: 26/10/2026</dd>
<dd><strong>Preferencia Viaje</strong>: Planta baja</dd>
<dd><strong>Horario de Salida</strong>: 18:30</dd>
<dd><strong>Cantidad de Pasajes</strong>: 1</dd>
<dd><strong>Empresa</strong>: EMPRESA EL NORTE BIS S.R.L.</dd></dl></fieldset>
</form></body></html>
"""

CONFIRMED = """
<html><body><h2>Solicitud Confirmada</h2>
<dd><strong>Destino</strong>: FLORENCIA (SANTA FE)</dd>
<dd><strong>Origen</strong>: RECONQUISTA (SANTA FE)</dd>
<dd><strong>Fecha de Salida</strong>: 26/10/2026</dd>
<dd><strong>Horario de Salida</strong>: 18:30</dd>
<dd><strong>Cantidad de Pasajes</strong>: 1</dd>
<dd><strong>Empresa</strong>: EMPRESA EL NORTE BIS S.R.L.</dd>
<dd><strong>Email</strong>: ejemplo@example.com</dd></body></html>
"""


class ParserTests(unittest.TestCase):
    def test_constraints(self):
        c = parse_constraints(AVAILABLE)
        self.assertEqual(c.min_hours, 48)
        self.assertEqual(c.max_days, 30)

    def test_only_available_radio_is_returned(self):
        services = parse_available_services(AVAILABLE, date(2026, 10, 26))
        self.assertEqual(len(services), 1)
        s = services[0]
        self.assertEqual(s.service_id, "5780362")
        self.assertEqual(s.departure, "18:30")
        self.assertEqual(s.arrival, "20:35")
        self.assertEqual(s.category, "Semicama")
        self.assertEqual(s.requested, 0)
        self.assertEqual(s.total_quota, 4)
        self.assertEqual(s.free_quota, 4)
        self.assertIn("EL NORTE", s.company)

    def test_confirmation_summary(self):
        s = parse_confirmation_summary(CONFIRM)
        self.assertIn("RECONQUISTA", s.origin)
        self.assertIn("FLORENCIA", s.destination)
        self.assertIn("18:30", s.departure)
        self.assertIn("EL NORTE", s.company)

    def test_confirmed(self):
        self.assertTrue(is_confirmed(CONFIRMED))
        s = parse_confirmation_summary(CONFIRMED)
        self.assertIn("26/10/2026", s.date_text)


if __name__ == "__main__":
    unittest.main()
