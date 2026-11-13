#!/usr/bin/env python3
"""Aplica un prototipo de correcciones sobre la copia de Poncho, nunca sobre main."""
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "upstream"
BT = chr(96)
SCOPE = chr(36) + "{this.scope_sufix}"

def change(path, pairs):
    path = BASE / path
    source = path.read_text("utf-8")
    for old, new in pairs:
        old = old.replace("@@BT@@", BT).replace("@@SCOPE@@", SCOPE)
        new = new.replace("@@BT@@", BT).replace("@@SCOPE@@", SCOPE)
        n = source.count(old)
        if n != 1:
            raise RuntimeError(f"Expected exactly one match in {path}, got {n}: {old[:100]}")
        source = source.replace(old, new)
    path.write_text(source, encoding="utf-8")
    print(f"Patched {path}")

change("src/js/poncho-map/src/js/poncho-map.js", [(
"""            Object.assign(_path, {
                'aria-label': properties?.[title],
                'tabIndex': (properties["pm-interactive"] === "n" ? -1 : 0),
                'data-entry-id': properties?.[id],
                'data-leaflet-id': _leaflet_id,
                'data-interactive': isInteractive ? null : "n",
                'role': isInteractive ? "button" : "graphics-symbol"
            });""",
"""            // Asignar propiedades JS con guiones no crea atributos SVG.
            _path.setAttribute("tabindex", isInteractive ? "0" : "-1");
            _path.setAttribute("role", isInteractive ? "button" : "graphics-symbol");
            if (properties?.[title] != null) {
                _path.setAttribute("aria-label", String(properties[title]));
            } else {
                _path.removeAttribute("aria-label");
            }
            if (properties?.[id] != null) {
                _path.setAttribute("data-entry-id", String(properties[id]));
            }
            if (_leaflet_id != null) {
                _path.setAttribute("data-leaflet-id", String(_leaflet_id));
            }
            if (isInteractive) {
                _path.removeAttribute("data-interactive");
            } else {
                _path.setAttribute("data-interactive", "n");
            }""")])

change("src/js/poncho-map/src/js/poncho-map-search.js", [
('searchElement.setAttribute("aria-controls", "js-poncho-results-list");',
 'searchElement.removeAttribute("aria-controls");'),
('searchContainer.id = "js-poncho-results-list";',
 'searchContainer.id = @@BT@@js-poncho-results-container@@SCOPE@@@@BT@@;'),
('ul.setAttribute("role", "listbox");',
 'ul.setAttribute("role", "listbox");\n                ul.id = @@BT@@js-poncho-results-list@@SCOPE@@@@BT@@;\n                searchElement.setAttribute("aria-controls", ul.id);'),
('searchContainer.replaceChildren();\n                searchElement.setAttribute("aria-expanded", "false");',
 'searchContainer.replaceChildren();\n                searchElement.setAttribute("aria-expanded", "false");\n                searchElement.removeAttribute("aria-controls");'),
('searchElement.setAttribute("aria-expanded", "false");\n        }\n    }',
 'searchElement.setAttribute("aria-expanded", "false");\n            searchElement.removeAttribute("aria-controls");\n        }\n    }'),
('searchElement.addEventListener("keydown", (e) => {\n            if(e.key == "ArrowDown"){',
 'searchElement.addEventListener("keydown", (e) => {\n            if (e.key === "Escape" && searchElement.getAttribute("aria-expanded") === "true") {\n                e.preventDefault();\n                this._closeSearchResults();\n                return;\n            }\n            if(e.key == "ArrowDown"){')
])

change("src/js/device-breadcrumb/src/scss/device-breadcrumb.scss", [
("""    &__toggle-item {
      position: absolute;
      left: -9999em;
      top: -9999em;
    }""",
"""    // No permitir foco en enlaces del breadcrumb contraído.
    &__toggle-item {
      display: none;
    }"""),
("""    &--expanded &__toggle-item {
      position: initial;
      left: 0;
      top: 0;
    }""",
"""    &--expanded &__toggle-item {
      display: list-item;
    }""")
])

change("src/js/device-breadcrumb/src/js/device-breadcrumb.js", [
("""            "click", () => this._removeDeviceHidden(breadcrumb) 
        ));""",
"""            "click", () => {
                this._removeDeviceHidden(breadcrumb);
                e.closest(this.selector)?.querySelector(".js-close button")?.focus();
            }
        ));"""),
("""            "click", () => this._removeExpanded(breadcrumb)
        ));""",
"""            "click", () => {
                this._removeExpanded(breadcrumb);
                e.closest(this.selector)?.querySelector(".js-ellip button")?.focus();
            }
        ));""")
])

change("src/js/device-panel-menu/device-panel-menu.js", [(
"""const panelMenu = () => {
    const details = document.querySelectorAll(".device-panel-menu");
    if (!details.length) {
        return;
    }
    if (window.innerWidth >= 991) {
        details.forEach((e) => e.setAttribute("open", true));
    } else {
        details.forEach((e) => e.removeAttribute("open"));
    }
};""",
"""let previousDesktopMode = null;
const panelMenu = () => {
    const details = document.querySelectorAll(".device-panel-menu");
    if (!details.length) {
        return;
    }
    const isDesktop = window.innerWidth >= 991;
    // Mantener la elección del usuario mientras no cambia el breakpoint.
    if (previousDesktopMode === isDesktop) {
        return;
    }
    previousDesktopMode = isDesktop;
    details.forEach((element) => {
        if (isDesktop) {
            element.open = true;
            return;
        }
        const summary = element.querySelector("summary");
        if (element.contains(document.activeElement) &&
            document.activeElement !== summary) {
            summary?.focus();
        }
        element.open = false;
    });
};""")
])
print("Parches listos para exportar con git diff.")
