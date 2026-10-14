from pathlib import Path

APP = Path("pasajes_accesibles_cnrt/app.py")
TESTS = Path("tests/test_ui_contract.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: se esperaba 1 coincidencia y se encontraron {count}")
    return text.replace(old, new, 1)


app = APP.read_text(encoding="utf-8")

app = replace_once(
    app,
    '''        self._search_fields_cleared = False\n        self._discard_scan_result = False\n''',
    '''        self._search_fields_cleared = False\n        self._discard_scan_result = False\n        self._last_search_form: dict | None = None\n''',
    "estado inicial",
)

app = replace_once(
    app,
    '''    def _show_search(self, event=None):\n        self._clear_content()\n''',
    '''    def _show_search(self, event=None, restore_previous=False):\n        saved_search = self._last_search_form if restore_previous else None\n        self._clear_content()\n''',
    "entrada a buscar pasajes",
)

app = replace_once(
    app,
    '''        self._populate_date_choices()\n        self._set_date_value("travel", self.allowed_min_date)\n        self._set_date_value("from", self.allowed_min_date)\n        self._set_date_value("to", self._clamp_allowed_date(self.allowed_min_date + timedelta(days=1)))\n        self._on_search_mode_change(None, move_focus=False)\n''',
    '''        self._populate_date_choices()\n        if saved_search is not None:\n            self._restore_search_form(saved_search)\n        else:\n            self._set_date_value("travel", self.allowed_min_date)\n            self._set_date_value("from", self.allowed_min_date)\n            self._set_date_value("to", self._clamp_allowed_date(self.allowed_min_date + timedelta(days=1)))\n        self._on_search_mode_change(None, move_focus=False)\n''',
    "valores iniciales de búsqueda",
)

helpers = '''    def _remember_search_form(self):\n        mode = (\n            "specific" if self.mode_specific.GetValue() else\n            "range" if self.mode_range.GetValue() else\n            "all"\n        )\n        self._last_search_form = {\n            "origin": self.selected_origin,\n            "destination": self.selected_destination,\n            "quantity_index": self.quantity.GetSelection(),\n            "delay": float(self.delay.GetValue()),\n            "mode": mode,\n            "travel_date": self.travel_date.GetValue(),\n            "from_date": self.from_date.GetValue(),\n            "to_date": self.to_date.GetValue(),\n        }\n\n    def _restore_search_form(self, state: dict):\n        origin = state.get("origin")\n        destination = state.get("destination")\n        self.selected_origin = origin\n        self.selected_destination = destination\n        self.origin_results = [origin] if origin is not None else []\n        self.destination_results = [destination] if destination is not None else []\n\n        for combo, selected in (\n            (self.origin_combo, origin),\n            (self.destination_combo, destination),\n        ):\n            combo.Clear()\n            if selected is not None:\n                combo.Append(selected.text)\n                combo.ChangeValue(selected.text)\n            else:\n                combo.ChangeValue("")\n\n        quantity_index = int(state.get("quantity_index", 0))\n        if 0 <= quantity_index < self.quantity.GetCount():\n            self.quantity.SetSelection(quantity_index)\n        self.delay.SetValue(float(state.get("delay", 0.9)))\n\n        mode = state.get("mode", "specific")\n        self.mode_specific.SetValue(mode == "specific")\n        self.mode_range.SetValue(mode == "range")\n        self.mode_all.SetValue(mode == "all")\n\n        for prefix, key in (\n            ("travel", "travel_date"),\n            ("from", "from_date"),\n            ("to", "to_date"),\n        ):\n            raw_value = str(state.get(key, "")).strip()\n            try:\n                parsed = datetime.strptime(raw_value, "%d-%m-%Y").date()\n            except ValueError:\n                getattr(self, f"{prefix}_date").ChangeValue(raw_value)\n                continue\n            self._set_date_value(prefix, parsed)\n\n    def _return_to_search(self, event=None):\n        self._show_search(restore_previous=True)\n\n'''

app = replace_once(
    app,
    '''    def _clear_date_editor(self, prefix: str):\n''',
    helpers + '''    def _clear_date_editor(self, prefix: str):\n''',
    "ayudantes de restauración",
)

app = replace_once(
    app,
    '''        self._accept_locality_after_search = {"origin": False, "destination": False}\n        self._search_fields_cleared = True\n\n        for combo_name in ("origin_combo", "destination_combo"):\n''',
    '''        self._accept_locality_after_search = {"origin": False, "destination": False}\n        self._search_fields_cleared = True\n        self._last_search_form = None\n\n        for combo_name in ("origin_combo", "destination_combo"):\n''',
    "limpiar búsqueda guardada",
)

app = replace_once(
    app,
    '''    def _start_scan(self, start_date: date | None, end_date: date | None):\n        self._discard_scan_result = False\n''',
    '''    def _start_scan(self, start_date: date | None, end_date: date | None):\n        self._remember_search_form()\n        self._discard_scan_result = False\n''',
    "recordar antes de buscar",
)

app = replace_once(
    app,
    '''        again.Bind(wx.EVT_BUTTON, self._show_search)\n''',
    '''        again.Bind(wx.EVT_BUTTON, self._return_to_search)\n''',
    "volver desde resultados",
)

APP.write_text(app, encoding="utf-8", newline="\n")

tests = TESTS.read_text(encoding="utf-8")

tests = replace_once(
    tests,
    '''        self.assertIn('again.Bind(wx.EVT_BUTTON, self._show_search)', SOURCE)\n''',
    '''        self.assertIn('again.Bind(wx.EVT_BUTTON, self._return_to_search)', SOURCE)\n''',
    "prueba del botón volver",
)

new_test = '''    def test_back_from_results_restores_the_previous_search(self):\n        self.assertIn('self._last_search_form: dict | None = None', SOURCE)\n        self.assertIn('def _remember_search_form(self):', SOURCE)\n        self.assertIn('"origin": self.selected_origin', SOURCE)\n        self.assertIn('"destination": self.selected_destination', SOURCE)\n        self.assertIn('"travel_date": self.travel_date.GetValue()', SOURCE)\n        self.assertIn('"from_date": self.from_date.GetValue()', SOURCE)\n        self.assertIn('"to_date": self.to_date.GetValue()', SOURCE)\n        self.assertIn('self._remember_search_form()', SOURCE)\n        self.assertIn('def _return_to_search(self, event=None):', SOURCE)\n        self.assertIn('self._show_search(restore_previous=True)', SOURCE)\n        self.assertIn('saved_search = self._last_search_form if restore_previous else None', SOURCE)\n        self.assertIn('self._restore_search_form(saved_search)', SOURCE)\n        self.assertIn('self._last_search_form = None', SOURCE)\n\n'''

tests = replace_once(
    tests,
    '''    def test_secondary_views_keep_a_meaningful_back_path(self):\n''',
    new_test + '''    def test_secondary_views_keep_a_meaningful_back_path(self):\n''',
    "prueba de conservación",
)

TESTS.write_text(tests, encoding="utf-8", newline="\n")
