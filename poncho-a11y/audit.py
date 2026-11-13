#!/usr/bin/env python3
"""Auditoría reproducible de componentes reales de argob/poncho en Chromium.
No automatiza ni sustituye pruebas manuales con NVDA.
"""
import json
import subprocess
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream"
PHASE = sys.argv[1] if len(sys.argv) > 1 else "before"
assert PHASE in ("before", "after")

def check(name, observed, expected):
    assert observed == expected, (
        f"{name}: observado {observed!r}; esperado {expected!r}")
    print(f"OK {name}: {json.dumps(observed, ensure_ascii=False)}", flush=True)

def field_source(path, name):
    data = (UPSTREAM / path).read_text(encoding="utf-8")
    needle = "    " + name + " = () => {"
    start = data.index(needle)
    stop = data.index("\n    };", start) + len("\n    };")
    return data[start:stop]

results = {}
with sync_playwright() as engine:
    browser = engine.chromium.launch(headless=True)

    # 1. Ejecuta el método real de PonchoMap sobre un elemento SVG en Chromium.
    page = browser.new_page()
    snippet = field_source("src/js/poncho-map/src/js/poncho-map.js",
                           "_setFetureAttributes")
    svg = page.evaluate(r"""(snippet) => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      document.body.appendChild(path);
      const props = {name: "Santa Fe", id: 123, "pm-interactive": "s"};
      const context = {
        title: "name", id: "id",
        map: {eachLayer: cb => cb({
          _path: path, _leaflet_id: 456, feature: {properties: props}
        })}
      };
      const arrow = snippet.substring(snippet.indexOf("=") + 1)
        .trim().replace(/;\s*$/, "");
      const fn = new Function("return (" + arrow + ");").call(context);
      fn();
      return {name: path.getAttribute("aria-label"),
              entry: path.getAttribute("data-entry-id")};
    }""", snippet)
    results["svg"] = svg
    check("Atributos SVG", svg,
          {"name": None, "entry": None} if PHASE == "before"
          else {"name": "Santa Fe", "entry": "123"})
    page.close()

    # 2. Construye dos buscadores reales del repositorio y genera resultados.
    page = browser.new_page()
    page.set_content("""
      <div data-scope="a"><label for="a">Buscar A</label>
        <input id="a" class="js-poncho-map-search__input"></div>
      <div data-scope="b"><label for="b">Buscar B</label>
        <input id="b" class="js-poncho-map-search__input"></div>
    """)
    page.add_script_tag(path=str(UPSTREAM /
        "src/js/poncho-map/src/js/poncho-map-search.js"))
    page.evaluate(r"""() => {
      window.slugify = s => s.toLowerCase();
      for (const scope of ["a", "b"]) {
        const instance = {
          headers: {}, title: "name", id: "id",
          search_fields: [], scope_sufix: "--" + scope
        };
        const search = new PonchoMapSearch(instance, {
          scope, combobox: true, datalist: false,
          combobox_options: {}, debounce_delay: 10
        });
        search.cachedDataEntries = [
          {id: scope, name: "Santa Fe", results: "santa"}
        ];
        search.searcher();
        const input = document.querySelector('[data-scope="' + scope + '"] input');
        input.value = "san";
        input.dispatchEvent(new KeyboardEvent("keyup", {key: "n", bubbles: true}));
      }
    }""")
    page.wait_for_timeout(100)
    combobox = page.evaluate("""() => ({
      controls: [...document.querySelectorAll('input[role="combobox"]')]
        .map(e => e.getAttribute("aria-controls")),
      lists: [...document.querySelectorAll('[role="listbox"]')]
        .map(e => e.id),
      targets: [...document.querySelectorAll('input[role="combobox"]')]
        .map(e => document.getElementById(e.getAttribute("aria-controls"))
          ?.getAttribute("role") || null)
    })""")
    results["combobox"] = combobox
    check("Relación combobox-listbox en dos instancias", combobox,
          {"controls": ["js-poncho-results-list", "js-poncho-results-list"],
           "lists": ["", ""], "targets": [None, None]}
          if PHASE == "before" else
          {"controls": ["js-poncho-results-list--a", "js-poncho-results-list--b"],
           "lists": ["js-poncho-results-list--a", "js-poncho-results-list--b"],
           "targets": ["listbox", "listbox"]})
    page.close()

    # 3. Comprueba si un enlace supuestamente oculto sigue siendo enfocables.
    page = browser.new_page(viewport={"width": 600, "height": 800})
    page.set_content("""<ol class="breadcrumb">
      <li><a href="/">Inicio</a></li>
      <li><a href="/tramites">Trámites</a></li>
      <li><a href="/transportes">Transporte</a></li>
      <li>Reservas</li>
    </ol>""")
    css = subprocess.check_output([
        str(ROOT / "node_modules/.bin/sass"),
        str(UPSTREAM / "src/js/device-breadcrumb/src/scss/device-breadcrumb.scss")
    ], text=True)
    page.add_style_tag(content=css)
    page.add_script_tag(path=str(UPSTREAM /
        "src/js/device-breadcrumb/src/js/device-breadcrumb.js"))
    breadcrumb = page.evaluate("""() => {
      const component = new DeviceBreadcrumb({domain: ["^/$"]});
      component.render(600);
      const hidden = document.querySelector(".device-breadcrumb__toggle-item a");
      if (!hidden) return {error: "No se generaron enlaces contraídos"};
      hidden.focus();
      const hiddenCanFocus = document.activeElement === hidden;
      const expand = document.querySelector(".js-ellip button");
      expand.click();
      const close = document.querySelector(".js-close button");
      const focusAfterExpand = document.activeElement === close;
      close.click();
      const focusAfterClose = document.activeElement === expand;
      return {hiddenCanFocus, focusAfterExpand, focusAfterClose};
    }""")
    results["breadcrumb"] = breadcrumb
    if PHASE == "before":
        assert breadcrumb.get("hiddenCanFocus") is True, breadcrumb
        print("OK breadcrumb original: enlace oculto aún acepta foco", breadcrumb, flush=True)
    else:
        check("Breadcrumb sin foco invisible y con foco restaurado",
              breadcrumb, {"hiddenCanFocus": False,
                           "focusAfterExpand": True, "focusAfterClose": True})
    page.close()

    # 4. Comprueba que redimensionar sin cambiar breakpoint no borre la decisión.
    page = browser.new_page(viewport={"width": 600, "height": 800})
    page.set_content("""<details class="device-panel-menu">
      <summary>Menú</summary><a href="/ejemplo">Opción</a>
    </details>""")
    page.add_script_tag(path=str(UPSTREAM /
        "src/js/device-panel-menu/device-panel-menu.js"))
    panel = page.evaluate("""() => {
      window.dispatchEvent(new Event("resize"));
      const details = document.querySelector("details");
      details.open = true;   // apertura solicitada por el usuario
      window.dispatchEvent(new Event("resize")); // seguimos en modo móvil
      return details.open;
    }""")
    results["panel"] = panel
    check("Menú conserva apertura en mismo breakpoint", panel,
          False if PHASE == "before" else True)
    page.close()
    browser.close()

path = ROOT / ("poncho-a11y-audit-" + PHASE + ".json")
path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print("Auditoría", PHASE, "completada. Resultados:", path, flush=True)
