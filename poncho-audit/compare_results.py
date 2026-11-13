#!/usr/bin/env python3
"""Compare complete axe/Chromium inventories before/after proposed patches."""
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent/"results"
before=json.loads((OUT/"all-demos-before.json").read_text("utf-8"))
after=json.loads((OUT/"all-demos-after.json").read_text("utf-8"))

def key(item):
    return item["path"]+" ["+item["viewport"]+"]"

indexed_before={key(v):v for v in before["pages"]}
indexed_after={key(v):v for v in after["pages"]}
assert set(indexed_before)==set(indexed_after),"Inventory differs across phases"

def signatures(record):
    return set((v["id"],"|".join(map(str,n["target"])))
        for v in record["violations"] for n in v["nodes"])

fixed=[]
introduced=[]
persistent=[]
for k in sorted(indexed_before):
    a=signatures(indexed_before[k])
    b=signatures(indexed_after[k])
    fixed.extend((k,rule,target) for rule,target in sorted(a-b))
    introduced.extend((k,rule,target) for rule,target in sorted(b-a))
    persistent.extend((k,rule,target) for rule,target in sorted(a&b))

def annotate(item):
    return item[0]+": "+item[1]+" — "+item[2][:115]

old_summary=before["summary"]
new_summary=after["summary"]
lines=[
"# Auditoría automatizada de accesibilidad — Poncho",
"",
"Proyecto original: argob/poncho. Comparación del código original y los parches",
"de una rama experimental. Se evaluaron todas las demostraciones HTML localizadas",
"en el árbol de trabajo, tanto en escritorio (1440 × 900) como en móvil (390 × 844).",
"",
"IMPORTANTE: un resultado favorable en axe-core NO demuestra conformidad WCAG;",
"las páginas que dependen de servidores externos, credenciales o datos remotos",
"pueden haber cargado parcialmente. Deben interpretarse por separado",
"los errores de JavaScript, las solicitudes fallidas y los defectos de accesibilidad.",
"",
"## Cobertura",
"",
f"- Demostraciones encontradas: {before['pagesPerViewport']}.",
f"- Visitas por fase: {len(before['pages'])}.",
f"- Páginas cargadas en origen: {old_summary['loaded']}.",
f"- Páginas cargadas con parches: {new_summary['loaded']}.",
f"- Páginas sin axe funcional: {old_summary['observations'].get('axeFailedPages',0)} originales y {new_summary['observations'].get('axeFailedPages',0)} corregidas.",
f"- Páginas con errores de JS: {old_summary['observations'].get('jsErrorPages',0)} originales y {new_summary['observations'].get('jsErrorPages',0)} corregidas.",
f"- Páginas con errores en recursos locales: {old_summary['observations'].get('badLocalPages',0)} originales y {new_summary['observations'].get('badLocalPages',0)} corregidas.",
f"- Páginas con errores en recursos externos: {old_summary['observations'].get('badExternalPages',0)} originales y {new_summary['observations'].get('badExternalPages',0)} corregidas.",
"",
"## Diferencia de hallazgos detectados por axe-core",
"",
f"- Hallazgos desaparecidos (regla + selector): {len(fixed)}.",
f"- Hallazgos nuevos (regla + selector): {len(introduced)}.",
f"- Hallazgos presentes en ambas versiones: {len(persistent)}.",
"",
"Los hallazgos nuevos no prueban automáticamente una regresión; pueden depender",
"de las cargas asincrónicas y de cambios en la estructura DOM. Cada uno requiere",
"verificación individual antes de presentarlo como defecto.",
"",
"### Reglas y nodos originales",
"",
"| Regla axe-core | Nodos afectados |",
"|---|---:|"
]
for name,count in old_summary["violationNodesByRule"].items():
    lines.append(f"| {name} | {count} |")
lines.extend(["","### Reglas y nodos después de parches","","| Regla axe-core | Nodos afectados |","|---|---:|"])
for name,count in new_summary["violationNodesByRule"].items():
    lines.append(f"| {name} | {count} |")

for title,items,limit in [
    ("Hallazgos que dejan de aparecer",fixed,40),
    ("Posibles regresiones detectadas",introduced,90),
    ("Hallazgos que persisten",persistent,60)
]:
    lines.extend(["","## "+title,""])
    if not items: lines.append("Ninguno registrado.")
    else:
        for item in items[:limit]:lines.append("- "+annotate(item))
        if len(items)>limit:lines.append(f"- ... y {len(items)-limit} adicionales. Ver archivos JSON.")

lines.extend([
"",
"## Limitaciones",
"",
"- Las páginas se abrieron en un servidor local; algunas demostraciones cargan",
"  APIs, mapas, bibliotecas y recursos desde dominios externos.",
"- Un mapa vacío por falta de datos puede ocultar los controles importantes.",
"- axe-core no evalúa anuncios de NVDA, orden lógico de lectura, interacción",
"  completa de diálogos ni todos los criterios WCAG.",
"- La prueba de teclado realiza 12 pulsaciones iniciales de Tab por página.",
"- Las pruebas de NVDA real se realizan en Windows por otro flujo CI.",
"",
"## Evidencia",
"",
"- results/all-demos-before.json: todos los hallazgos originales.",
"- results/all-demos-after.json: hallazgos tras aplicar parches.",
"- results/compare.json: diferencias detalladas.",
"",
"Se recomienda reproducir manualmente cada defecto importante con NVDA.",
""
])
report=OUT/"AUDITORIA-PONCHO.md"
report.write_text("\n".join(lines),encoding="utf-8")
(OUT/"compare.json").write_text(json.dumps(dict(
 demoCount=before["pagesPerViewport"],viewportVisits=len(before["pages"]),
 before=old_summary, after=new_summary,
 resolvedCount=len(fixed),newCount=len(introduced),
 resolved=fixed,introduced=introduced,persistentCount=len(persistent)
),indent=2,ensure_ascii=False),encoding="utf-8")
print(f"Generated report: {report}")
print(f"axe findings resolved={len(fixed)} introduced={len(introduced)} persisted={len(persistent)}")
