# Arquitectura técnica

## Principio general

La interfaz accesible y la sesión web están separadas. La persona utiliza controles de escritorio; Playwright mantiene una sesión real con CNRT en segundo plano.

## Módulos

- `app.py`: interfaz wxPython, foco, mensajes, confirmaciones y flujo de usuario.
- `worker.py`: hilo único para Playwright. Evita usar el navegador desde varios hilos.
- `client.py`: ingreso, localidades, escaneo, preparación/confirmación de reserva, perfil y solicitudes.
- `parsers.py`: analiza HTML devuelto por CNRT sin depender de posiciones visuales.
- `storage.py`: caché SQLite de localidades y almacenamiento opcional de credenciales con DPAPI.
- `models.py`: estructuras de datos del dominio.
- `updater.py`: consulta GitHub Releases, valida versión/asset, descarga el instalador y verifica SHA-256 antes de abrirlo.

## Flujo de escaneo

1. Se inicia sesión normalmente en `/web/ingresar`.
2. Se obtiene el enlace real de `Solicitar Pasaje` y los campos ocultos de sesión.
3. Para cada fecha se envía una búsqueda a `/web/buscarServicios` utilizando las mismas cookies de la sesión de navegador.
4. El HTML de respuesta se analiza por los bloques de servicio publicados por CNRT.
5. Los servicios que poseen `input[name='servicioARealizar_horario']` se consideran seleccionables. Si el usuario elige **Mostrar todos los servicios**, también se leen los bloques que CNRT marca como no disponibles, pero quedan con `available=False` y sin valor de radio para impedir su reserva.
6. Las consultas se ejecutan una por una con una pausa configurable, nunca en paralelo.

## Flujo de reserva

1. El usuario elige un resultado del escaneo.
2. Antes de continuar se repite la consulta para esa fecha.
3. Si el `radio_value` elegido ya no existe, la reserva se detiene.
4. Se abre el formulario oficial, se selecciona origen, destino, fecha y servicio.
5. Cuando la solicitud es por dos pasajes, se completan tipo y número de documento, apellido y nombre del acompañante antes de enviar el formulario de selección.
6. CNRT genera su pantalla oficial de confirmación. Para dos pasajes, la aplicación verifica además que los cuatro datos del acompañante hayan sido conservados por CNRT.
7. La aplicación presenta el resumen al usuario.
8. Solo una segunda confirmación explícita hace POST a `/web/confirmarReserva`.
9. El resultado se considera exitoso únicamente si la respuesta contiene `Solicitud Confirmada`.

## Datos sensibles

Los tokens y el identificador interno de beneficiario se leen de la sesión activa y nunca se persisten. Si se habilita recordar credenciales o acompañante, DPAPI cifra cada JSON y lo vincula al usuario de Windows. Credenciales y acompañante usan archivos separados.


## Flujo de Mis Solicitudes

1. Se abre el enlace real `/web/consultar/` publicado por la sesión.
2. `parsers.py` lee las columnas de `table#reservar` por sus encabezados, no por posición visual fija.
3. Cada reserva conserva en memoria únicamente los enlaces de acciones que CNRT genera para esa fila.
4. Modificar correo abre `/web/modificarEmail/<id>` y envía el formulario oficial, incluyendo su token CSRF.
5. Modificar preferencia abre `/web/editarPreferenciaViaje/<id>`, selecciona planta baja/alta y limita el motivo a 30 caracteres.
6. Anular usa el href oficial de esa reserva después de una confirmación humana explícita.
7. Después de una modificación o anulación se vuelve a consultar CNRT para verificar el resultado.
8. Los enlaces con token de sesión nunca se persisten en disco.

## Flujo de actualización

1. El ejecutable oficial conoce el repositorio desde `build_info.py`, que GitHub Actions genera durante la compilación.
2. Al iniciar, después del consentimiento de telemetría si corresponde, se agenda una comprobación en segundo plano.
3. La comprobación automática se hace como máximo una vez cada 24 horas. Si existe una versión nueva, se muestra un diálogo accesible; también puede iniciarse manualmente desde **Ayuda > Buscar actualizaciones...**.
4. La API pública de GitHub Releases se usa únicamente para localizar el último release estable y su instalador esperado.
5. La descarga se guarda primero como archivo parcial en `%APPDATA%\Pasajes Accesibles CNRT\updates`.
6. Antes de renombrar el archivo como instalador válido se comprueban tamaño y SHA-256. Si no coinciden, se descarta.
7. La instalación requiere una segunda acción explícita de la persona. El instalador se abre como proceso separado y la aplicación se cierra.
8. El instalador reemplaza los archivos del programa bajo `%LOCALAPPDATA%\Programs\Pasajes Accesibles CNRT`; los datos persistentes de `%APPDATA%` no se eliminan.

