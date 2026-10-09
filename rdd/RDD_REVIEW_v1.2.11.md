# Revisión RDD — activación real de PostHog

Versión revisada: **Pasajes Accesibles CNRT 1.2.11**

Cambio revisado: activación del project token público del proyecto de PostHog en **US Cloud**, manteniendo el consentimiento previo y el aislamiento entre telemetría técnica y reservas.

## Risk

Resultado: **PASS**.

- Se usa únicamente un **Project token** de captura (`phc_...`), no una Personal API Key.
- El host predeterminado de ingesta es `https://us.i.posthog.com`.
- La existencia del token no activa telemetría por sí sola: `TelemetryClient` debe estar habilitado mediante el consentimiento guardado.
- Se añadió una prueba que comprueba que, con `enabled=False`, ni los eventos técnicos ni los eventos de reservas llegan a `_enqueue`.
- El consentimiento informa explícitamente que los datos se envían a PostHog y se procesan en su región de Estados Unidos.
- Se mantienen las exclusiones de nombre, apellido, DNI, CUD, correo, teléfono, código de reserva y credenciales.
- Los eventos de reservas continúan separados del identificador aleatorio de instalación.

Riesgo residual aceptado: PostHog puede derivar ubicación aproximada de la conexión, ya informado en el consentimiento. Las variables de entorno permiten reemplazar token y host con fines de prueba o rotación; un entorno local alterado por terceros queda fuera del modelo de amenaza de esta capa.

## Readability

Resultado: **PASS**.

- La configuración se expresa mediante `DEFAULT_POSTHOG_PROJECT_TOKEN` y `DEFAULT_POSTHOG_HOST`.
- Las variables de entorno conservan nombres explícitos para sustitución controlada.
- No se añadió una nueva dependencia: el envío sigue aislado en `telemetry.py` usando `urllib` de la biblioteca estándar.
- README y `PRIVACIDAD.md` describen la configuración distribuida y la región de procesamiento.

## Reliability

Resultado: **PASS**.

Pruebas adversariales relevantes:

- Token presente + consentimiento desactivado: **0 eventos encolados**.
- Host predeterminado: **US Cloud correcto**.
- Project token distribuido: formato `phc_...`.
- La suite previa de ciclo de reservas permanece sin regresiones.

No se realizó una captura real hacia el proyecto de PostHog desde este entorno; la validación cubre configuración, construcción de payload, gating por consentimiento y rutas de envío.

## Resilience

Resultado: **PASS**.

- Si PostHog no responde, el error continúa atrapado dentro del hilo daemon de telemetría.
- Una falla de red no bloquea inicio, búsquedas, reservas, consultas ni anulaciones.
- Las variables de entorno permiten rotar el token o cambiar el host sin modificar el código.
- La aplicación sigue funcionando normalmente con telemetría desactivada por la persona usuaria.

## Evidencia final

- Pruebas unitarias: **49/49 PASS**.
- Compilación estática del paquete y pruebas: **PASS**.
- Auditor `wxpython-accessible-app-development` v1.2.3: **0 hallazgos**.
- Consentimiento previo al envío: **PASS**.
- Configuración PostHog US Cloud: **PASS**.

No se afirma validación runtime real con CNRT, NVDA/JAWS/Narrador ni recepción efectiva en el panel de PostHog desde este entorno.
