# Propuesta de dos contribuciones independientes a Anki

Estado: **preparación y pruebas**, no es una PR publicada en `ankitects/anki`.
Fuentes upstream inspeccionadas: `ankitects/anki`, `main` en
`827f4aa42681f1d60ab0fe4ad76eb75d767a385e` (13 de noviembre de 2026).

## PR 1: nombres accesibles de los campos del editor

Archivo: `0001-editor-fields-accessible-names.patch`.

La propuesta modifica solamente cuatro componentes Svelte del editor:

- `NoteEditor.svelte`: transmite `field.name` al editor de texto enriquecido y al de HTML.
- `RichTextInput.svelte`: aplica el nombre al `anki-editable` que recibe el foco en el *shadow DOM* (no a un contenedor).
- `PlainTextInput.svelte`: transmite el nombre a CodeMirror.
- `CodeMirror.svelte`: etiqueta el `getInputField()` real, no el `textarea` oculto utilizado para inicializarlo.

No cambia los atajos de teclado ni desplaza el foco. Los nombres se actualizan
tras cambiar el tipo de nota o los nombres de campo.

**Validación realizada hasta ahora:** el equivalente implementado como
complemento anunció `Front edit focused blank` y `Back edit focused blank`
con NVDA real. Los tests de comportamiento cubren renombrar campos y la
ausencia de cambios en el revisor. El propio parche Svelte se comprueba con
`git apply --check` sobre el commit exacto de upstream en CI; **esto no
equivale a compilar ni probar en ejecución la variante integrada a Anki**.

**Pendiente para la PR:** compilar el proyecto upstream, probar el cambio de
tipo de nota y de idioma durante una sesión, confirmar que no hay doble
anuncio en NVDA/JAWS/Narrador y verificar que no interfiere con los controles
de CodeMirror ni con campos definidos por complementos.

## PR 2: comportamiento de enfoque del revisor

La implementación de prueba se aisló en
`../anki-accessibility-prototype/reviewer_focus.py`, completamente separada
de `editor_labels.py` y desactivada por defecto.

El prototipo demostró en Windows que una tarjeta básica breve puede anunciar
pregunta y respuesta de manera automática al recibir el foco, sin reescribir
el DOM de la tarjeta. También comprobamos tarjetas complejas y la restauración
de atributos al cambiar de tarjeta.

**No hay todavía un parche upstream recomendado para el revisor**. No es
responsable introducir `aria-label` con todo el texto visible de cualquier
tarjeta, pues eso ocultaría estructura semántica, fórmulas, enlaces, imágenes,
medios e interacciones. Se requiere acordar con los mantenedores si la opción
debe ser una preferencia, cómo debería funcionar en Qt WebEngine y qué
comportamiento resulta adecuado en NVDA/JAWS/VoiceOver/Orca. Los resultados
de lectura real de fracciones, exponentes, ecuaciones, textos alternativos y
controles de sonido se registran por separado en `semantic-audit.json`.

## Controles de regresión disponibles

- `test_policy.py` y `review_dom_harness.js`: no mover el foco por defecto,
  restaurar `role`, `tabindex` y `aria-label`, conservar la estructura y
  el foco en tarjetas con controles, limitar anuncios, impedir truncamientos,
  actualizar nombres de campos sin perderlos.
- `ankiNvda.robot` y `AnkiNvdaTests.py`: teclado real y registros del
  habla de NVDA con Anki instalado en Windows. Prueba un recorrido básico y
  las tarjetas de imagen, MathJax, audio, texto largo, escritura de respuesta,
  Cloze, tabla y controles interactivos.
- `AnkiNoAtKeyboard.py`: prueba independiente sin NVDA, Narrador ni JAWS,
  con el enfoque automático desactivado, para detectar regresiones de
  navegación por teclado.
- Los controles matemáticos/multimedia ahora se registran como **comprobados,
  no demostrados o fallidos en cuanto a habla**. Completar un recorrido no es
  lo mismo que comprender una ecuación o escuchar un audio.

## Procedimiento de contribución

1. Aplicar `0001-editor-fields-accessible-names.patch` en una rama de un
   *fork* actualizado del proyecto Anki (basada en el commit indicado).
2. Ejecutar compilación, pruebas Svelte y E2E de Anki; contrastar con NVDA.
3. Presentar exclusivamente la mejora del editor en una PR pequeña.
4. Abrir una discusión técnica independiente para el revisor con las
   evidencias de `semantic-audit.json` y acordar el comportamiento esperado.
5. Preparar una segunda PR para el revisor cuando exista una solución
   accesible para contenido complejo, sin fingir resultados.

La rama de auditoría en `Pasajes-Accesibles-CNRT` conserva las pruebas. No
se modificó ni se publicó una rama dentro del repositorio original de Anki.
