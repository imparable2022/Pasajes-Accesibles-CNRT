import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "pasajes_accesibles_cnrt" / "app.py"
SOURCE = APP.read_text(encoding="utf-8")


class SearchUiContractTests(unittest.TestCase):
    def test_main_menu_uses_simple_search_name(self):
        self.assertIn('("&Buscar pasajes", self._show_search)', SOURCE)
        self.assertNotIn('Buscar pasajes en todas las fechas', SOURCE)

    def test_locality_fields_are_single_editable_comboboxes(self):
        self.assertIn('self.origin_combo = wx.ComboBox(', SOURCE)
        self.assertIn('self.destination_combo = wx.ComboBox(', SOURCE)
        self.assertIn('style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER', SOURCE)
        self.assertIn('self.origin_combo.Bind(wx.EVT_TEXT', SOURCE)
        self.assertIn('self.destination_combo.Bind(wx.EVT_TEXT', SOURCE)
        self.assertIn('self.origin_combo.Bind(wx.EVT_TEXT_ENTER', SOURCE)
        self.assertIn('self.destination_combo.Bind(wx.EVT_TEXT_ENTER', SOURCE)
        self.assertIn('self.origin_combo.Bind(wx.EVT_COMBOBOX', SOURCE)
        self.assertIn('self.destination_combo.Bind(wx.EVT_COMBOBOX', SOURCE)
        self.assertIn('wx.WXK_UP', SOURCE)
        self.assertIn('wx.WXK_DOWN', SOURCE)
        self.assertNotIn('name="Resultados de origen"', SOURCE)
        self.assertNotIn('name="Resultados de destino"', SOURCE)
        self.assertNotIn('self.origin_list = wx.ListBox', SOURCE)
        self.assertNotIn('self.destination_list = wx.ListBox', SOURCE)

    def test_date_can_be_edited_or_selected_by_day_month_year(self):
        self.assertIn('self._build_date_editor(self.specific_sizer, "Fecha", "travel"', SOURCE)
        self.assertIn('self._build_date_editor(self.range_sizer, "Desde", "from"', SOURCE)
        self.assertIn('self._build_date_editor(self.range_sizer, "Hasta", "to"', SOURCE)
        self.assertIn('wx.WXK_UP', SOURCE)
        self.assertIn('wx.WXK_DOWN', SOURCE)
        self.assertIn('name=f"{label}, día"', SOURCE)
        self.assertIn('name=f"{label}, mes"', SOURCE)
        self.assertIn('name=f"{label}, año"', SOURCE)

    def test_search_mode_static_box_owns_its_radio_buttons(self):
        self.assertIn('self.mode_specific = wx.RadioButton(\n            mode_box.GetStaticBox(),', SOURCE)
        self.assertIn('self.mode_range = wx.RadioButton(\n            mode_box.GetStaticBox(),', SOURCE)
        self.assertIn('self.mode_all = wx.RadioButton(\n            mode_box.GetStaticBox(),', SOURCE)

    def test_search_mode_uses_radio_buttons_with_requested_shortcuts(self):
        self.assertIn('label="Buscar fecha e&specífica"', SOURCE)
        self.assertIn('label="Buscar &rango de fechas"', SOURCE)
        self.assertIn('label="Escanear todas las fechas disponibl&es"', SOURCE)
        self.assertIn('name="Escanear todas las fechas disponibles"', SOURCE)
        self.assertIn('style=wx.RB_GROUP', SOURCE)
        self.assertIn('wx.EVT_RADIOBUTTON', SOURCE)
        self.assertNotIn('Limitar el escaneo a un rango de fechas', SOURCE)

    def test_only_controls_for_selected_mode_are_shown(self):
        self.assertIn('self.specific_panel.Show(specific)', SOURCE)
        self.assertIn('self.range_panel.Show(ranged)', SOURCE)
        self.assertIn('scan_all = self.mode_all.GetValue()', SOURCE)
        self.assertIn('self.range_panel.Hide()', SOURCE)

    def test_search_button_changes_singular_plural_and_keeps_alt_f(self):
        self.assertIn('self.search_dates_button.SetLabel("Buscar &fecha")', SOURCE)
        self.assertIn('self.search_dates_button.SetLabel("Buscar &fechas")', SOURCE)
        self.assertIn('self.search_dates_button.SetLabel("Escanear todas las &fechas disponibles")', SOURCE)
        self.assertIn('self._start_scan(None, None)', SOURCE)
        self.assertIn('self.search_dates_button.Bind(wx.EVT_BUTTON, self.on_search_dates)', SOURCE)

    def test_scan_all_is_an_independent_third_option(self):
        self.assertIn('self.mode_all = wx.RadioButton(', SOURCE)
        self.assertIn('label="Escanear todas las fechas disponibl&es"', SOURCE)
        self.assertIn('self.mode_all.Bind(wx.EVT_RADIOBUTTON, self._on_search_mode_change)', SOURCE)
        self.assertIn('self.mode_all.SetValue(True)', SOURCE)
        self.assertIn('self._start_scan(None, None)', SOURCE)
        self.assertIn('self.specific_panel.Show(specific)', SOURCE)
        self.assertIn('self.range_panel.Show(ranged)', SOURCE)

    def test_changing_search_mode_keeps_focus_on_selected_radio_button(self):
        self.assertIn('selected_mode = (', SOURCE)
        self.assertIn('self.mode_specific if specific else', SOURCE)
        self.assertIn('self.mode_range if ranged else', SOURCE)
        self.assertIn('self.mode_all', SOURCE)
        self.assertIn('wx.CallAfter(selected_mode.SetFocus)', SOURCE)
        self.assertNotIn('self.travel_date.SetFocus()\n            elif ranged:', SOURCE)

    def test_successful_cancellation_is_explicitly_announced(self):
        self.assertIn('"Reserva anulada con éxito"', SOURCE)
        self.assertIn('self._announce("Reserva anulada con éxito. La anulación fue verificada por CNRT.")', SOURCE)


    def test_visual_header_uses_meaningful_accessible_name_instead_of_generic_label(self):
        self.assertIn('def _heading(self, text: str, accessible_text: str | None = None):', SOURCE)
        self.assertIn('header = wx.Panel(self.content, name=spoken)', SOURCE)
        self.assertIn('header._pasajes_accesibles_cnrt_visual_header = True', SOURCE)
        self.assertIn('getattr(child, "_pasajes_accesibles_cnrt_visual_header", False)', SOURCE)
        self.assertNotIn('name="Encabezado visual"', SOURCE)
        self.assertIn('"Reserva, consulta y gestión accesible de pasajes",', SOURCE)


    def test_visible_product_name_is_pasajes_accesibles_cnrt(self):
        self.assertIn('title="Pasajes Accesibles CNRT"', SOURCE)
        self.assertIn('"Pasajes Accesibles CNRT",\n            "Reserva, consulta y gestión accesible de pasajes",', SOURCE)
        self.assertIn('"Acerca de Pasajes Accesibles CNRT"', SOURCE)

    def test_help_menu_exposes_about_and_contact_shortcuts(self):
        self.assertIn('menu_bar.Append(help_menu, "A&yuda")', SOURCE)
        self.assertIn('"&Acerca de\\tAlt+A"', SOURCE)
        self.assertIn('"Contáctate &conmigo\\tAlt+C"', SOURCE)
        self.assertIn('self.Bind(wx.EVT_MENU, self._show_about, about)', SOURCE)
        self.assertIn('self.Bind(wx.EVT_MENU, self._contact_me, contact)', SOURCE)
        self.assertIn('"&Privacidad y estadísticas"', SOURCE)
        self.assertIn('self.Bind(wx.EVT_MENU, self._manage_telemetry_consent, privacy)', SOURCE)

    def test_about_text_and_contact_address_are_preserved(self):
        self.assertIn('Pasajes Accesibles CNRT es una aplicación independiente (no oficial)', SOURCE)
        self.assertIn('Lo que sí podés hacer con el software:', SOURCE)
        self.assertIn('Lo que no podés hacer con el programa:', SOURCE)
        self.assertIn('Licencia: PolyForm Noncommercial 1.0.0.', SOURCE)
        self.assertIn('© Copyright 2026, Martín Ortiz, derechos reservados.', SOURCE)
        self.assertIn('mailto:martinortiz4362@gmail.com', SOURCE)
        self.assertIn('wx.LaunchDefaultBrowser(mailto)', SOURCE)

    def test_visual_theme_keeps_native_controls_and_adds_accessible_colour_roles(self):
        self.assertIn('COLOR_BG = wx.Colour(245, 247, 250)', SOURCE)
        self.assertIn('COLOR_MUTED = wx.Colour(71, 85, 105)', SOURCE)
        self.assertIn('COLOR_PRIMARY = wx.Colour(37, 99, 235)', SOURCE)
        self.assertIn('COLOR_DANGER = wx.Colour(153, 27, 27)', SOURCE)
        self.assertIn('def _style_button(self, button: wx.Button, role: str = "secondary"):', SOURCE)
        self.assertIn('self._style_button(self.request_cancel_button, "danger")', SOURCE)
        self.assertIn('self._set_status_visual(message)', SOURCE)
        self.assertIn('wx.Button(', SOURCE)
        self.assertIn('wx.ComboBox(', SOURCE)
        self.assertIn('wx.RadioButton(', SOURCE)

    def test_low_vision_mode_supports_system_contrast_and_text_up_to_200_percent(self):
        self.assertIn('def _windows_high_contrast_enabled() -> bool:', SOURCE)
        self.assertIn('SPI_GETHIGHCONTRAST = 0x0042', SOURCE)
        self.assertIn('self.Bind(wx.EVT_SYS_COLOUR_CHANGED, self.on_system_colour_changed)', SOURCE)
        self.assertIn('wx.SystemSettings.GetColour', SOURCE)
        self.assertIn('self.text_scale = min(2.0, max(1.0', SOURCE)
        self.assertIn('self._change_text_scale(0.25)', SOURCE)
        self.assertIn('self._change_text_scale(-0.25)', SOURCE)
        self.assertIn('self._set_text_scale(1.0)', SOURCE)
        self.assertIn('self.visual_config.Write("visual/text_scale"', SOURCE)
        self.assertIn('Tamaño de texto actual:', SOURCE)

    def test_low_vision_layout_reflows_and_status_does_not_rely_on_colour_alone(self):
        self.assertIn('self.content = wx.ScrolledWindow(', SOURCE)
        self.assertIn('wx.WrapSizer(wx.HORIZONTAL)', SOURCE)
        self.assertIn('max(44, round(44 * self.text_scale))', SOURCE)
        self.assertIn('self.status_label.SetLabel(f"Estado — {role}")', SOURCE)
        self.assertIn('role = "Éxito"', SOURCE)
        self.assertIn('role = "Error"', SOURCE)
        self.assertIn('role = "Aviso"', SOURCE)
        self.assertNotIn('wx.EVT_SET_FOCUS', SOURCE)



if __name__ == "__main__":
    unittest.main()
