# Pasajes Accesibles CNRT

**Pasajes Accesibles CNRT** es un programa gratuito para Windows pensado para que las personas puedan sacar fácilmente sus pasajes correspondientes al cupo de discapacidad.

Desarrollé la aplicación con la idea de hacer que buscar y reservar los pasajes en el sistema web de la CNRT sea un proceso más rápido, sencillo y totalmente accesible por teclado, ratón y lector de pantalla.

Como este es un proyecto independiente, no es una aplicación oficial, por lo que no está patrocinada ni avalada por la Comisión Nacional de Regulación del Transporte (CNRT).

Si te gustaría donar para que pueda seguir haciendo programas como este, puedes hacerlo por estos medios:

- **PayPal:** [paypal.me/paypalmemartinamanecer](https://paypal.me/paypalmemartinamanecer)
- **Mercado Pago:** `imparable.m.pago`

## ¿Qué podés hacer con este programa?

- **Ingresar fácilmente:** Iniciás sesión con tu DNI y tu número de credencial (CUD, INCUCAI o pases municipales/provinciales).
- **Recordar credenciales (opcional):** Si querés, podés hacer que el programa recuerde tus datos de ingreso para no tener que escribirlos cada vez que uses el programa.
- **Buscar sin complicaciones:** Escribís tu origen y destino, y el programa te va a ir sugiriendo las localidades.
- **Búsquedas a tu medida:** Buscás pasajes para un día específico, revisás un rango de varios días o escaneás todas las fechas que la CNRT tenga habilitadas para el origen y destino que ingreses.
- **Resultados útiles:** El programa solo te va a mostrar los servicios que realmente tengan lugares disponibles.
- **Reservas seguras:** Antes de confirmar, el programa vuelve a verificar en tiempo real que el asiento siga libre.
- **Personalizá tu viaje:** Elegís si preferís viajar en planta baja o alta y especificás el motivo.
- **Gestioná tus pasajes:** En la sección **Mis solicitudes** vas a poder leer todos los detalles de tus pasajes y gestionarlos.

## ¿Qué necesitás para usarlo?

- Windows 10 o Windows 11 (versiones de 64 bits).
- Si lo necesitás, un lector de pantalla como NVDA, JAWS, etc.; y si no, no te va a hacer falta porque funciona muy bien usándolo con el ratón.
- Conexión a Internet.

## Cómo descargar e instalar

Tenés dos opciones para usar el programa, y ambas te avisarán si hay alguna actualización para que siempre estés al día con las últimas funciones:

1. **Instalador (`.exe`):** Se instala en tu computadora como cualquier programa tradicional.
2. **Versión portátil (`.zip`):** Ideal si no querés instalar nada. Solo descomprimís el archivo en una carpeta y abrís `pasajes_accesibles_cnrt.exe`.

*Nota técnica: Ya sea que uses la versión instalable o portátil, tus configuraciones y credenciales se guardan en un lugar seguro de tu usuario de Windows (`%APPDATA%`). Esto significa que podés actualizar el programa sin miedo a perder tus datos.*

## Para programadores (instalación desde el código fuente)

Si preferís ejecutar el código directamente, necesitás Python (3.10, 3.11 o 3.12 de 64 bits).

1. Extraé los archivos.
2. Abrí el archivo `instalar.bat` (si no tenés Python, este archivo va a intentar instalarlo por vos usando Winget, además de preparar todo lo necesario).
3. Abrí `ejecutar.bat` para iniciar.

## Privacidad y seguridad

- **Tus datos están protegidos:** Si decidís activar la opción **Recordar credenciales**, tu documento y número de pase se cifran con la máxima seguridad de Windows (DPAPI) y quedan atados únicamente a tu usuario de la computadora.
- **Estadísticas opcionales y anónimas:** Para ayudarme a mejorar el programa, podés elegir enviarme estadísticas de uso. Si lo activás desde el menú de Ayuda, solamente se van a enviar datos técnicos (versión de Windows, qué lector de pantalla o ajuste de accesibilidad usás), así puedo seguir mejorándolo para que las personas tengan o no una discapacidad puedan usarlo mejor.

## Cómo sacar un pasaje

Para buscar y reservar un pasaje, primero ingresá tus datos de sesión (DNI y credencial), elegí si el programa va a recordar esos datos para que no tengas que ponerlos de nuevo cada vez y presioná **Ingresar**.

Después seleccioná la localidad de **Origen** y **Destino** (podés escribir el nombre y usar las **flechas Arriba/Abajo** para seleccionar las opciones de la lista según lo que busques, confirmando con **Enter**).

Luego, elegí una de las **3 formas de búsqueda disponibles**:

1. **Buscar fecha específica (`Alt + S`):** Te permite consultar un día puntual. Podés escribir la fecha en formato `DD-MM-AAAA` (ej. `15-10-2026`) o usar los cuadros de día, mes y año. Dentro del cuadro de fecha, podés cambiar de día rápido con las flechas **Arriba/Abajo**.
2. **Buscar rango de fechas (`Alt + R`):** Podés elegir una fecha de inicio y una de fin para consultar varios días seguidos (ej. del `10-10-2026` al `15-10-2026`).
3. **Escanear todas las fechas disponibles (`Alt + E`):** Revisa de forma automática todas las fechas permitidas por la CNRT para el origen y destino que coloques.

Para iniciar la búsqueda presioná **Alt + F**. El programa solo te va a mostrar los servicios que tengan pasajes libres. Al terminar de buscar, el foco del teclado salta automáticamente a la lista de resultados.

Elegí tu asiento (planta baja o alta) y presioná el botón de envío para confirmar la reserva.

## Cómo gestionar "Mis solicitudes"

Desde la sección **Mis solicitudes** podés revisar y administrar todos los pasajes que tengas pedidos o reservados. En esta pantalla podés hacer 3 cosas principales:

1. **Consultar tus reservas:** Podés leer todos los datos de cada pasaje (origen, destino, empresa, fecha, horario, correo electrónico asociado, cantidad de pasajes y el estado actual del trámite).
2. **Modificar tus datos:** Si la CNRT lo permite para ese pasaje, podés cambiar tu dirección de correo electrónico de contacto o tu preferencia de ubicación (planta baja / alta).
3. **Anular pasajes:** Si ya no vas a viajar, podés cancelar la solicitud directamente desde la aplicación cuando el sistema de CNRT tenga la opción disponible.

## Tips de accesibilidad e interacción

- Podés moverte de un control a otro cómodamente usando las teclas **Tab** y **Shift + Tab**, además de los atajos de teclado.
- Presioná **F6** en cualquier momento para saltar al cuadro de **Estado** y escuchar con tu lector de pantalla los últimos mensajes y novedades del programa.

## Detalles técnicos y límites

El programa funciona interactuando directamente con la página web de la CNRT. Si en el futuro la CNRT cambia el diseño de su página, las rutas o los nombres de los botones, la aplicación se va a detener y te va a mostrar un mensaje de error claro en lugar de intentar hacer una reserva a ciegas con datos incorrectos.

## Licencia

Este proyecto utiliza la Licencia no comercial PolyForm 1.0.0. Podés usar, modificar y compartir el código libremente, pero no está permitido su uso comercial o venta. Para más detalles, consultá el archivo `LICENSE.txt`.

## Historial de cambios

### Versión 1.1

- Mis Solicitudes usa la tabla real de CNRT y conserva el identificador y los enlaces propios de cada reserva.
- Modificación de correo mediante la pantalla oficial `/web/modificarEmail/...`, respetando su token CSRF.
- Modificación de preferencia de viaje mediante `/web/editarPreferenciaViaje/...`.
- Anulación mediante el enlace exacto que CNRT publica para la reserva seleccionada, con confirmación humana previa.
- Verificación posterior de los cambios contra CNRT cuando la interfaz lo permite.
- Botones de acciones deshabilitados automáticamente cuando CNRT no ofrece esa acción para la reserva.

### Versión 1.1.1

- Instalador corregido: ya no exige rígidamente `py -3.11`.
- Detecta Python 3.10, 3.11 o 3.12 de 64 bits mediante `py`, PATH o las rutas habituales de instalación.
- Si no encuentra Python compatible, intenta instalar Python 3.11 mediante winget.
- Las dependencias se instalan llamando directamente al Python del entorno virtual, sin depender de `activate.bat`.
- Si ya existe un entorno virtual funcional, lo reutiliza.

### Versión 1.1.2

- Corregida la detección de Python en `instalar.bat`: ya no usa comparaciones con `>` que CMD podía interpretar de forma incorrecta dentro de `python -c`.
- Si `py -3.11` funciona, el instalador reutiliza esa instalación y no intenta reinstalar Python mediante winget.

### Versión 1.1.3

- Corregido el flujo de confirmación de reservas: el correo del perfil se obtiene antes de preparar la reserva.
- Una vez que CNRT abre `/web/confirmarReserva`, la aplicación no navega a otra página hasta que el usuario confirma o cancela.
- Esto corrige el error `No está abierta la pantalla de confirmación de una reserva` que podía aparecer después de `Reserva preparada`.
- Si no se puede leer el correo del perfil, la reserva igualmente puede prepararse y el correo se ingresa manualmente en la pantalla final.

### Versión 1.1.4

- El menú ahora dice simplemente **Buscar pasajes**.
- Origen y destino usan un único cuadro combinado editable con búsqueda dinámica; no existe una lista de localidades separada.
- Flechas arriba/abajo recorren las coincidencias del mismo cuadro y Enter acepta la localidad.
- Se añadió búsqueda de una fecha concreta sin perder el escaneo de todas las fechas.
- La fecha de viaje puede editarse como `DD-MM-AAAA` y también elegirse mediante Día, Mes y Año.
- Flecha arriba/abajo en una fecha editable avanza o retrocede un día dentro de los límites de CNRT.
- Desde/Hasta permanecen ocultos hasta marcar **Limitar el escaneo a un rango de fechas**.
- Desde/Hasta también disponen de edición directa y de cuadros combinados de Día, Mes y Año.
- Al abrir Buscar pasajes, las fechas se inicializan en la primera fecha actualmente admitida por CNRT.

### Versión 1.1.5

- Se reemplazó la casilla de rango por dos botones de opción: **Buscar fecha específica** (`Alt + E`) y **Buscar rango de fechas** (`Alt + R`).
- Solo se muestran los controles de fecha correspondientes al modo seleccionado.
- El único botón de búsqueda cambia entre **Buscar fecha** y **Buscar fechas** y mantiene `Alt + F`.
- El rango se inicializa desde la primera fecha permitida por CNRT hasta el día siguiente.
- Se eliminó el diálogo adicional de confirmación Sí/No al enviar una reserva; el botón final sigue siendo la acción explícita que envía la solicitud.
- Cuando CNRT confirma una reserva, además del estado aparece un mensaje accesible **Reserva realizada con éxito**.

### Versión 1.1.6

- Cuando CNRT verifica una anulación correctamente, la aplicación muestra un mensaje accesible con el título **Reserva anulada con éxito**.
- El estado accesible también anuncia que la anulación fue verificada por CNRT.
- Se mantiene la confirmación previa antes de anular una solicitud.

### Versión 1.2.0

- Se incorporó una identidad visual clara azul/blanco manteniendo los controles nativos de wxPython.
- Fondo general gris muy claro (`#F5F7FA`) y superficies de entrada/listas blancas.
- Los encabezados de cada pantalla usan azul principal (`#2563EB`) con texto blanco.
- Las acciones principales, como Ingresar, Buscar, Reservar, Preparar reserva, Confirmar y Guardar, se destacan en azul.
- La acción destructiva **Anular solicitud** se diferencia visualmente en rojo (`#B91C1C`).
- El panel Estado usa un fondo azul suave y cambia a verde, rojo o ámbar según éxito, error o advertencia/cancelación, sin depender solo del color: el mensaje textual accesible se conserva.
- Se aumentaron márgenes, altura mínima de botones y jerarquía tipográfica para mejorar la lectura visual.
- El menú principal incluye un subtítulo y destaca **Buscar pasajes** como acción principal.
- No se cambió la lógica de CNRT ni el comportamiento de teclado, foco, ComboBox, radios, reservas o anulaciones.

### Versión 1.2.1

- Se reforzó la accesibilidad visual para personas con baja visión tomando como referencia las recomendaciones de Olga Carreras, WCAG 2.2 y el Editor's Draft de WCAG 3.0 del 2 de octubre de 2026.
- El gris secundario pasó a `#475569` para aumentar claramente el contraste sobre el fondo claro; también se reforzaron los tonos de estado y el borde de referencia.
- El tamaño base de la interfaz parte de la fuente del sistema y nunca baja de 11 puntos.
- El menú **Vista** permite aumentar el texto en pasos de 25 % hasta 200 %, reducirlo y restablecerlo. También funcionan `Ctrl++`, `Ctrl+-` y `Ctrl+0`.
- El porcentaje elegido se recuerda entre ejecuciones.
- El contenido principal usa una ventana desplazable y las filas de acciones/fechas se ajustan mediante `WrapSizer`, para conservar acceso al contenido al ampliar texto o usar magnificación.
- Los botones tienen una altura mínima de 44 píxeles lógicos y crecen junto con el texto.
- En Windows se detecta el modo de alto contraste. Cuando está activo, la aplicación abandona la paleta propia para usar los colores del sistema; también responde si el ajuste cambia mientras la aplicación está abierta.
- Se conserva el indicador de foco nativo de Windows en lugar de sustituirlo por un foco personalizado dependiente del color.
- El bloque Estado añade una indicación textual —Información, Éxito, Error o Aviso— además del color, de modo que el significado no dependa únicamente del tono.
- No se cambió la lógica de CNRT ni el comportamiento de búsqueda, reservas, anulaciones o navegación con NVDA.

#### Nota sobre WCAG 3

WCAG 3.0 sigue siendo un borrador y no se declara conformidad con un estándar todavía no publicado. La versión 1.2.1 usa su dirección de diseño para ajustes del usuario, ampliación del texto, foco, contraste de controles y reflujo. Para ratios numéricos de contraste se mantienen los valores verificables de WCAG 2.2 porque el Editor's Draft de WCAG 3 todavía no ha fijado el algoritmo final de contraste.

#### Referencias de accesibilidad visual usadas en 1.2.1

- [Olga Carreras: Errores habituales de accesibilidad en el acceso con modo alto contraste](https://olgacarreras.blogspot.com/2024/01/errores-habituales-de-accesibilidad-en.html)
- [Olga Carreras: reseña de Accessibility Handbook, apartado sobre baja visión](https://olgacarreras.blogspot.com/2020/09/resena-de-accessibility-handbook-de.html)
- [W3C: WCAG 3.0 Editor's Draft](https://w3c.github.io/wcag3/guidelines/)
- [W3C: WCAG 2.2 Recommendation](https://www.w3.org/TR/WCAG22/)

### Versión 1.2.2

- Se corrigió la relación interna entre el grupo visual **Modo de búsqueda** y sus tres botones de opción.
- Los botones **Buscar fecha específica**, **Buscar rango de fechas** y **Escanear todas las fechas disponibles** ahora son hijos reales del `StaticBox` que los agrupa, como recomienda wxPython.
- Se mantienen exactamente los mismos textos, atajos de teclado, orden de Tab y comportamiento de foco de la versión 1.2.1.
- El auditor `wxpython-accessible-app-development` v1.2 ya no informa hallazgos WX001 en `app.py`.
- No se modificó la lógica de CNRT, las búsquedas, reservas, anulaciones, ComboBox, escalado de texto ni alto contraste.

### Versión 1.2.3

- El encabezado visual ya no expone a tecnologías de asistencia el nombre genérico **Encabezado visual**.
- NVDA recibe el nombre real de cada pantalla: por ejemplo, **Buscar pasajes**, **Resultados de búsqueda**, **Mi información** o **Mis solicitudes**.
- En el menú principal, el encabezado accesible anuncia **Reserva, consulta y gestión accesible de pasajes**.
- La identificación interna del encabezado para aplicar el tema visual quedó separada de su nombre accesible, evitando que una etiqueta técnica llegue al usuario.
- No se modificaron la lógica de CNRT, los atajos, el orden de Tab, los ComboBox ni el comportamiento del foco.

### Versión 1.2.4

- El código original de Pasajes Accesibles CNRT se publica bajo **PolyForm Noncommercial License 1.0.0**.
- Se añadió `LICENSE.txt` con la URL de los términos oficiales y los avisos obligatorios del proyecto.
- Se añadió `THIRD_PARTY_NOTICES.md` para separar claramente la licencia del proyecto de las licencias de Python, wxPython, Playwright y Beautiful Soup.
- Se incorporó una aclaración visible de que Pasajes Accesibles CNRT es un proyecto independiente y no oficial de CNRT.
- No se modificó la lógica de reservas, búsqueda, accesibilidad, navegación por teclado ni comunicación con CNRT.

### Versión 1.2.5

- Se agregó el menú **Ayuda** con acceso mediante `Alt + Y`.
- **Acerca de** (`Alt + A`) muestra la descripción del proyecto, permisos y restricciones de uso, licencia y copyright.
- **Contáctate conmigo** (`Alt + C`) abre un mensaje nuevo en el programa de correo predeterminado dirigido a `martinortiz4362@gmail.com`.

### Versión 1.2.6

- El nombre visible del programa se estableció como **Pasajes Accesibles CNRT**.
- Se actualizaron el título de la ventana, el encabezado principal, el diálogo **Acerca de**, el instalador, la documentación y los avisos de licencia con el nuevo nombre.
- Las referencias funcionales a CNRT se conservaron porque la aplicación sigue trabajando con el sistema oficial de reservas de CNRT.
- En esa entrega todavía se mantuvo temporalmente compatibilidad interna con datos y configuración de versiones anteriores. La versión 1.2.7 elimina esa compatibilidad por decisión del proyecto.

### Versión 1.2.7

- Se completó el cambio de identidad interna a **Pasajes Accesibles CNRT**.
- El paquete Python ahora se llama `pasajes_accesibles_cnrt`.
- La carpeta de datos de usuario ahora es `%APPDATA%\Pasajes Accesibles CNRT`.
- La configuración visual usa `wx.Config("Pasajes Accesibles CNRT")`.
- La descripción usada por DPAPI pasó a `Pasajes Accesibles CNRT`.
- Este cambio es intencionalmente incompatible con la ubicación de datos y configuración de versiones anteriores: no se migran automáticamente preferencias ni credenciales guardadas bajo la identidad anterior.

### Versión 1.2.8

- El nombre completo del programa pasó a **Pasajes Accesibles CNRT**.
- La identidad interna también usa el nuevo nombre, sin conservar compatibilidad con la identidad anterior.
- El paquete Python ahora se llama `pasajes_accesibles_cnrt`.
- La carpeta de datos de usuario ahora es `%APPDATA%\Pasajes Accesibles CNRT`.
- La configuración visual usa `wx.Config("Pasajes Accesibles CNRT")`.
- La descripción usada por DPAPI pasó a `Pasajes Accesibles CNRT`.
- La carpeta raíz de distribución pasó a `Pasajes_Accesibles_CNRT`.

### Versión 1.2.9

- Se añadió telemetría opcional para estadísticas de uso mediante PostHog.
- Toda la recopilación se controla con un único consentimiento accesible de **Sí / No**.
- El consentimiento explica datos técnicos, ajustes de accesibilidad, empresa/origen/destino/fecha de viaje, ubicación aproximada y los datos personales que nunca se envían.
- Se añadió **Ayuda > Privacidad y estadísticas** para cambiar la decisión posteriormente.
- Las estadísticas técnicas usan un identificador aleatorio de instalación; los eventos de viaje usan identificadores aleatorios separados y no incluyen ese identificador de instalación.
- Se detectan NVDA, JAWS, Narrador, Lupa de Windows, alto contraste, Teclas especiales, Teclas filtro, Teclas de alternancia y Teclas de mouse, además de resolución, DPI y escala de texto.
- Una reserva confirmada genera `reservation_completed`; una reserva anulada genera `reservation_cancelled`, para mantener ambas situaciones diferenciadas.
- La telemetría permanece totalmente inactiva hasta que el proyecto tenga configurado un project token público de PostHog.

### Versión 1.2.10

- Se añadió seguimiento anónimo del ciclo de cada reserva.
- Una reserva confirmada genera `reservation_created`.
- Al consultar **Mis solicitudes**, `Activa` genera `reservation_active` solo cuando ese estado cambia o se observa por primera vez.
- `Pasaje Emitido` genera `reservation_ticket_issued`; no se interpreta como viaje realizado.
- Una anulación verificada genera `reservation_cancelled`.
- Cada reserva tiene un UUID aleatorio propio, separado del UUID de instalación y del código real de CNRT.
- El código real de reserva nunca se envía y el seguimiento local lo conserva únicamente como hash opaco.
- Estados desconocidos se agrupan como `other` y no se envía su texto libre.
- Se evita duplicar eventos si CNRT muestra repetidamente el mismo estado.

### Versión 1.2.11

- Se activó la configuración real de PostHog para el proyecto de Pasajes Accesibles CNRT en US Cloud.
- El consentimiento único sigue siendo obligatorio: sin aceptación no se encola ni se envía ningún evento.
- Se mantienen variables de entorno para sustituir el project token o el host durante pruebas o futuras rotaciones.
- No se añadió una dependencia externa de PostHog; la captura continúa usando el endpoint público mediante la biblioteca estándar de Python.

### Versión 1.2.12

- Se añadió `.gitignore` para evitar publicar por accidente entornos virtuales, variables `.env`, logs, volcados, bases locales, certificados y otros archivos generados.
- Se corrigió el encabezado visual restante del instalador para usar **Pasajes Accesibles CNRT**.
- Se añadió `SECURITY.md` con las reglas para publicar el repositorio y la diferencia entre el Project token público `phc_` de PostHog y las claves privadas que nunca deben incluirse.
- Se añadieron pruebas automáticas de higiene del repositorio para detectar regresiones básicas antes de una publicación pública.

### Versión 1.2.13

- Se añadió un sistema de actualización para la futura distribución como ejecutable de Windows.
- **Ayuda > Buscar actualizaciones...** consulta el release estable más reciente de GitHub.
- El ejecutable oficial comprueba automáticamente una vez cada 24 horas si existe una nueva versión y, cuando la encuentra, muestra un diálogo accesible para ofrecer la descarga.
- La descarga exige un instalador con el nombre esperado y verifica su SHA-256 antes de permitir ejecutarlo.
- El instalador se abre como proceso separado y la aplicación se cierra para permitir reemplazar los archivos instalados.
- Se añadieron PyInstaller, un script de Inno Setup y un workflow de GitHub Actions para construir el ejecutable, incluir Chromium de Playwright, generar el instalador y adjuntarlo a GitHub Releases al publicar un tag `vX.Y.Z`.
- El repositorio de actualizaciones se inyecta automáticamente durante la compilación oficial mediante `${{ github.repository }}`; el código fuente no necesita conocer de antemano el usuario o nombre definitivo del repositorio.
- La consulta de actualizaciones es independiente de la telemetría de PostHog y no envía datos de CNRT ni datos de reservas.

### Versión 1.2.14

- Se añadió distribución portátil oficial en cada GitHub Release, además del instalador tradicional.
- El portable incluye el ejecutable, dependencias y Chromium de Playwright; no requiere Python ni instalación.
- El actualizador distingue automáticamente entre instalación y portable y descarga el formato correspondiente.
- Las actualizaciones portátiles verifican SHA-256, validan las rutas del ZIP y rechazan enlaces simbólicos, duplicados y paquetes con estructura inesperada.
- Un actualizador auxiliar independiente espera a que cierre la aplicación, reemplaza la carpeta y vuelve a abrir la nueva versión.
- El reemplazo mantiene una copia anterior durante la operación y vuelve a ella si no logra activar o iniciar la nueva versión.
- Se añadió un manifiesto portable para preservar archivos ajenos al programa que la persona haya guardado dentro de su carpeta.