import unittest

from pasajes_accesibles_cnrt.parsers import parse_request_records


REQUESTS_HTML = """
<html><body><table id="reservar">
<thead><tr>
<th>Origen</th><th>Destino</th><th>Empresa</th><th>Fecha salida</th><th>Horario salida</th>
<th>Email</th><th>Modificar email</th><th>Cantidad reservada</th><th>Modificar preferencia viaje</th>
<th>Modificar acompañante</th><th>Estado</th><th>Anular</th>
</tr></thead><tbody>
<tr>
<td>ORIGEN A</td><td>DESTINO B</td><td>EMPRESA PRUEBA</td><td>26-10-2026</td><td>18:30</td>
<td>persona@example.com</td>
<td><a href="/web/modificarEmail/12345?token=sesion">Modificar Email</a></td>
<td>1</td>
<td><a href="/web/editarPreferenciaViaje/12345?token=sesion">Modificar preferencia Viaje</a></td>
<td></td><td>Activa</td>
<td><a href="/web/consultar/?anular=1&beneficiarioCnrtId=1&br=12345&estado=Activa&token=sesion">Anular Solicitud</a></td>
</tr>
<!-- Simula un HTML copiado por un visor que perdió el <tr> de la fila siguiente. -->
<td>ORIGEN C</td><td>DESTINO D</td><td>EMPRESA HISTORICA</td><td>11-01-2025</td><td>12:10</td>
<td>persona@example.com</td><td></td><td>2</td><td></td><td></td><td>Pasaje Emitido</td><td></td>
</tbody></table></body></html>
"""


class RequestParserTests(unittest.TestCase):
    def test_active_request_keeps_exact_actions(self):
        rows = parse_request_records(REQUESTS_HTML, "https://reservapasajes.cnrt.gob.ar")
        self.assertEqual(len(rows), 2)
        active = rows[0]
        self.assertEqual(active.reservation_id, "12345")
        self.assertEqual(active.status, "Activa")
        self.assertTrue(active.can_modify_email)
        self.assertTrue(active.can_modify_preference)
        self.assertTrue(active.cancellable)
        self.assertIn("/web/modificarEmail/12345", active.modify_email_url)
        self.assertIn("/web/editarPreferenciaViaje/12345", active.modify_preference_url)
        self.assertIn("br=12345", active.cancel_url)

    def test_historical_request_has_no_actions(self):
        rows = parse_request_records(REQUESTS_HTML, "https://reservapasajes.cnrt.gob.ar")
        old = rows[1]
        self.assertEqual(old.status, "Pasaje Emitido")
        self.assertFalse(old.can_modify_email)
        self.assertFalse(old.can_modify_preference)
        self.assertFalse(old.cancellable)
        self.assertIn("ORIGEN C", old.text)


if __name__ == "__main__":
    unittest.main()
