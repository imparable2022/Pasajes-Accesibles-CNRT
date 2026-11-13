"""Produce Windows/NVDA Chromium fixtures from unmodified and patched Poncho sources."""
import re
import json
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

# PonchoMap._setFetureAttributes is a class instance FIELD (arrow function),
# not on the prototype. Extract and execute its EXACT current upstream body.
# The previous prototype call threw before any SVG naming could take place.
map_source = (SOURCE / "src/js/poncho-map/src/js/poncho-map.js").read_text("utf-8")
method_name = "    _setFetureAttributes = () => {"
method_start = map_source.index(method_name)
method_end = map_source.index("\n    };", method_start) + len("\n    };")
method = map_source[method_start:method_end]
arrow_source = method[method.index("=") + 1:].strip().rstrip(";")
method_json = json.dumps(arrow_source)

html("svg", f"""
<h2>Mapa de provincias</h2>
<svg width="160" height="100" aria-label="Mapa" role="group">
  <path d="M10 10 H130 V80 H10 Z" fill="#1967a3" id="santa-fe-shape" tabindex="0" role="button" />
</svg>
<script>
  const path = document.getElementById("santa-fe-shape");
  const properties = {{name: "Santa Fe", id: 123, "pm-interactive": "s"}};
  const fixtureContext = {{
    map: {{eachLayer: cb => cb({{
       _path: path, _leaflet_id: 456, feature: {{properties}}
    }})}}, title: "name", id: "id"
  }};
  const method = new Function("return (" + {method_json} + ");").call(fixtureContext);
  method();
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
<button id="resize" type="button" onclick="window.dispatchEvent(new Event('resize')); this.textContent = 'Estado del menú: ' + (document.querySelector('details').open ? 'abierto' : 'cerrado');">
  Simular redimensión
</button>
<script src="{panel_url}"></script>
""")

html("combobox", f"""
<h2>Búsqueda de lugares</h2>
<div data-scope="a"><label for="input-a">Buscar A</label>
<div class="input-group"><input id="input-a" class="js-poncho-map-search__input"></div></div>
<div data-scope="b"><label for="input-b">Buscar B</label>
<div class="input-group"><input id="input-b" class="js-poncho-map-search__input"></div></div>
<p id="selected" role="status">Sin selección</p>
<script src="{search_url}"></script>
<script>
  window.slugify = s => String(s).toLowerCase();
  window.selected = [];
  for(const scope of ["a", "b"]) {{
     const instance = {{
         headers: {{}}, title: "name", id: "id", search_fields: [],
         scope_sufix: "--" + scope,
         _setSearchInputValue: value => {{ window.selected.push(["value",scope,value]); }},
         gotoEntry: (id, a, b) => {{ window.selected.push(["goto",scope,id]); document.getElementById("selected").textContent="Seleccionado "+id; }}
     }};
     const search = new PonchoMapSearch(instance, {{
          scope, combobox:true, datalist:false,
          combobox_options: {{}}, debounce_delay: 10
     }});
     search.cachedDataEntries = [
       {{id:scope+"-1",name:"Santa Fe",results:"san"}},
       {{id:scope+"-2",name:"San Justo",results:"san"}},
       {{id:scope+"-3",name:"San Javier",results:"san"}}
     ];
     search.searcher();
     const el = document.getElementById("input-" + scope);
     el.value = "san";
     el.dispatchEvent(new KeyboardEvent("keyup", {{key:"n", bubbles:true}}));
  }}
</script>
""")


dialog_methods = {name:map_source[
    map_source.index("    "+name+" = "):
    map_source.index("\n    };", map_source.index("    "+name+" = ")) + len("\n    };")
] for name in ["_renderSlider", "toggleSlider", "isSliderOpen"]}
method_map=json.dumps(dialog_methods)
html("dialog", f"""
<h2>Panel de información</h2>
<button id="trigger" type="button">Mostrar información</button>
<div class="poncho-map" data-scope="ponchomap"></div>
<button id="outside" type="button">Acción exterior</button>
<button id="state" type="button" onclick="this.textContent='Panel: '+document.querySelector('dialog').getAttribute('aria-modal')">Leer estado</button>
<script>
 const context = {{
   render_slider:true,content_outside:false,no_info:false,
   scope_selector:'[data-scope="ponchomap"]',scope_sufix:"--ponchomap",
   slider_selector:"pm-slider", _t:s=>s,
   addAnchorElement:opts=>document.createElement('a')
 }};
 for(const [name,code] of Object.entries({method_map})){{
   const arrow=code.slice(code.indexOf("=")+1).trim().replace(/;$/, "");
   context[name]=new Function("return ("+arrow+");").call(context);
 }}
 context._renderSlider();
 document.getElementById("trigger").addEventListener("click",()=>context.toggleSlider());
</script>
""")

print("Created real-source NVDA fixtures:", phase)
