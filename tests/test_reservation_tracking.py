import json
import tempfile
import unittest
from pathlib import Path

from pasajes_accesibles_cnrt.models import RequestRecord
from pasajes_accesibles_cnrt.reservation_tracking import (
    ReservationLifecycleTracker,
    STATE_ACTIVE,
    STATE_CANCELLED,
    STATE_OTHER,
    STATE_TICKET_ISSUED,
    event_name_for_state,
    normalize_cnrt_status,
)


class ReservationTrackingTests(unittest.TestCase):
    def make_record(self, *, status="Activa", reservation_id="12345", cancel_url="https://x/anular"):
        return RequestRecord(
            reservation_id=reservation_id,
            origin="RECONQUISTA",
            destination="BUENOS AIRES",
            company="EMPRESA PRUEBA",
            date_text="26-10-2026",
            departure="18:30",
            quantity="1",
            status=status,
            cancel_url=cancel_url,
        )

    def test_normalizes_only_confirmed_state_categories(self):
        self.assertEqual(STATE_ACTIVE, normalize_cnrt_status("Activa"))
        self.assertEqual(STATE_TICKET_ISSUED, normalize_cnrt_status("Pasaje Emitido"))
        self.assertEqual(STATE_CANCELLED, normalize_cnrt_status("Anulada"))
        self.assertEqual(STATE_CANCELLED, normalize_cnrt_status("Cancelada"))
        self.assertEqual(STATE_ACTIVE, normalize_cnrt_status("", cancellable=True))
        self.assertEqual(STATE_OTHER, normalize_cnrt_status("Estado futuro no conocido"))
        self.assertEqual("reservation_ticket_issued", event_name_for_state(STATE_TICKET_ISSUED))

    def test_created_active_ticket_issued_keep_same_anonymous_reservation_id(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tracker.json"
            tracker = ReservationLifecycleTracker(path)
            tracking_id = tracker.register_created(
                company="EMPRESA PRUEBA",
                origin="RECONQUISTA",
                destination="BUENOS AIRES",
                travel_date="2026-10-26",
                departure="18:30",
                quantity="1",
            )
            active = tracker.observe(self.make_record())
            self.assertIsNotNone(active)
            self.assertEqual(tracking_id, active.tracking_id)
            self.assertEqual(STATE_ACTIVE, active.state)
            self.assertIsNone(tracker.observe(self.make_record()))

            emitted = tracker.observe(self.make_record(status="Pasaje Emitido", cancel_url=""))
            self.assertIsNotNone(emitted)
            self.assertEqual(tracking_id, emitted.tracking_id)
            self.assertEqual(STATE_TICKET_ISSUED, emitted.state)
            self.assertIsNone(tracker.observe(self.make_record(status="Pasaje Emitido", cancel_url="")))

    def test_cancel_reuses_existing_lifecycle_and_is_not_double_counted(self):
        with tempfile.TemporaryDirectory() as td:
            tracker = ReservationLifecycleTracker(Path(td) / "tracker.json")
            tracking_id = tracker.register_created(
                company="EMPRESA PRUEBA",
                origin="RECONQUISTA",
                destination="BUENOS AIRES",
                travel_date="26-10-2026",
                departure="18:30",
                quantity="1",
            )
            tracker.observe(self.make_record())
            cancelled = tracker.mark_cancelled(self.make_record())
            self.assertIsNotNone(cancelled)
            self.assertEqual(tracking_id, cancelled.tracking_id)
            self.assertEqual(STATE_CANCELLED, cancelled.state)
            self.assertIsNone(tracker.mark_cancelled(self.make_record()))

    def test_local_tracking_file_contains_no_clear_reservation_or_trip_details(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tracker.json"
            tracker = ReservationLifecycleTracker(path)
            tracker.register_created(
                company="EMPRESA MUY SECRETA",
                origin="ORIGEN MUY SECRETO",
                destination="DESTINO MUY SECRETO",
                travel_date="2026-10-26",
                departure="18:30",
                quantity="1",
            )
            tracker.observe(self.make_record(reservation_id="CODIGO-RESERVA-SECRETO"))
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("CODIGO-RESERVA-SECRETO", text)
            self.assertNotIn("EMPRESA MUY SECRETA", text)
            self.assertNotIn("ORIGEN MUY SECRETO", text)
            self.assertNotIn("DESTINO MUY SECRETO", text)
            data = json.loads(text)
            self.assertIn("reservations", data)
            self.assertTrue(data["reservations"][0]["tracking_id"].startswith("reservation-"))

    def test_corrupt_state_file_fails_open_for_app_and_recovers(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tracker.json"
            path.write_text("{broken", encoding="utf-8")
            tracker = ReservationLifecycleTracker(path)
            observation = tracker.observe(self.make_record(status="Pasaje Emitido", cancel_url=""))
            self.assertIsNotNone(observation)
            self.assertEqual(STATE_TICKET_ISSUED, observation.state)
            json.loads(path.read_text(encoding="utf-8"))

    def test_identical_reservations_get_separate_lifecycle_ids(self):
        with tempfile.TemporaryDirectory() as td:
            tracker = ReservationLifecycleTracker(Path(td) / "tracker.json")
            kwargs = dict(
                company="EMPRESA PRUEBA",
                origin="RECONQUISTA",
                destination="BUENOS AIRES",
                travel_date="2026-10-26",
                departure="18:30",
                quantity="1",
            )
            first = tracker.register_created(**kwargs)
            second = tracker.register_created(**kwargs)
            self.assertNotEqual(first, second)

    def test_identical_historical_rows_without_cnrt_id_remain_separate(self):
        with tempfile.TemporaryDirectory() as td:
            tracker = ReservationLifecycleTracker(Path(td) / "tracker.json")
            kwargs = dict(
                company="EMPRESA PRUEBA",
                origin="RECONQUISTA",
                destination="BUENOS AIRES",
                travel_date="2026-10-26",
                departure="18:30",
                quantity="1",
            )
            first = tracker.register_created(**kwargs)
            second = tracker.register_created(**kwargs)
            record = self.make_record(status="Pasaje Emitido", reservation_id="", cancel_url="")
            obs0 = tracker.observe(record, occurrence=0)
            obs1 = tracker.observe(record, occurrence=1)
            self.assertEqual(first, obs0.tracking_id)
            self.assertEqual(second, obs1.tracking_id)
            self.assertNotEqual(obs0.tracking_id, obs1.tracking_id)

    def test_a_state_is_counted_only_once_even_after_a_regression(self):
        with tempfile.TemporaryDirectory() as td:
            tracker = ReservationLifecycleTracker(Path(td) / "tracker.json")
            tracker.register_created(
                company="EMPRESA PRUEBA",
                origin="RECONQUISTA",
                destination="BUENOS AIRES",
                travel_date="2026-10-26",
                departure="18:30",
                quantity="1",
            )
            self.assertIsNotNone(tracker.observe(self.make_record(status="Activa")))
            self.assertIsNotNone(tracker.observe(self.make_record(status="Pasaje Emitido", cancel_url="")))
            self.assertIsNone(tracker.observe(self.make_record(status="Activa")))


if __name__ == "__main__":
    unittest.main()
