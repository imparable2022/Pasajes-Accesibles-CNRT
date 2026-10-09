# Revisión RDD — seguimiento anónimo de estados de reservas

Versión revisada: **Pasajes Accesibles CNRT 1.2.10**

## Candidato congelado

Se congeló el candidato previo a la revisión y se comparó contra v1.2.9. El diff de cambio fue de 337 líneas y el módulo nuevo `reservation_tracking.py` quedó por debajo del límite de 400 líneas.

SHA-256 del candidato congelado principal:

- `reservation_tracking.py`: `f8c53fc088be3ed2ad42bb61b9a2469cdd6c86d5aff848273517e166af856ee9`
- `telemetry.py`: `8e5cd9f3ac3cb3020b32391aba4cddf05a6993a939e530c9748fee3b0e1d0977`
- `app.py`: `fd6321dfb04a46ddfc84fc2155d171294fb12fc3d556b668ac608ab4410bdbc4`

## Risk

Se intentó romper el aislamiento entre estadísticas técnicas y reservas.

Resultado: **PASS**.

- El UUID de instalación no se incluye en eventos de reservas.
- El código/identificador real de CNRT no se envía a PostHog.
- El archivo local de seguimiento no guarda en claro código de reserva, empresa, origen ni destino; conserva hashes opacos, UUID anónimo y estados.
- Estados desconocidos se normalizan a `other`; su texto libre no se envía.
- `Pasaje Emitido` no se interpreta como viaje realizado.
- El consentimiento único informa que se envían empresa, origen, destino, fecha y estado observado.

Riesgo residual aceptado: el servicio estadístico puede derivar ubicación aproximada de la conexión, tal como informa el consentimiento. El seguimiento de estados solo ocurre con consentimiento y configuración activa.

## Readability

Resultado: **PASS**.

- El ciclo de reservas se aisló en `reservation_tracking.py`.
- Estados y nombres de eventos usan constantes explícitas.
- La integración de interfaz se limita a tres puntos: reserva confirmada, consulta de Mis solicitudes y anulación verificada.
- El módulo corregido tiene 280 líneas.

Hallazgo no bloqueante: queda un `import uuid` sin uso en `telemetry.py`, heredado de la implementación anterior. No afecta comportamiento ni privacidad y no justificó una segunda corrección después de congelar el candidato.

## Reliability

Resultado inicial: **FINDING**, luego **PASS tras una única corrección acotada**.

Caso reproducido sobre el candidato congelado:

`Activa → Pasaje Emitido → Activa`

El candidato original volvía a emitir `reservation_active` al regresar a un estado ya observado, lo que podía inflar conteos brutos.

Corrección acotada aplicada: cada reserva conserva `seen_states`; cada estado normalizado se emite como máximo una vez durante el ciclo local de esa reserva. Se añadió una prueba de regresión que exige que el segundo `Activa` no genere evento.

Después de la corrección:

- reserva creada: `reservation_created`;
- Activa: `reservation_active`, máximo una vez por reserva;
- Pasaje Emitido: `reservation_ticket_issued`, máximo una vez por reserva;
- anulación/cancelación verificada: `reservation_cancelled`, máximo una vez por reserva;
- estado desconocido: `reservation_status_other`, máximo una vez por reserva.

También se probó que dos reservas idénticas puedan mantener IDs anónimos separados, incluso en filas históricas sin identificador CNRT visible, usando el ordinal de ocurrencia dentro de la tabla.

## Resilience

Resultado: **PASS**.

- Un archivo local de seguimiento corrupto no impide abrir ni usar la aplicación; el módulo vuelve a un estado vacío y se recupera en la siguiente escritura.
- Los fallos de escritura local se descartan y nunca bloquean una reserva.
- Los fallos de PostHog continúan aislados en el hilo de telemetría.
- La telemetría permanece inactiva sin project token o sin consentimiento.
- Repetir el mismo estado no genera eventos duplicados.
- Una anulación verificada que luego desaparece de Mis solicitudes ya queda contabilizada por el evento de anulación.

Limitación conocida: los estados posteriores a una reserva solo se conocen cuando la aplicación vuelve a consultar **Mis solicitudes** o verifica una anulación. Por tanto, las cifras de `Pasaje Emitido` representan estados observados por la aplicación, no un registro exhaustivo de cambios ocurridos mientras el programa estuvo cerrado.

## Evidencia final

- Pruebas unitarias: **47/47 PASS**.
- Compilación estática de paquete y pruebas: **PASS**.
- Auditor `wxpython-accessible-app-development` v1.2.3: **0 hallazgos**.
- Reproducción adversarial posterior a la corrección: `Activa → Pasaje Emitido → Activa` emite `active`, `ticket_issued`, y luego **ningún evento duplicado**.

SHA-256 posterior a la corrección:

- `reservation_tracking.py`: `30bb9ef85fdff071acfb716988c6fac199785b2f8421bf43e5995f3e541ee0cc`
- `telemetry.py`: `8e5cd9f3ac3cb3020b32391aba4cddf05a6993a939e530c9748fee3b0e1d0977`
- `app.py`: `fd6321dfb04a46ddfc84fc2155d171294fb12fc3d556b668ac608ab4410bdbc4`
- `test_reservation_tracking.py`: `93effca84e2cb1823170d5485faa99092833245ef347f20ab67cf9c60a769b0c`

No se afirma validación runtime real con CNRT ni con NVDA/JAWS/Narrador desde este entorno.
