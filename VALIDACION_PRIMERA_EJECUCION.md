# Validación de primera ejecución real

La primera prueba con una cuenta autorizada debería hacerse en este orden y sin confirmar una reserva hasta el final:

1. Iniciar sesión y verificar que aparece el menú principal.
2. Buscar una localidad conocida como origen y otra como destino.
3. Ejecutar un escaneo corto de 2 o 3 fechas.
4. Comparar los resultados con la web oficial para esas fechas.
5. Ejecutar el escaneo completo permitido.
6. Seleccionar un servicio disponible y pulsar `Preparar reserva`.
7. Verificar que el resumen oficial coincide con la selección.
8. Elegir `No reservar` durante las primeras pruebas.
9. Probar `Mi información` sin modificar valores; luego hacer una modificación controlada si corresponde.
10. Abrir `Mis solicitudes` y comprobar que una reserva activa muestra las mismas acciones que CNRT: modificar correo, modificar preferencia y anular; una reserva histórica no debe inventar acciones.
11. Probar una modificación controlada de correo o preferencia y comprobar que la aplicación la verifica contra CNRT.
12. Probar una anulación únicamente sobre una reserva que se haya creado expresamente para la prueba y comprobar el estado posterior.
13. Cuando todo lo anterior haya sido validado, hacer una reserva real autorizada y comprobar que la pantalla final dice `Solicitud Confirmada`.

Si CNRT cambia alguna estructura, copie el HTML de esa pantalla antes de modificar el código; la aplicación está diseñada para detenerse ante estructuras inesperadas.
