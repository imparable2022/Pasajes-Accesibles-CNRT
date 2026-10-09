**Pasajes Accesibles CNRT**

**Pasajes Accesibles CNRT** es un programa gratuito para Windows pensado para que las personas puedan sacar fácilmente sus pasajes correspondientes al cupo de discapacidad.

Desarrollé la aplicación con la idea de hacer que buscar y reservar los pasajes en el sistema web de la CNRT sea un proceso más rápido, sencillo y totalmente accesible por teclado, ratón y lector de pantalla.

**Como** Este es un proyecto independiente, no es una aplicación oficial, por lo que no está patrocinada o avalada por la Comisión Nacional de Regulación del Transporte (CNRT).

**¿Qué podés hacer con este programa?**

- **Ingresar fácilmente:** Iniciás sesión con tu DNI y      tu número de credencial (CUD, INCUCAI o pases municipales/provinciales).
- **Recordar credenciales (Opcional):** Si querés, podés hacer que      el programa recuerde tus datos de ingreso para no tener que escribirlos      cada vez que uses el programa.
- **Buscar sin complicaciones:** Escribís tu origen y      destino, y el programa te va a ir sugiriendo las localidades.

* **Búsquedas a tu medida:** Buscás pasajes para un día      específico, revisás un rango de varios días o escaneás todas las fechas      que la CNRT tenga habilitadas para el origen y destino que coloques.

- **Resultados útiles:** El programa solo te va a      mostrar los servicios que realmente tengan lugares disponibles.

* **Reservas seguras:** Antes de confirmar, el      programa vuelve a verificar en tiempo real que el asiento siga libre.

- **Personalizá tu viaje:** Elegís si preferís viajar      en planta baja o alta y especificá el motivo.

* **Gestioná tus pasajes:** En la sección "Mis      solicitudes" vas a poder leer todos los detalles de tus pasajes y      gestionarlos.

**¿Qué necesitás para usarlo?**

- Windows 10 o Windows 11 (versiones de 64      bits).

* Si lo necesitás, un lector      de pantalla como NVDA, Jaws, etc, y si no no te va a hacer falta porque      funciona muy bien usándolo con el ratón.

- Conexión a Internet.

**Cómo descargar e instalar**

Tenés dos opciones para usar el programa, y ambas te avisarán si hay alguna actualización para que siempre estés al día con las últimas funciones:



1. **Instalador (.exe):** Se instala en tu      computadora como cualquier programa tradicional.

2) **Versión Portátil (.zip):** Ideal si no querés instalar      nada. Solo descomprimís el archivo en una carpeta y abrís “pasajes_accesibles_cnrt.exe”

*Nota técnica: Ya sea que uses la versión instalable o portátil, tus configuraciones y credenciales se guardan en un lugar seguro de tu usuario de Windows (*%APPDATA%*). Esto significa que podés actualizar el programa sin miedo a perder tus datos.*

**Para programadores (Instalación desde el código fuente):**

Si preferís ejecutar el código directamente, necesitás Python (3.10, 3.11 o 3.12 de 64 bits).



1. Extraé los archivos.

2) Abrí el archivo instalar.bat (si no tenés Python, este      archivo va a intentar instalarlo por vos usando Winget, además de preparar      todo lo necesario).

3. Abrí ejecutar.bat para iniciar.

**Privacidad y Seguridad**

- **Tus datos están protegidos:** Si decidís activar la      opción "Recordar credenciales", tu documento y número de pase se      cifran con la máxima seguridad de Windows (DPAPI) y quedan atados      únicamente a tu usuario de la computadora.
- **Estadísticas opcionales y      anónimas:**      Para ayudarme a mejorar el programa, podés elegir enviarme estadísticas de      uso. Si lo activás desde el menú de Ayuda, solamente se van a enviar datos      técnicos (versión de Windows, qué lector de pantalla o ajuste de      accesibilidad usás), así puedo seguir mejorándolo poara que las personas tengan      o no una discapacidad puedan usarlo mejor..

**Cómo sacar un pasaje**

Para buscar y reservar un pasaje, primero ingresá tus datos de sesión (DNI y credencial), elegí si el programa va a recordar esos datos para que no tengas que ponerlos de nuevo cada vez y presioná ingresar.

Después seleccioná la localidad de **Origen** y **Destino** (podés escribir el nombre y usar las **flechas Arriba/Abajo** para seleccionar las opciones de la lista según lo que busques, confirmando con Enter).

Luego, elegí una de las **3 formas de búsqueda disponibles**:

**1. Buscar fecha específica (Alt + S): Te permite consultar un día puntual. Podés escribir la fecha en formato DD-MM-AAAA (ej. 15-10-2026) o usar los cuadros de día, mes y año. Dentro del cuadro de fecha, podés cambiar de día rápido con las flechas Arriba/Abajo.**

**2. Buscar rango de fechas (Alt + R): Podés elegir una fecha de inicio y una de fin para consultar varios días seguidos (ej. del 10-10-2026 al 15-10-2026).**

**3. Escanear todas las fechas disponibles (**Alt + E**):** Revisa de forma automática todas las fechas permitidas por la CNRT para el origen y destino que coloques.

Para iniciar la búsqueda presioná Alt + F. El programa solo te va a mostrar los servicios que tengan pasajes libres. Al terminar de buscar, el foco del teclado salta automáticamente a la lista de resultados.

Elegí tu asiento (planta baja o alta) y presioná el botón de envío para confirmar la reserva.

**Cómo gestionar "Mis solicitudes"**

Desde la sección **Mis solicitudes** podés revisar y administrar todos los pasajes que tengas pedidos o reservados. En esta pantalla podés hacer 3 cosas principales:

1. **Consultar tus reservas:** Podés leer todos los datos      de cada pasaje (origen, destino, empresa, fecha, horario, correo electrónico      asociado, cantidad de pasajes y el estado actual del trámite).

2) **Modificar tus datos:** Si la CNRT lo permite para      ese pasaje, podés cambiar tu dirección de correo electrónico de contacto o      tu preferencia de ubicación (planta baja / alta).

3. **Anular pasajes:** Si ya no vas a viajar,      podés cancelar la solicitud directamente desde la aplicación cuando el      sistema de CNRT tenga la opción disponible.

*Tips de accesibilidad e interacción:*



- Podés moverte de un control      a otro cómodamente usando la tecla **Tab y shift+tap, además de      los atajos de teclado**.

* Presioná **F6** en cualquier momento para saltar al cuadro de      "Estado" y escuchar con tu lector de pantalla los últimos      mensajes y novedades del programa.

**Detalles técnicos y límites**

El programa funciona interactuando directamente con la página web de la CNRT. Si en el futuro la CNRT cambia el diseño de su página, las rutas o los nombres de los botones, la aplicación se va a detener y te va a mostrar un mensaje de error claro en lugar de intentar hacer una reserva a ciegas con datos incorrectos.

**Licencia:** Este proyecto utiliza la Licencia no comercial PolyForm 1.0.0. Podés usar, modificar y compartir el código libremente, pero no está permitido su uso comercial o venta. Para más detalles, consultá el archivo LICENSE.txt.