# Revisión RDD — Pasajes Accesibles CNRT 1.2.14

Fecha: 2026-10-07

## Candidato congelado

La ampliación incorpora un segundo canal de distribución: `Setup.exe` y `Portable.zip`. Ambos se publican en el mismo GitHub Release con SHA-256. El ejecutable detecta el canal portable por un marcador incluido únicamente en ese paquete.

## Risk

- El repositorio oficial continúa fijado durante GitHub Actions y no puede ser sustituido por una variable de entorno en la compilación oficial.
- El actualizador exige el nombre exacto del asset correspondiente al canal y una URL HTTPS dentro del release esperado.
- Antes de aplicar un portable se verifica SHA-256, tamaño, única carpeta raíz, ausencia de `..`, rutas absolutas, barras inversas anómalas, ADS mediante `:`, enlaces simbólicos y archivos duplicados ignorando mayúsculas/minúsculas.
- El auxiliar solo reemplaza carpetas que contengan el marcador portable.
- No se modifica `%APPDATA%`, donde permanecen preferencias, credenciales protegidas y seguimiento local.

## Readability

- `updater.py` concentra descubrimiento, descarga, verificación y preparación del canal.
- `portable_updater.py` es un auxiliar pequeño e independiente dedicado únicamente al cambio de carpeta después de cerrar el proceso principal.
- `tools/write_portable_manifest.py` genera de forma determinista la lista de archivos administrados por el portable.
- El workflow nombra por separado las fases de aplicación, auxiliar, instalador, portable, hashes y release.

## Reliability

Pruebas adversariales cubrieron selección correcta de canal, rechazo de assets externos, hash incorrecto, mezcla de canales, ZIP traversal, duplicados insensibles a mayúsculas, reemplazo completo, rollback al fallar el arranque y preservación de archivos agregados por el usuario.

### Hallazgo del candidato congelado

Se reprodujo un problema: el primer diseño reemplazaba toda la carpeta portable y eliminaba cualquier archivo que la persona hubiera agregado manualmente dentro de ella. Era un problema causado por esta ampliación.

### Única corrección RDD aplicada

Se añadió `.portable-manifest.json`. El helper considera administrados únicamente los archivos que figuraban en el manifiesto de la versión anterior; antes de eliminar la copia de respaldo devuelve a la nueva carpeta los archivos no administrados y nunca sobrescribe con ellos archivos del nuevo paquete. Tras esta corrección se añadió una prueba específica de preservación.

## Resilience

- Una descarga incompleta o con SHA incorrecto se descarta sin tocar la aplicación actual.
- El ZIP se prepara en una carpeta hermana antes de cerrar la aplicación; si no hay permisos o espacio, la versión actual sigue intacta.
- El auxiliar espera a que termine el proceso, conserva temporalmente la carpeta anterior y revierte si no puede activar o iniciar la nueva.
- Los bloqueos transitorios de Windows se reintentan durante un período acotado.
- Si la copia anterior no puede borrarse después de un inicio exitoso, se conserva; eso ocupa espacio pero no invalida la actualización.

## Riesgos residuales documentados

- El instalador y el portable todavía no usan firma Authenticode; SHA-256 verifica integridad respecto del release, pero no sustituye una firma de editor para SmartScreen.
- El comportamiento real de bloqueo de archivos, antivirus, USB y reinicio del helper debe validarse en Windows con el artefacto construido por GitHub Actions.
- La carpeta donde vive el portable debe ser escribible para poder actualizarse automáticamente.

## Resultado

Después de la corrección acotada: 79/79 pruebas correctas, `compileall` correcto y auditor wxPython con 0 hallazgos dirigidos. El build Windows final queda a cargo del workflow al publicar el tag.
