from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ExecutableReleaseContractTests(unittest.TestCase):
    def test_release_workflow_builds_installer_portable_and_checksums(self):
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn('runs-on: windows-2025', workflow)
        self.assertIn('persist-credentials: false', workflow)
        self.assertIn('pyinstaller --noconfirm PasajesAccesiblesCNRT.spec', workflow)
        self.assertIn('python tools/generate_build_info.py --repository "${{ github.repository }}"', workflow)
        self.assertIn('Verify injected update repository', workflow)
        self.assertIn('python -m playwright install chromium', workflow)
        self.assertIn('Inno Setup 6', workflow)
        self.assertIn('Build portable updater helper', workflow)
        self.assertIn('PasajesPortableUpdater.exe', workflow)
        self.assertIn('Pasajes_Accesibles_CNRT_Setup.exe', workflow)
        self.assertIn('Pasajes_Accesibles_CNRT_Portable.zip', workflow)
        self.assertIn('channel=portable', workflow)
        self.assertIn('write_portable_manifest.py', workflow)
        self.assertIn('Get-FileHash', workflow)
        self.assertIn('python -m unittest discover -s tests -q', workflow)
        self.assertIn('python -m compileall -q pasajes_accesibles_cnrt launcher.py portable_updater.py tools', workflow)
        self.assertIn('gh release create', workflow)

    def test_installer_is_per_user_and_preserves_appdata(self):
        script = (ROOT / "installer" / "PasajesAccesiblesCNRT.iss").read_text(encoding="utf-8")
        self.assertIn('DefaultDirName={localappdata}\\Programs\\Pasajes Accesibles CNRT', script)
        self.assertIn('PrivilegesRequired=lowest', script)
        self.assertIn('CloseApplications=yes', script)
        self.assertNotIn('{appdata}', script)

    def test_bundled_browser_is_discovered_next_to_executable(self):
        client = (ROOT / "pasajes_accesibles_cnrt" / "client.py").read_text(encoding="utf-8")
        self.assertIn('getattr(sys, "frozen", False)', client)
        self.assertIn('Path(sys.executable).resolve().parent / "ms-playwright"', client)
        self.assertIn('PLAYWRIGHT_BROWSERS_PATH', client)

    def test_portable_helper_is_separate_from_main_executable(self):
        helper = (ROOT / "portable_updater.py").read_text(encoding="utf-8")
        self.assertIn('os.replace(target, backup)', helper)
        self.assertIn('os.replace(source, target)', helper)
        self.assertIn('os.replace(backup, target)', helper)
        self.assertIn('PORTABLE_MARKER', helper)

    def test_update_menu_and_automatic_check_are_exposed(self):
        app = (ROOT / "pasajes_accesibles_cnrt" / "app.py").read_text(encoding="utf-8")
        self.assertIn('"&Buscar actualizaciones..."', app)
        self.assertIn('self.Bind(wx.EVT_MENU, self._manual_check_updates, check_updates)', app)
        self.assertIn('wx.CallLater(2500, self._auto_check_updates)', app)
        self.assertIn('self._initialize_telemetry_consent()\n        wx.CallLater(2500, self._auto_check_updates)', app)
        self.assertIn('24 * 60 * 60', app)
        self.assertIn('SHA-256', app)
        self.assertIn('prepare_portable_update', app)
        self.assertIn('launch_portable_update', app)

    def test_automatic_update_check_prompts_when_a_new_version_exists(self):
        app = (ROOT / "pasajes_accesibles_cnrt" / "app.py").read_text(encoding="utf-8")
        self.assertIn('Tanto la comprobación automática como la manual deben avisar', app)
        self.assertIn('"Actualización disponible"', app)
        self.assertIn('wx.YES_NO | wx.NO_DEFAULT | wx.ICON_INFORMATION', app)
        self.assertNotIn('La comprobación automática nunca abre ventanas ni roba el foco.', app)
        self.assertNotIn('Para verla, abra Ayuda y elija Buscar actualizaciones.', app)


if __name__ == "__main__":
    unittest.main()
