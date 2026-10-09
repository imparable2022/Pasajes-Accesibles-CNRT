# Revisión RDD — Pasajes Accesibles CNRT 1.2.13

Fecha: 2026-10-07

Alcance: nuevo sistema de construcción de ejecutable/instalador de Windows y actualización mediante GitHub Releases.

## Candidato congelado

Antes de la revisión adversarial se congeló un manifiesto SHA-256 del candidato funcional. El manifiesto del candidato tenía SHA-256:

`4be34202ee6374fa90841351c49610062498beb4d3e7d180eaa019ad483fd178`

La revisión se hizo después de comprobar que el candidato pasaba la suite funcional existente.

## Lente Risk

### Hallazgo reproducible

El candidato permitía que la variable de entorno `PASAJES_CNRT_UPDATE_REPOSITORY` tuviera prioridad sobre el repositorio oficial inyectado durante la compilación. Un ejecutable oficial configurado para `martin/oficial` podía terminar consultando `atacante/falso` si esa variable estaba presente.

Eso era una ruptura de la cadena de confianza: el repositorio alternativo también podía publicar su propio instalador y su propio SHA-256.

### Corrección aplicada

- El repositorio inyectado por GitHub Actions tiene ahora prioridad absoluta en una compilación oficial.
- La variable de entorno solo se usa cuando `build_info.py` no contiene repositorio, es decir, para desarrollo desde el código fuente.
- Se añadieron pruebas de regresión para ambos casos.
- `actions/checkout` usa `persist-credentials: false` para no dejar las credenciales del workflow persistidas en la copia de trabajo durante la instalación de dependencias y el build.

### Comprobaciones de riesgo posteriores

- El actualizador solo acepta el release estable más reciente del repositorio fijado.
- El nombre del instalador debe coincidir exactamente con la versión esperada.
- La URL del instalador y, si se usa, la del `.sha256` deben pertenecer al mismo repositorio/tag esperado de GitHub Releases.
- Se valida un tamaño máximo y el tamaño exacto publicado.
- El SHA-256 descargado debe coincidir antes de renombrar el archivo parcial como instalador válido.
- Se añadieron pruebas que rechazan un instalador alojado fuera del release esperado y un checksum perteneciente a otro repositorio.
- El instalador no se ejecuta de forma silenciosa: la persona debe aceptar la descarga y luego aceptar la instalación.

### Riesgo residual aceptado

SHA-256 verifica que el archivo descargado coincide con el release consultado, pero no sustituye una firma Authenticode de editor. Si la cuenta/repositorio oficial de GitHub fuera comprometido, un atacante con capacidad de publicar un release podría publicar también un hash válido. Se documentó que, si el proyecto obtiene un certificado de firma de código, conviene firmar ejecutable e instalador.

## Lente Readability

- La lógica de red queda aislada en `pasajes_accesibles_cnrt/updater.py`.
- La identidad del repositorio oficial queda separada en `build_info.py` y se genera con `tools/generate_build_info.py`.
- El empaquetado está separado entre `PasajesAccesiblesCNRT.spec`, `installer/PasajesAccesiblesCNRT.iss` y `.github/workflows/release.yml`.
- `ARQUITECTURA.md`, `README.md` y `SECURITY.md` describen el flujo y la frontera de confianza.
- La interfaz solo coordina comprobación, diálogo, descarga y apertura del instalador; no implementa directamente HTTP ni validación criptográfica.

Resultado: sin hallazgos bloqueantes de legibilidad o separación de responsabilidades para este módulo.

## Lente Reliability

Se validaron, entre otros, estos contratos:

- comparación de versiones `X.Y.Z`;
- release igual o anterior no genera actualización;
- release nuevo exige instalador esperado y SHA-256;
- instalador alterado se descarta;
- descarga válida conserva exactamente los bytes verificados;
- repositorio oficial no puede ser reemplazado por variable de entorno;
- el workflow exige que el tag `vX.Y.Z` coincida con `__version__`;
- el workflow ejecuta pruebas y `compileall` antes de construir el release;
- comprobación automática como máximo una vez cada 24 horas;
- comprobación manual disponible en **Ayuda > Buscar actualizaciones...**;
- si una comprobación automática encuentra una versión nueva, muestra el diálogo **Actualización disponible**, tal como se requiere para el producto.

Suite final: **68/68 pruebas correctas**.

## Lente Resilience

- La consulta y la descarga se ejecutan en hilos en segundo plano, sin bloquear el hilo de wxPython.
- Los resultados vuelven a la interfaz mediante `wx.CallAfter`.
- Si no hay red, GitHub devuelve error o la respuesta es inválida, no se reemplaza ningún archivo del programa.
- Una descarga interrumpida se guarda como `.part`; en un nuevo intento ese parcial se elimina antes de empezar.
- Si el hash o el tamaño no coincide, el instalador se descarta.
- La aplicación actual no intenta sobrescribirse a sí misma: abre el instalador como proceso separado y después se cierra.
- El instalador es por usuario (`%LOCALAPPDATA%\\Programs\\Pasajes Accesibles CNRT`) y no elimina los datos persistentes de `%APPDATA%\\Pasajes Accesibles CNRT`.
- Si el código fuente se ejecuta sin repositorio configurado, la comprobación automática no interfiere y la comprobación manual explica que falta la configuración de release.

### Decisión de producto sobre el foco

Durante la revisión se consideró evitar un diálogo modal en la comprobación automática para que no interrumpiera el foco. El requisito final del producto es el contrario: **cuando la comprobación automática encuentre una actualización debe aparecer el diálogo de actualización**, además de existir la opción manual. Se conserva ese comportamiento y se limita la comprobación automática a una vez cada 24 horas para no repetir el aviso en cada inicio.

## Auditoría accesible

El auditor estático `wxpython-accessible-app-development 1.2.3` terminó con **0 hallazgos dirigidos**. Esto no sustituye la validación real con NVDA en Windows.

## Verificaciones externas usadas

- GitHub documenta el endpoint público `GET /repos/{owner}/{repo}/releases/latest` y los assets de releases.
- La respuesta de assets admite el campo `digest` con SHA-256.
- El runner `windows-2025` está disponible y actualmente incluye Inno Setup 6.

## Resultado RDD

**Aprobado después de la corrección de la cadena de confianza del repositorio.**

No quedaron hallazgos críticos o altos reproducibles dentro del alcance del actualizador. Queda como mejora futura la firma Authenticode del ejecutable/instalador cuando se disponga de un certificado de firma de código.
