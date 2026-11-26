# Revisión de Facturación y Proyectados

## Actualización del 26 de noviembre de 2026

La interfaz compartida incorpora búsqueda de pantallas, sección actual marcada
y abierta, formularios de archivo adaptables, filtros más legibles, foco visible
y avisos de desplazamiento en tablas. Personal ofrece checklist por mes,
pendientes específicos y confirmación de publicación desde ese bloque.
La última pestaña de Matriz se llama «Resumen por segmento Personal» y excluye
los registros sin segmento.

Se comprobaron Personal, Matriz, Dashboard y Datos Maestros en 390 y 1366 píxeles.
La revisión visual de las demás pantallas y la aceptación con usuarios en el
destino siguen pendientes. Las secciones siguientes conservan la revisión
histórica y sus propuestas.

Revisión del 27 de octubre de 2026 sobre las vistas Flask. Se conservaron las fórmulas y las reglas de negocio. Las pruebas de escritura se realizan sobre una copia de la base local.

## Mejoras implementadas en esta pasada

**Alcance final:** la apertura interactiva cliente → campañas → mensual queda exclusivamente en el cuadro **Alertas** (antes llamado Clientes en riesgo). Las otras alertas son informativas y las tarjetas adicionales de desvíos se retiraron del dashboard para evitar duplicaciones.

Actualización del 28 de octubre: el cuadro **Alertas de la selección** sigue el recorrido **cliente → campañas → mensual**. Primero muestra el acumulado por cliente del período filtrado. Tocar un cliente despliega todas sus campañas, incluidas las positivas que compensan a las negativas, para conciliar con el total del cliente. Presionar una campaña abre un cuadro con todos sus meses, desvíos positivos/negativos y total del período; se cierra con clic afuera, Escape o Volver al acumulado, conservando el cliente desplegado. El cumplimiento acumulado se calcula desde los totales, sin promediar porcentajes mensuales. La apertura se consulta al abrirla, respeta filtros y permisos e incluye búsqueda y paginación. Mantiene las reglas previas de alertas (`Total Real − Total Teórico`), que pueden diferir del desvío comparable del indicador principal; la apertura lo explica para no mezclar ambos controles.

| Vista | Problema observado | Resultado |
| --- | --- | --- |
| Facturación → Control | Se dibujaban todos los registros de la consulta en una tabla de 27 columnas. | Paginación de 25, 50 o 100 registros; encabezados fijos y estado de consulta visible. Excel conserva el conjunto completo de registros filtrados. |
| Facturación → Control | Cerrar la edición descartaba lo ingresado sin avisar; un fallo de red podía dejar el formulario sin respuesta. | Aviso antes de descartar cambios, diálogo accesible, error dentro del formulario y bloqueo de envíos repetidos mientras se guarda. |
| Facturación → Control | El registro completo se insertaba como JSON en un atributo de botón delimitado por comillas simples. Un nombre con apóstrofos podía romper el botón. | Los botones usan el ID para recuperar el registro; los textos de la tabla se escapan al construir el HTML. |
| Proyectados → Variable | Cambiar de año vaciaba las ediciones pendientes de Next Gen antes de saber si la nueva consulta funcionaba. | Confirmación antes de cambiar de año; se descartan los cambios aceptados solo después de recibir todas las respuestas válidas. Un error conserva el año y los datos anteriores. |
| Proyectados → Variable | Variables, Tarifación y Next Gen se consultaban en serie, sin comprobar todas las respuestas. | Consultas independientes en paralelo; se actualizan juntas cuando todas responden correctamente. Las respuestas atrasadas no sustituyen el año más reciente. |
| Proyectados → Tarifación | Al reconstruir la tabla se mostraban los importes guardados, ignorando los pendientes en memoria. | Los importes pendientes siguen visibles al filtrar, alternar vistas o actualizar el mismo año. |
| Proyectados → Next Gen y Tarifación | Un fallo de guardado masivo podía dejar botones bloqueados o permitir editar mientras se enviaba una versión anterior. | Estado de guardado, protección de la edición durante el envío y recuperación de botones conservando los cambios ante errores. |
| Proyectados → Next Gen y Tarifación | Los mensajes se escribían dentro del panel de porcentajes, oculto al usar otras vistas. | Mensaje común visible desde todas las vistas; las consultas y los guardados afectados tienen tiempo de espera para recuperar la interacción si no llega respuesta. |
| Acceso a Proyectados | Varias API de Precios, Facturación horas, Tarifación, Next Gen y distribución de Personal se clasificaban como Facturación. | Las API se clasifican como Proyectados, igual que sus pantallas. Se mantienen los controles de edición: el acceso de lectura no permite guardar. |
| Acceso a Facturación → Resumen | El prefijo `/resumen` de Proyectados también capturaba `/resumen-horas`. | Se distingue la página exacta de Proyectados del Resumen de Facturación y se verifica la separación con perfiles limitados. |

## Próximas prioridades

La revisión transversal sobre tareas que deben resolverse desde la interfaz está en [Autonomía operativa](AUTONOMIA_OPERATIVA.md). Incluye el Centro de administración, el año de apertura administrable y las dependencias pendientes de archivos y scripts.

Estas observaciones requieren una siguiente intervención; no se consideran resueltas por esta pasada.

1. **Precios: revisión del alcance antes de guardar.** La matriz guarda al salir de una celda y replica el nuevo precio hacia los meses siguientes. Conviene incorporar una revisión similar a Proyecciones, con los meses afectados y la opción de volver a editar. También conviene conservar el valor propuesto si falla el envío; actualmente se restaura el anterior.
2. **Facturación horas y Control proyecciones: estado y recuperación de consultas.** Los cargadores necesitan control de respuestas atrasadas y errores de red para evitar estados de carga persistentes o datos de un año anterior bajo una selección nueva.
3. **Formularios auxiliares de Variable.** Extender el seguimiento de cambios a los formularios individuales de porcentaje, producto y tarifación. Esta pasada protege las ediciones masivas en grilla.
4. **Rendimiento del servidor.** La paginación incorporada en Control reduce el trabajo del navegador, pero la API continúa devolviendo la consulta completa. Medir tiempos y volumen antes de diseñar paginación desde el servidor y exportación independiente.
5. **Continuidad del contexto.** Evaluar una navegación entre Proyecciones, Precios, Facturación horas y Control que mantenga explícitos año, cliente y campaña, respetando las diferencias entre filtros de cada vista.

## Criterios de aceptación

- Las vistas muestran claramente si la consulta está cargando, actualizada o fallida.
- Las ediciones pendientes se conservan al alternar vistas o actualizar el mismo año.
- Cancelar un cambio de año o el cierre de una edición conserva lo ingresado.
- Un error de guardado deja disponible el reintento y mantiene los valores propuestos.
- Las fórmulas, permisos, confirmación con contraseña y contenido de las solicitudes de guardado se mantienen.
- Los cambios visuales y de navegación funcionan en escritorio y móvil.


### Ranking de Alertas

La apertura Alertas y la tarjeta Desvío negativo usan `resumen_dashboard`, la misma función del KPI Desvío. Comparan facturado por horas + variable productivo + bonos/penalizaciones contra el objetivo comparable, excluyendo Next Gen de ese desvío. Ordenan clientes de mayor pérdida a menor, con compensaciones positivas al final. Conservan la apertura cliente → campañas → meses, ocultan acumulados que se muestran como $0,00 y mantienen los cálculos de facturación. La verificación contrasta el KPI, la alerta y las sumas por cliente, campaña y mes con filtros anuales y mensuales.
