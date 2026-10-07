# Privacidad y estadísticas de Pasajes Accesibles CNRT

## Consentimiento

La telemetría está desactivada si no existe un project token de PostHog configurado. Cuando la integración está configurada, en el primer inicio sin una decisión previa el programa muestra un único consentimiento con dos opciones: compartir o no compartir estadísticas. La decisión se guarda localmente y puede cambiarse desde **Ayuda > Privacidad y estadísticas**.

## Qué se recopila al aceptar

### Estadísticas técnicas

- versión de Pasajes Accesibles CNRT;
- Windows y número de compilación;
- arquitectura;
- cantidad lógica de CPU agrupada por rangos;
- memoria RAM agrupada por rangos;
- idioma y zona horaria;
- resolución de pantalla y DPI;
- escala de texto elegida dentro de la aplicación.

### Accesibilidad

La detección está limitada a funciones concretas. No se envía una lista general de procesos ni programas instalados.

- NVDA;
- JAWS;
- Narrador de Windows;
- Lupa de Windows;
- indicador de lector de pantalla de Windows;
- alto contraste;
- Teclas especiales;
- Teclas filtro;
- Teclas de alternancia;
- Teclas de mouse.

### Reservas y viajes

Cuando CNRT confirma una reserva se registra `reservation_created` con:

- empresa;
- origen;
- destino;
- fecha del viaje.

Cuando **Mis solicitudes** vuelve a mostrar esa reserva, el programa puede registrar cambios de estado normalizados:

- `active`, cuando CNRT muestra **Activa** o mantiene disponible la acción Anular;
- `ticket_issued`, cuando CNRT muestra **Pasaje Emitido**;
- `cancelled`, cuando CNRT muestra un estado de anulación/cancelación o la anulación fue verificada por el propio programa;
- `other`, para cualquier estado no reconocido. El texto desconocido no se envía.

`Pasaje Emitido` significa que CNRT muestra el pasaje como emitido; **no se interpreta como confirmación de que la persona efectivamente viajó**.

### Ubicación aproximada

El servicio de estadísticas puede derivar de la conexión información aproximada como país, región o ciudad. La aplicación no consulta GPS ni guarda una dirección física.

## Qué no se recopila

La telemetría no recibe nombre, apellido, DNI, número de CUD u otra credencial, correo electrónico, teléfono, código de reserva, nombre de usuario de Windows, nombre del equipo, dirección MAC, número de serie ni una lista completa de procesos o programas instalados.

## Separación entre estadísticas técnicas y reservas

Las estadísticas técnicas pueden usar un UUID aleatorio de instalación para estimar equipos distintos. Cada reserva usa otro UUID aleatorio con prefijo `reservation-`, separado del identificador de instalación. Ese identificador se reutiliza solamente entre los eventos de **esa reserva** para poder medir su ciclo de estado sin conocer quién la hizo.

El número/código real de reserva de CNRT nunca se envía a PostHog. El archivo local de seguimiento tampoco lo guarda en claro: conserva un hash opaco, el UUID aleatorio de la reserva y el último estado observado. Tampoco guarda en claro empresa, origen ni destino. Se mantiene `$process_person_profile` en `false` para evitar crear perfiles de personas.

Los estados solo pueden actualizarse cuando la aplicación vuelve a consultar **Mis solicitudes** o cuando verifica una anulación. Por eso estas métricas representan estados **observados por la aplicación**, no un registro exhaustivo de todos los cambios ocurridos en CNRT mientras el programa estaba cerrado.

## Configuración de PostHog

La distribución oficial tiene configurado un project token público de captura para el proyecto **Pasajes Accesibles CNRT** en PostHog US Cloud y usa `https://us.i.posthog.com` como host de ingesta. Cuando la persona acepta el consentimiento, las estadísticas se envían a PostHog y se procesan en su región de Estados Unidos. El token de captura no da acceso de lectura a los datos del proyecto.

Para pruebas o rotación, la aplicación admite reemplazar esos valores mediante:

- `PASAJES_ACCESIBLES_CNRT_POSTHOG_TOKEN`;
- `PASAJES_ACCESIBLES_CNRT_POSTHOG_HOST`.

La presencia del token no equivale a consentimiento: sin aceptación de la persona usuaria no se encola ni se envía telemetría. Nunca debe distribuirse una personal API key (`phx_...`) dentro del programa.

## Fallos de red

La telemetría se envía en un hilo daemon independiente. Si PostHog no responde o no hay Internet, el error se descarta y no interrumpe búsquedas, reservas, anulaciones ni el cierre del programa.


## Comprobación de actualizaciones

La versión ejecutable puede consultar periódicamente la API pública de GitHub Releases para saber si existe una versión nueva. Esta comprobación es independiente de PostHog y no envía nombre, DNI, CUD, correo, credenciales CNRT ni datos de reservas. Como en cualquier conexión HTTPS, GitHub puede recibir datos técnicos normales de red, incluida la dirección IP desde la que se realiza la consulta. La descarga solo se ejecuta después de que la persona acepta actualizar y el instalador se verifica mediante SHA-256 antes de abrirse.
