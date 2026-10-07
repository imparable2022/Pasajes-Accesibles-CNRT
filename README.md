# Pasajes Accesibles CNRT

Aplicación de escritorio para Windows orientada a personas usuarias de lectores de pantalla. Automatiza el Sistema Web de Reserva de Pasajes de CNRT sin almacenar tokens de sesión.

**Licencia:** PolyForm Noncommercial License 1.0.0. El código propio del proyecto puede usarse, modificarse y redistribuirse para los fines permitidos por esa licencia, pero no se concede uso comercial. Consulte `LICENSE.txt`.

**Proyecto independiente:** Pasajes Accesibles CNRT no es una aplicación oficial de CNRT ni está desarrollada, patrocinada o avalada por la Comisión Nacional de Regulación del Transporte.

## Funciones

- Inicio de sesión con DNI/documento y credencial CUD, INCUCAI o municipal/provincial.
- Búsqueda dinámica de origen y destino usando el buscador oficial de CNRT, con navegación por teclado.
- Caché local de localidades ya consultadas.
- Búsqueda de una fecha específica o de un rango de fechas elegido por el usuario.
- Presentación únicamente de servicios con opción seleccionable/disponible.
- Revalidación en vivo del servicio antes de reservar.
- Preferencia de planta baja/alta y motivo de preferencia.
- Envío final mediante un botón explícito, sin un segundo diálogo de confirmación.
- Lectura de comprobante de solicitud confirmada.
- Consulta y modificación de teléfono/correo.
- "Mis solicitudes" con lectura de origen, destino, empresa, fecha, horario, correo, cantidad y estado; modificación de correo/preferencia y anulación cuando CNRT ofrece esas acciones.
- Opción de recordar credenciales cifradas con DPAPI de Windows. Desactivada por defecto.

## Requisitos recomendados

- Windows 10 u 11 de 64 bits.
- Para ejecutar desde el código fuente: Python 3.10, 3.11 o 3.12 de 64 bits. Si no hay una versión compatible, `instalar.bat` intenta instalar Python 3.11 mediante winget.
- Para la distribución oficial mediante instalador `.exe`: no es necesario instalar Python por separado.
- NVDA u otro lector de pantalla.
- Conexión a Internet.

## Distribución como ejecutable

El repositorio incluye una compilación para Windows basada en PyInstaller e Inno Setup. Al publicar un tag con formato `vX.Y.Z`, el workflow `.github/workflows/release.yml` valida que el tag coincida con `__version__`, ejecuta las pruebas, compila el programa e incluye Chromium de Playwright. Cada GitHub Release publica dos formatos, ambos con su SHA-256:

- `Pasajes_Accesibles_CNRT_Setup_vX.Y.Z.exe`: instalador por usuario.
- `Pasajes_Accesibles_CNRT_Portable_vX.Y.Z.zip`: versión portable autocontenida, que se ejecuta después de descomprimirla y no necesita instalación.

La versión instalada se guarda en `%LOCALAPPDATA%\Programs\Pasajes Accesibles CNRT`. La versión portable permanece en la carpeta donde la persona la descomprima. En ambos casos, las preferencias, credenciales protegidas y demás datos de usuario se guardan en `%APPDATA%\Pasajes Accesibles CNRT`, por lo que actualizar o reemplazar la carpeta del programa no los elimina.

El actualizador detecta automáticamente el canal. La versión instalada descarga el siguiente Setup; la versión portable descarga el siguiente ZIP portable, valida SHA-256 y la estructura del paquete, cierra la aplicación y usa un auxiliar independiente para reemplazar la carpeta. El portable incluye un manifiesto de archivos administrados para conservar archivos que la persona haya agregado por su cuenta dentro de esa carpeta.

Se requiere Inno Setup 6 para crear el instalador final; el workflow de GitHub Actions realiza todo el empaquetado automáticamente.

## Instalación desde el código fuente

1. Extraiga esta carpeta.
2. Ejecute `instalar.bat`.
3. Ejecute `ejecutar.bat`.

El instalador detecta automáticamente Python 3.10/3.11/3.12 de 64 bits. Si no encuentra una versión compatible y `winget` está disponible, intenta instalar Python 3.11 para el usuario actual. Luego crea un entorno virtual, instala las dependencias y descarga Chromium para Playwright.

## Seguridad

- El programa nunca escribe en archivos los tokens de sesión de CNRT.
- El documento y número de credencial solo se guardan si se marca "Recordar credenciales".
- En Windows, esas credenciales se cifran con DPAPI y quedan vinculadas al usuario de Windows actual.
- El escaneo no reserva nada.
- La reserva definitiva requiere pulsar explícitamente el botón de envío; no aparece un diálogo adicional de Sí/No.
- Antes de preparar la reserva se vuelve a consultar la fecha elegida para comprobar que el servicio siga disponible.


## Privacidad y estadísticas

Pasajes Accesibles CNRT incorpora una capa de telemetría opcional basada en PostHog. No se envía ningún dato mientras no exista un project token configurado y la persona usuaria no haya aceptado el consentimiento único que muestra el programa.

Si se acepta, la aplicación puede enviar estadísticas técnicas generales (versión de la aplicación, Windows/build, arquitectura, CPU y RAM por rangos, idioma, zona horaria, resolución, DPI y escala), ajustes de accesibilidad detectados (NVDA, JAWS, Narrador, Lupa, alto contraste, Teclas especiales, Teclas filtro, Teclas de alternancia y Teclas de mouse) y estadísticas de reservas: empresa, origen, destino, fecha del viaje y estado normalizado observado por CNRT. PostHog puede derivar ubicación aproximada de la conexión, como país, región o ciudad.

No se envían nombre, apellido, DNI, número de CUD, correo electrónico, teléfono, código de reserva ni credenciales de acceso a CNRT. Las estadísticas técnicas usan un identificador aleatorio de instalación para estimar equipos distintos. Cada reserva usa un identificador aleatorio propio y separado, que solo se reutiliza para seguir los cambios de estado de esa misma reserva. Esto permite contar reservas creadas, activas, con pasaje emitido o anuladas sin construir un historial de viajes asociado a una instalación o persona.

`Pasaje Emitido` se registra únicamente como el estado que muestra CNRT; no se interpreta como prueba de que la persona efectivamente haya realizado el viaje. Los cambios de estado se conocen cuando el programa consulta **Mis solicitudes** o verifica una anulación, por lo que son estados observados y no necesariamente todos los cambios ocurridos mientras la aplicación estuvo cerrada.

El consentimiento puede cambiarse desde **Ayuda > Privacidad y estadísticas**. Desactivarlo detiene futuros envíos; no elimina estadísticas ya enviadas. Consulte `PRIVACIDAD.md` para el detalle técnico.

La distribución oficial incluye configurado el project token público de PostHog del proyecto **Pasajes Accesibles CNRT** y usa la región US (`https://us.i.posthog.com`). Esto no hace que se envíen datos automáticamente: la telemetría sigue desactivada hasta que la persona acepte expresamente el consentimiento dentro del programa. Para pruebas o rotación se puede reemplazar la configuración mediante `PASAJES_ACCESIBLES_CNRT_POSTHOG_TOKEN` y `PASAJES_ACCESIBLES_CNRT_POSTHOG_HOST`. Nunca debe colocarse una personal API key (`phx_...`) dentro de la aplicación.

## Búsqueda y fechas

CNRT publica en su formulario una fecha mínima y máxima. La aplicación lee esos límites de la sesión. Puede buscar una fecha específica o recorrer secuencialmente un rango elegido entre esos límites, con una pausa configurable entre consultas. No lanza consultas paralelas.

La fecha puede escribirse como DD-MM-AAAA o elegirse mediante cuadros combinados separados de día, mes y año. En el cuadro de edición, flecha arriba avanza un día y flecha abajo retrocede un día, siempre dentro del período admitido por CNRT.

El modo de búsqueda se elige con tres botones de opción: "Buscar fecha específica" (Alt+S), "Buscar rango de fechas" (Alt+R) y "Escanear todas las fechas disponibles" (Alt+E). Solo se muestran los controles de fecha del modo seleccionado; en el escaneo completo se ocultan. El botón de ejecución cambia entre "Buscar fecha", "Buscar fechas" y "Escanear todas las fechas disponibles", manteniendo Alt+F como acceso rápido a la acción principal. Al cambiar de modo, el foco permanece en el botón de opción seleccionado.

Al abrir la pantalla se usa como referencia la primera fecha actualmente admitida por CNRT; el rango se inicializa desde esa fecha hasta el día siguiente, siempre dentro del máximo permitido.

## Accesibilidad

La interfaz usa controles nativos de wxPython y un orden de tabulación lineal. Origen y destino son cuadros combinados editables: el texto y sus coincidencias forman un solo control. Al terminar una búsqueda de pasajes, el foco pasa a la lista de servicios disponibles. El cuadro "Estado" conserva los últimos mensajes para que puedan revisarse con NVDA.

Uso por teclado en Buscar pasajes:

- Origen y destino son cuadros combinados editables y se filtran automáticamente mientras se escribe.
- Flechas arriba/abajo recorren las coincidencias dentro del mismo control; Enter acepta la localidad.
- Flechas izquierda/derecha siguen moviendo el cursor por el texto del cuadro editable.
- Flechas izquierda/derecha conservan su función normal de mover el cursor mientras el foco está en el cuadro de edición.
- En cualquier fecha editable, flecha arriba/abajo cambia un día.
- F6 mueve el foco al cuadro Estado.

## Límites conocidos

Las funciones principales se desarrollaron contra las estructuras HTML suministradas: ingreso, búsqueda, servicios disponibles, confirmación, comprobante, Mi Información, Mis Solicitudes, Modificar Email y Modificar Preferencia Viaje. Aun así, la primera ejecución con una cuenta autorizada debe validar el comportamiento de redirecciones y mensajes del servidor real.

Si CNRT cambia nombres de campos, rutas o estructura HTML, la aplicación mostrará un error descriptivo en lugar de intentar completar una reserva con datos inciertos.


## Cambios de la versión 1.1

- Mis Solicitudes usa la tabla real de CNRT y conserva el identificador y los enlaces propios de cada reserva.
- Modificación de correo mediante la pantalla oficial `/web/modificarEmail/...`, respetando su token CSRF.
- Modificación de preferencia de viaje mediante `/web/editarPreferenciaViaje/...`.
- Anulación mediante el enlace exacto que CNRT publica para la reserva seleccionada, con confirmación humana previa.
- Verificación posterior de los cambios contra CNRT cuando la interfaz lo permite.
- Botones de acciones deshabilitados automáticamente cuando CNRT no ofrece esa acción para la reserva.


## Cambios de la versión 1.1.1

- Instalador corregido: ya no exige rígidamente `py -3.11`.
- Detecta Python 3.10, 3.11 o 3.12 de 64 bits mediante `py`, PATH o las rutas habituales de instalación.
- Si no encuentra Python compatible, intenta instalar Python 3.11 mediante winget.
- Las dependencias se instalan llamando directamente al Python del entorno virtual, sin depender de `activate.bat`.
- Si ya existe un entorno virtual funcional, lo reutiliza.


## Cambios de la versión 1.1.2

- Corregida la detección de Python en `instalar.bat`: ya no usa comparaciones con `>` que CMD podía interpretar de forma incorrecta dentro de `python -c`.
- Si `py -3.11` funciona, el instalador reutiliza esa instalación y no intenta reinstalar Python mediante winget.


## Cambios de la versión 1.1.3

- Corregido el flujo de confirmación de reservas: el correo del perfil se obtiene antes de preparar la reserva.
- Una vez que CNRT abre `/web/confirmarReserva`, la aplicación no navega a otra página hasta que el usuario confirma o cancela.
- Esto corrige el error `No está abierta la pantalla de confirmación de una reserva` que podía aparecer después de `Reserva preparada`.
- Si no se puede leer el correo del perfil, la reserva igualmente puede prepararse y el correo se ingresa manualmente en la pantalla final.


## Cambios de la versión 1.1.4

- El menú ahora dice simplemente "Buscar pasajes".
- Origen y destino usan un único cuadro combinado editable con búsqueda dinámica; no existe una lista de localidades separada.
- Flechas arriba/abajo recorren las coincidencias del mismo cuadro y Enter acepta la localidad.
- Se añadió búsqueda de una fecha concreta sin perder el escaneo de todas las fechas.
- La fecha de viaje puede editarse como DD-MM-AAAA y también elegirse mediante Día, Mes y Año.
- Flecha arriba/abajo en una fecha editable avanza o retrocede un día dentro de los límites de CNRT.
- Desde/Hasta permanecen ocultos hasta marcar "Limitar el escaneo a un rango de fechas".
- Desde/Hasta también disponen de edición directa y de cuadros combinados de Día, Mes y Año.
- Al abrir Buscar pasajes, las fechas se inicializan en la primera fecha actualmente admitida por CNRT.


## Cambios de la versión 1.1.5

- Se reemplazó la casilla de rango por dos botones de opción: "Buscar fecha específica" (Alt+E) y "Buscar rango de fechas" (Alt+R).
- Solo se muestran los controles de fecha correspondientes al modo seleccionado.
- El único botón de búsqueda cambia entre "Buscar fecha" y "Buscar fechas" y mantiene Alt+F.
- El rango se inicializa desde la primera fecha permitida por CNRT hasta el día siguiente.
- Se eliminó el diálogo adicional de confirmación Sí/No al enviar una reserva; el botón final sigue siendo la acción explícita que envía la solicitud.
- Cuando CNRT confirma una reserva, además del estado aparece un mensaje accesible "Reserva realizada con éxito".

## Cambios de la versión 1.1.6

- Cuando CNRT verifica una anulación correctamente, la aplicación muestra un mensaje accesible con el título **Reserva anulada con éxito**.
- El estado accesible también anuncia que la anulación fue verificada por CNRT.
- Se mantiene la confirmación previa antes de anular una solicitud.

## Cambios de la versión 1.2.0

- Se incorporó una identidad visual clara azul/blanco manteniendo los controles nativos de wxPython.
- Fondo general gris muy claro (`#F5F7FA`) y superficies de entrada/listas blancas.
- Los encabezados de cada pantalla usan azul principal (`#2563EB`) con texto blanco.
- Las acciones principales, como Ingresar, Buscar, Reservar, Preparar reserva, Confirmar y Guardar, se destacan en azul.
- La acción destructiva "Anular solicitud" se diferencia visualmente en rojo (`#B91C1C`).
- El panel Estado usa un fondo azul suave y cambia a verde, rojo o ámbar según éxito, error o advertencia/cancelación, sin depender solo del color: el mensaje textual accesible se conserva.
- Se aumentaron márgenes, altura mínima de botones y jerarquía tipográfica para mejorar la lectura visual.
- El menú principal incluye un subtítulo y destaca "Buscar pasajes" como acción principal.
- No se cambió la lógica de CNRT ni el comportamiento de teclado, foco, ComboBox, radios, reservas o anulaciones.

## Cambios de la versión 1.2.1

- Se reforzó la accesibilidad visual para personas con baja visión tomando como referencia las recomendaciones de Olga Carreras, WCAG 2.2 y el Editor's Draft de WCAG 3.0 del 2 de octubre de 2026.
- El gris secundario pasó a `#475569` para aumentar claramente el contraste sobre el fondo claro; también se reforzaron los tonos de estado y el borde de referencia.
- El tamaño base de la interfaz parte de la fuente del sistema y nunca baja de 11 puntos.
- El menú **Vista** permite aumentar el texto en pasos de 25 % hasta 200 %, reducirlo y restablecerlo. También funcionan `Ctrl++`, `Ctrl+-` y `Ctrl+0`.
- El porcentaje elegido se recuerda entre ejecuciones.
- El contenido principal usa una ventana desplazable y las filas de acciones/fechas se ajustan mediante `WrapSizer`, para conservar acceso al contenido al ampliar texto o usar magnificación.
- Los botones tienen una altura mínima de 44 píxeles lógicos y crecen junto con el texto.
- En Windows se detecta el modo de alto contraste. Cuando está activo, la aplicación abandona la paleta propia para usar los colores del sistema; también responde si el ajuste cambia mientras la aplicación está abierta.
- Se conserva el indicador de foco nativo de Windows en lugar de sustituirlo por un foco personalizado dependiente del color.
- El bloque Estado añade una indicación textual (`Información`, `Éxito`, `Error` o `Aviso`) además del color, de modo que el significado no dependa únicamente del tono.
- No se cambió la lógica de CNRT ni el comportamiento de búsqueda, reservas, anulaciones o navegación con NVDA.



## Cambios de la versión 1.2.6

- El nombre visible del programa se estableció como **Pasajes Accesibles CNRT**.
- Se actualizaron el título de la ventana, el encabezado principal, el diálogo **Acerca de**, el instalador, la documentación y los avisos de licencia con el nuevo nombre.
- Las referencias funcionales a CNRT se conservaron porque la aplicación sigue trabajando con el sistema oficial de reservas de CNRT.
- En esa entrega todavía se mantuvo temporalmente compatibilidad interna con datos y configuración de versiones anteriores. La versión 1.2.7 elimina esa compatibilidad por decisión del proyecto.

## Cambios de la versión 1.2.5

- Se agregó el menú **Ayuda** con acceso mediante `Alt+Y`.
- **Acerca de** (`Alt+A`) muestra la descripción del proyecto, permisos y restricciones de uso, licencia y copyright.
- **Contáctate conmigo** (`Alt+C`) abre un mensaje nuevo en el programa de correo predeterminado dirigido a `martinortiz4362@gmail.com`.

## Cambios de la versión 1.2.4

- El código original de Pasajes Accesibles CNRT se publica bajo **PolyForm Noncommercial License 1.0.0**.
- Se añadió `LICENSE.txt` con la URL de los términos oficiales y los avisos obligatorios del proyecto.
- Se añadió `THIRD_PARTY_NOTICES.md` para separar claramente la licencia del proyecto de las licencias de Python, wxPython, Playwright y Beautiful Soup.
- Se incorporó una aclaración visible de que Pasajes Accesibles CNRT es un proyecto independiente y no oficial de CNRT.
- No se modificó la lógica de reservas, búsqueda, accesibilidad, navegación por teclado ni comunicación con CNRT.

## Cambios de la versión 1.2.3

- El encabezado visual ya no expone a tecnologías de asistencia el nombre genérico “Encabezado visual”.
- NVDA recibe el nombre real de cada pantalla: por ejemplo, “Buscar pasajes”, “Resultados de búsqueda”, “Mi información” o “Mis solicitudes”.
- En el menú principal, el encabezado accesible anuncia “Reserva, consulta y gestión accesible de pasajes”.
- La identificación interna del encabezado para aplicar el tema visual quedó separada de su nombre accesible, evitando que una etiqueta técnica llegue al usuario.
- No se modificaron la lógica de CNRT, los atajos, el orden de Tab, los ComboBox ni el comportamiento del foco.

## Cambios de la versión 1.2.2

- Se corrigió la relación interna entre el grupo visual **Modo de búsqueda** y sus tres botones de opción.
- Los botones **Buscar fecha específica**, **Buscar rango de fechas** y **Escanear todas las fechas disponibles** ahora son hijos reales del `StaticBox` que los agrupa, como recomienda wxPython.
- Se mantienen exactamente los mismos textos, atajos de teclado, orden de Tab y comportamiento de foco de la versión 1.2.1.
- El auditor `wxpython-accessible-app-development` v1.2 ya no informa hallazgos WX001 en `app.py`.
- No se modificó la lógica de CNRT, las búsquedas, reservas, anulaciones, ComboBox, escalado de texto ni alto contraste.

### Nota sobre WCAG 3

WCAG 3.0 sigue siendo un borrador y no se declara conformidad con un estándar todavía no publicado. La versión 1.2.1 usa su dirección de diseño para ajustes del usuario, ampliación del texto, foco, contraste de controles y reflujo. Para ratios numéricas de contraste se mantienen los valores verificables de WCAG 2.2 porque el Editor's Draft de WCAG 3 todavía no ha fijado el algoritmo final de contraste.


### Referencias de accesibilidad visual usadas en 1.2.1

- Olga Carreras, "Errores habituales de accesibilidad en el acceso con modo alto contraste": https://olgacarreras.blogspot.com/2024/01/errores-habituales-de-accesibilidad-en.html
- Olga Carreras, reseña de "Accessibility Handbook", apartado sobre baja visión: https://olgacarreras.blogspot.com/2020/09/resena-de-accessibility-handbook-de.html
- W3C, WCAG 3.0 Editor's Draft (2 de octubre de 2026 al desarrollar esta versión): https://w3c.github.io/wcag3/guidelines/
- W3C, WCAG 2.2 Recommendation, usada para los ratios numéricos de contraste: https://www.w3.org/TR/WCAG22/

## Cambios de la versión 1.2.7

- Se completó el cambio de identidad interna a **Pasajes Accesibles CNRT**.
- El paquete Python ahora se llama `pasajes_accesibles_cnrt`.
- La carpeta de datos de usuario ahora es `%APPDATA%\\Pasajes Accesibles CNRT`.
- La configuración visual usa `wx.Config("Pasajes Accesibles CNRT")`.
- La descripción usada por DPAPI pasó a `Pasajes Accesibles CNRT`.
- Este cambio es intencionalmente incompatible con la ubicación de datos y configuración de versiones anteriores: no se migran automáticamente preferencias ni credenciales guardadas bajo la identidad anterior.

## Cambios de la versión 1.2.8

- El nombre completo del programa pasó a **Pasajes Accesibles CNRT**.
- La identidad interna también usa el nuevo nombre, sin conservar compatibilidad con la identidad anterior.
- El paquete Python ahora se llama `pasajes_accesibles_cnrt`.
- La carpeta de datos de usuario ahora es `%APPDATA%\Pasajes Accesibles CNRT`.
- La configuración visual usa `wx.Config("Pasajes Accesibles CNRT")`.
- La descripción usada por DPAPI pasó a `Pasajes Accesibles CNRT`.
- La carpeta raíz de distribución pasó a `Pasajes_Accesibles_CNRT`.

## Cambios de la versión 1.2.9

- Se añadió telemetría opcional para estadísticas de uso mediante PostHog.
- Toda la recopilación se controla con un único consentimiento accesible de **Sí / No**.
- El consentimiento explica datos técnicos, ajustes de accesibilidad, empresa/origen/destino/fecha de viaje, ubicación aproximada y los datos personales que nunca se envían.
- Se añadió **Ayuda > Privacidad y estadísticas** para cambiar la decisión posteriormente.
- Las estadísticas técnicas usan un identificador aleatorio de instalación; los eventos de viaje usan identificadores aleatorios separados y no incluyen ese identificador de instalación.
- Se detectan NVDA, JAWS, Narrador, Lupa de Windows, alto contraste, Teclas especiales, Teclas filtro, Teclas de alternancia y Teclas de mouse, además de resolución, DPI y escala de texto.
- Una reserva confirmada genera `reservation_completed`; una reserva anulada genera `reservation_cancelled`, para mantener ambas situaciones diferenciadas.
- La telemetría permanece totalmente inactiva hasta que el proyecto tenga configurado un project token público de PostHog.


## Cambios de la versión 1.2.10

- Se añadió seguimiento anónimo del ciclo de cada reserva.
- Una reserva confirmada genera `reservation_created`.
- Al consultar **Mis solicitudes**, `Activa` genera `reservation_active` solo cuando ese estado cambia o se observa por primera vez.
- `Pasaje Emitido` genera `reservation_ticket_issued`; no se interpreta como viaje realizado.
- Una anulación verificada genera `reservation_cancelled`.
- Cada reserva tiene un UUID aleatorio propio, separado del UUID de instalación y del código real de CNRT.
- El código real de reserva nunca se envía y el seguimiento local lo conserva únicamente como hash opaco.
- Estados desconocidos se agrupan como `other` y no se envía su texto libre.
- Se evita duplicar eventos si CNRT muestra repetidamente el mismo estado.


## Cambios de la versión 1.2.11

- Se activó la configuración real de PostHog para el proyecto de Pasajes Accesibles CNRT en US Cloud.
- El consentimiento único sigue siendo obligatorio: sin aceptación no se encola ni se envía ningún evento.
- Se mantienen variables de entorno para sustituir el project token o el host durante pruebas o futuras rotaciones.
- No se añadió una dependencia externa de PostHog; la captura continúa usando el endpoint público mediante la biblioteca estándar de Python.

## Cambios de la versión 1.2.12

- Se añadió `.gitignore` para evitar publicar por accidente entornos virtuales, variables `.env`, logs, volcados, bases locales, certificados y otros archivos generados.
- Se corrigió el encabezado visual restante del instalador para usar **Pasajes Accesibles CNRT**.
- Se añadió `SECURITY.md` con las reglas para publicar el repositorio y la diferencia entre el Project token público `phc_` de PostHog y las claves privadas que nunca deben incluirse.
- Se añadieron pruebas automáticas de higiene del repositorio para detectar regresiones básicas antes de una publicación pública.


## Cambios de la versión 1.2.13

- Se añadió un sistema de actualización para la futura distribución como ejecutable de Windows.
- **Ayuda > Buscar actualizaciones...** consulta el release estable más reciente de GitHub.
- El ejecutable oficial comprueba automáticamente una vez cada 24 horas si existe una nueva versión y, cuando la encuentra, muestra un diálogo accesible para ofrecer la descarga.
- La descarga exige un instalador con el nombre esperado y verifica su SHA-256 antes de permitir ejecutarlo.
- El instalador se abre como proceso separado y la aplicación se cierra para permitir reemplazar los archivos instalados.
- Se añadieron PyInstaller, un script de Inno Setup y un workflow de GitHub Actions para construir el ejecutable, incluir Chromium de Playwright, generar el instalador y adjuntarlo a GitHub Releases al publicar un tag `vX.Y.Z`.
- El repositorio de actualizaciones se inyecta automáticamente durante la compilación oficial mediante `${{ github.repository }}`; el código fuente no necesita conocer de antemano el usuario o nombre definitivo del repositorio.
- La consulta de actualizaciones es independiente de la telemetría de PostHog y no envía datos de CNRT ni datos de reservas.


## Cambios de la versión 1.2.14

- Se añadió distribución portable oficial en cada GitHub Release, además del instalador tradicional.
- El portable incluye el ejecutable, dependencias y Chromium de Playwright; no requiere Python ni instalación.
- El actualizador distingue automáticamente entre instalación y portable y descarga el formato correspondiente.
- Las actualizaciones portable verifican SHA-256, validan las rutas del ZIP y rechazan enlaces simbólicos, duplicados y paquetes con estructura inesperada.
- Un actualizador auxiliar independiente espera a que cierre la aplicación, reemplaza la carpeta y vuelve a abrir la nueva versión.
- El reemplazo mantiene una copia anterior durante la operación y vuelve a ella si no logra activar o iniciar la nueva versión.
- Se añadió un manifiesto portable para preservar archivos ajenos al programa que la persona haya guardado dentro de su carpeta.
