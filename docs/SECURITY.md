# Seguridad del repositorio

Pasajes Accesibles CNRT está pensado para poder publicarse como repositorio público sin incluir credenciales personales de CNRT ni secretos administrativos de servicios externos.

## PostHog

La aplicación incluye un **Project token** de PostHog con prefijo `phc_`. Este token es de escritura/captura y PostHog lo considera público: permite asociar eventos al proyecto, pero no leer las estadísticas privadas ni administrar la cuenta.

Por ese motivo, ocultarlo u ofuscarlo dentro de una aplicación de escritorio no lo convertiría en un secreto real. Cualquier valor que la aplicación deba recuperar para enviar eventos puede terminar extrayéndose del código, memoria o tráfico de la propia aplicación.

No deben incorporarse al repositorio claves privadas o administrativas de PostHog, entre ellas claves reales con prefijos `phx_`, `phs_`, `pha_` o `phr_`.

Si en el futuro fuera necesario impedir que terceros fabriquen eventos usando el Project token público, la protección adecuada es interponer un servicio propio que valide los eventos, aplique límites de frecuencia y reenvíe solamente datos aceptados. No alcanza con cifrar u ofuscar un secreto estático dentro del cliente.

## Archivos locales

El archivo `.gitignore` excluye entornos virtuales, archivos `.env`, claves/certificados, logs, volcados, bases de datos y otros archivos locales que no deben publicarse.

Los datos persistentes de la aplicación se almacenan fuera del repositorio, bajo la carpeta de datos de usuario de Windows. Las credenciales que una persona elige recordar se protegen mediante DPAPI y no forman parte del código fuente.

## Antes de publicar

Antes de cada publicación pública conviene comprobar que:

- no haya archivos `.env`, certificados o claves privadas;
- no haya bases de datos, logs o volcados locales;
- no haya credenciales reales de CNRT;
- no haya claves privadas de PostHog;
- el Project token `phc_` sea el único identificador de PostHog incorporado intencionalmente al cliente.


## Actualizaciones

Los ejecutables oficiales deben publicarse exclusivamente mediante GitHub Releases. El actualizador solo acepta instaladores cuyo nombre coincida con la versión publicada y exige verificar SHA-256 usando el digest del asset de GitHub o el archivo `.sha256` adjunto. No se debe quitar esta verificación para facilitar una publicación.

La compilación oficial queda fijada al repositorio que GitHub Actions inyecta durante el build. Una variable de entorno no puede redirigir un ejecutable oficial a otro repositorio; el override por entorno solo se admite cuando se ejecuta el código fuente sin repositorio inyectado, para desarrollo local.
El workflow de publicación usa `persist-credentials: false` al descargar el repositorio para que las credenciales de GitHub no queden persistidas en la copia de trabajo durante la instalación de dependencias y el build. El token con permiso de publicación solo se expone explícitamente al paso final que crea el GitHub Release.

La verificación SHA-256 protege frente a descargas corruptas o sustituciones que no coincidan con el release consultado, pero no reemplaza una firma Authenticode de editor. Si el proyecto obtiene en el futuro un certificado de firma de código, conviene firmar tanto el ejecutable como el instalador antes de publicarlos.

