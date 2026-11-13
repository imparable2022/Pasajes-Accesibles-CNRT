"""Produce Windows/NVDA Chromium fixtures from unmodified and patched Poncho sources."""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "upstream"
TARGET = ROOT / "poncho-nvda" / "fixtures"
phase = sys.argv[1]
assert phase in ("before", "after")
dest = TARGET / phase
dest.mkdir(parents=True, exist_ok=True)

def asset(relative, name):
    target = dest / name
    shutil.copyfile(SOURCE / relative, target)
    return target.as_uri()

def html(name, body):
    (dest / (name + ".html")).write_text(body, encoding="utf-8")

map_url = asset("src/js/poncho-map/src/js/poncho-map.js", "poncho-map.js")
search_url = asset("src/js/poncho-map/src/js/poncho-map-search.js", "poncho-map-search.js")
crumb_url = asset("src/js/device-breadcrumb/src/js/device-breadcrumb.js", "breadcrumb.js")
panel_url = asset("src/js/device-panel-menu/device-panel-menu.js", "panel.js")

# Sass from Poncho; force mobile media query in test fixture because Chrome's
# remote desktop size on a GitHub Actions runner is not guaranteed to be 600px.
scss_path = SOURCE / "src/js/device-breadcrumb/src/scss/device-breadcrumb.scss"
css_path = dest / "breadcrumb.css"
sass_exe = ROOT / "node_modules" / ".bin" / "sass.cmd"
subprocess.run([str(sass_exe), str(scss_path), str(css_path)], check=True)
css = css_path.read_text("utf-8").replace("@media (max-width: 991px)", "@media (min-width: 0px)")
css_path.write_text(css, encoding="utf-8")
css_url = css_path.as_uri()

html("svg", f"""
<script src="{map_url}"></script>
<h2>Mapa de provincias</h2>
<svg width="160" height="100" aria-label="Mapa" role="group">
  <path d="M10 10 H130 V80 H10 Z" fill="#1967a3" id="santa-fe-shape" />
</svg>
<script>
  const path = document.getElementById("santa-fe-shape");
  const properties = {{name: "Santa Fe", id: 123, "pm-interactive": "s"}};
  PonchoMap.prototype._setFetureAttributes.call({{
    map: {{eachLayer: cb => cb({{
       _path: path, _leaflet_id: 456, feature: {{properties}}
    }})}}, title: "name", id: "id"
  }});
</script>
""")

# Real demo markup, not a made-up list.
sample = (SOURCE / "src/js/device-breadcrumb/demo/caso-3.html").read_text("utf-8")
match = re.search(r'<ol class="breadcrumb".*?</ol>', sample, flags=re.S)
if not match:
    raise RuntimeError("Expected case 3 breadcrumb not found")
crumb_markup = match.group(0)
html("breadcrumb", f"""
<link rel="stylesheet" href="{css_url}" />
<h2>Rutas de navegación</h2>
{crumb_markup}
<script src="{crumb_url}"></script>
<script>
  new DeviceBreadcrumb({{domain: ["unmatched.example"]}}).render(600);
</script>
""")

html("panel", f"""
<h2>Menú de navegación</h2>
<details class="device-panel-menu"><summary>Opciones de navegación</summary>
  <p><a href="#contenido">Contenido del menú</a></p></details>
<button id="resize" type="button" onclick="window.dispatchEvent(new Event('resize'))">
  Simular redimensión
</button>
<script src="{panel_url}"></script>
""")

html("combobox", f"""
<h2>Búsqueda de lugares</h2>
<div data-scope="a"><label for="input-a">Buscar A</label>
<input id="input-a" class="js-poncho-map-search__input"></div>
<div data-scope="b"><label for="input-b">Buscar B</label>
<input id="input-b" class="js-poncho-map-search__input"></div>
<script src="{search_url}"></script>
<script>
  window.slugify = s => String(s).toLowerCase();
  for(const scope of ["a", "b"]) {{
     const instance = {{
         headers: {{}}, title: "name", id: "id", search_fields: [],
         scope_sufix: "--" + scope
     }};
     const search = new PonchoMapSearch(instance, {{
          scope, combobox:true, datalist:false,
          combobox_options: {{}}, debounce_delay: 10
     }});
     search.cachedDataEntries = [{{id: scope, name: "Santa Fe", results:"santa"}}];
     search.searcher();
     const el = document.getElementById("input-" + scope);
     el.value = "san";
     el.dispatchEvent(new KeyboardEvent("keyup", {{key:"n", bubbles:true}}));
  }}
</script>
""")

print("Created real-source NVDA fixtures:", phase)
