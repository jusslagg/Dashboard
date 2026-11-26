# Entrega técnica para Desarrollo y Base de Datos

Este documento define cómo conectar, crear o migrar la base del Dashboard de
Facturación sin cambiar los resultados que entrega la aplicación. El contrato
vigente está compuesto por los modelos SQLAlchemy, los DDL generados y el
manifiesto de datos incluidos en este repositorio.

## Acceso desde la aplicación

El documento se consulta dentro de la aplicación desde **Ayuda > Entrega a
Desarrollo** o mediante `/entrega-desarrollo`. Tanto la vista como las descargas
del documento y del manifiesto están habilitadas automáticamente para `Full` y
para usuarios con la autorización puntual
`permisos_personalizados.entrega_desarrollo = true`.

## Fuentes autoritativas

Actualización de entrega del 26 de noviembre de 2026. Las revisiones históricas
de UX y autonomía conservan sus fechas y se complementan con esta versión.

La copia de datos preparada para esta entrega es
`entregas/Base-Dashboard-2026-11-26.db`, con su archivo SHA-256. El manifiesto
`docs/base_actual_manifest.json` corresponde a esa copia consistente del origen,
tomada durante la preparación. Las cargas posteriores de la aplicación
pertenecen a una nueva línea base. Transferir la copia por el canal interno
acordado para datos operativos, junto con el manifiesto. El ZIP de código
se entrega por separado.

## Circuitos vigentes y aceptación funcional

### Personal y publicación

1. Seleccionar la configuración de seguimiento e importar la proforma del tipo
   Masivo, Personal Pay o Soporte como Proyectada o Definitiva.
2. La definitiva reemplaza el lote del mismo tipo y período. La proyectada
   posterior a una definitiva se rechaza.
3. Cargar la planificación PLP donde corresponda y guardar los cambios.
4. Para una definitiva, cargar el cierre del mismo mes. Se admiten dos archivos
   originales. El de Soporte se aplica a Soporte. El general separa Masivo
   (incluye SMB) y Personal Pay automáticamente.
5. Revisar las correspondencias nuevas en Aux y los responsables en Datos Maestros.
6. Elegir el mes en «Checklist de publicación», resolver sus pendientes mediante
   «Revisar» y usar «Confirmar y publicar en dashboard».

El importador nativo de cierres está en `app/cierre_trafico_cat.py`. Lee Resumen,
Resumen SMB y Resumen Pay según el libro, toma el mes del detalle con actividad,
aplica las distribuciones porcentuales de Horas Cuadro y conserva las horas a
liquidar y la penalidad por adhesión del resumen. Evita sumar los subtotales
junto con sus campañas. Un error de división en una jornada sin horas se trata
como cero únicamente cuando las horas brutas de esa jornada son cero.

El cierre puede llegar antes de la definitiva y quedar pendiente hasta su carga.
Una carga repetida reemplaza el cierre del mismo tipo y período. El cierre
general genera dos lotes internos con historial independiente.

La sincronización automática sigue operativa cuando el circuito está completo.
El botón del checklist permite confirmar y ejecutar la publicación desde el
mismo lugar. El backend vuelve a validar el mes al recibir la solicitud.
Objetivos negativos, PLP requerida ausente, cierres incompletos y asignaciones
necesarias ausentes impiden publicar. El filtro de Aux muestra pendientes de
proformas vigentes y omite los nombres heredados ajenos a ellas.

### Matriz, Resumen y criterio de totales

Matriz distingue Total facturado de facturación comparable. Total facturado usa
`total_dashboard`, incluyendo los conceptos independientes y el total manual
cuando corresponde. Cumplimiento y desvío comparable mantienen su base
operativa. Los importes se muestran con dos decimales.

La última pestaña es «Resumen por segmento Personal». Sólo incluye registros
de Personal con segmento asignado y sus indicadores se calculan sobre esa
selección. «Sin segmento» queda fuera de esa vista.

El reloj y el bloque operativo de Resumen usan horas facturadas divididas por
horas objetivo. La tabla operativa termina en «Cumplimiento de horas» y mantiene
los valores hora en pesos. Un porcentaje de valor hora debe identificarse como
tal donde exista.

### Usabilidad compartida

`layout.html` carga `usabilidad.css` y `usabilidad.js`. Incluyen búsqueda por
nombre o sección, estado vacío de búsqueda, apertura de la sección actual,
enlace para saltar al contenido, foco de teclado, adaptación de formularios de
archivo y aviso para tablas anchas. Las pestañas de Matriz admiten varias filas.

La prueba visual realizada cubrió Personal, Matriz, Dashboard y Datos Maestros
en 390 y 1366 píxeles. La comprobación visual de las demás pantallas y las pruebas
con usuarios en el entorno destino quedan como aceptación de Desarrollo.

### Pruebas del circuito

```powershell
python scripts/verificar_proforma_seguimiento.py
python scripts/verificar_cierre_trafico_personal.py
python scripts/verificar_dashboard_definitivas_personal.py
python scripts/verificar_resumen_horas.py
python scripts/verificar_matriz_segmentos.py
python scripts/verificar_handoff.py
```

Para aceptar la entrega, probar además un mes con definitiva y ambos cierres,
el reemplazo repetido del mismo lote, una campaña nueva sin correspondencia,
la confirmación del checklist y el deshacer del historial. Verificar que otros
grupos y meses mantengan sus datos y que los totales concilien con el origen.

| Elemento | Fuente |
| --- | --- |
| Modelo lógico y reglas de cálculo | `app/models.py` y `app/routes.py` |
| Esquema limpio PostgreSQL | `docs/esquema_base_datos_postgresql.sql` |
| Esquema limpio SQLite | `docs/esquema_base_datos_sqlite.sql` |
| Línea base del contenido actual | `docs/base_actual_manifest.json` |
| Alias configurables de nombres | `config/name_aliases.json` |
| Configuración de ambiente | `.env.example` |

Los DDL se generan desde `app/models.py`; no deben editarse manualmente. Después
de cambiar un modelo se ejecuta:

```powershell
python scripts/generar_esquema_base_datos.py
python scripts/verificar_handoff.py
```

## Configuración sin valores locales fijos

La aplicación selecciona la base exclusivamente mediante `DATABASE_URL`.
Direcciones, credenciales, año operativo y año base PLP se configuran por
ambiente:

```dotenv
APP_ENV=production
SECRET_KEY=<secreto persistente administrado por el ambiente>
DATABASE_URL=postgresql+psycopg://usuario:password@host:5432/facturacion
APP_DEFAULT_YEAR=2026
PLP_BASE_YEAR=2026
NAME_ALIASES_FILE=config/name_aliases.json
CORS_ORIGINS=https://dominio-del-frontend
SESSION_COOKIE_SECURE=1
```

`APP_DEFAULT_YEAR` define la selección inicial y no limita los años almacenados.
`PLP_BASE_YEAR` identifica la hoja anual del libro histórico de Personal; las
proformas nuevas pueden pertenecer a períodos posteriores. Ninguna ruta local,
IP de WiFi o archivo del usuario forma parte del código de producción.

Las jefaturas, segmentos, gerencias, campañas y vigencias operativas provienen
de `asignaciones_comerciales`, administrada desde **Datos Maestros**. El archivo
`config/name_aliases.json` sólo normaliza variantes de escritura; no asigna la
jefatura de una campaña. Si una campaña nueva no tiene asignación, el circuito
de Personal informa el faltante y no inventa un responsable.

## Filtros de interfaz

El diseño de filtros es compartido por toda la aplicación. La plantilla
`app/templates/layout.html` carga `app/static/ui-filters.css` y
`app/static/ui-filters.js`. El script reconoce controles de búsqueda, período
y filtros de negocio, incluidos los que se crean después de una llamada a la
API. Los filtros de opciones abren una ventana centrada con fondo atenuado, búsqueda,
opciones marcables, limpieza, cancelación y aplicación explícita. Los filtros
múltiples conservan la selección previa hasta pulsar «Aplicar filtro» y
disparan una sola actualización; los selectores de valor único mantienen esa
restricción. El control original conserva su valor y su evento `change` para
que las consultas existentes sigan funcionando. Los formularios de carga y
edición no se modifican.

Para un filtro nuevo se debe usar un identificador semántico (`filtro...`,
`buscar...`) o el atributo `data-filter-control`. Cuando una sección contiene
varios controles con nombres heredados, se marca con `data-filter-scope`. Una
barra completa puede marcarse con `data-filter-bar`; los botones segmentados usan
`app-filter-tabs`, `app-filter-tab` y `active`. No se deben copiar estilos de
altura, borde o color dentro de cada plantilla.

## Esquema y compatibilidad

Una base nueva contiene 28 tablas. `facturacion_anio` es multianual; el nombre
Python `Facturacion2026` se conserva únicamente como alias de compatibilidad y
apunta al mismo modelo, no a otra tabla.

La SQLite operativa puede conservar artefactos históricos que la aplicación ya
no consulta: la tabla vacía `bajas_operativas` y algunas columnas antiguas. El
migrador omite esos artefactos. Si `bajas_operativas` tuviera filas, la auditoría
la reportaría como tabla extra y la migración debe detenerse para revisión.

Los importes usan `NUMERIC`, no `FLOAT`, con la precisión declarada en los DDL.
Las fórmulas se calculan en Python a partir de columnas persistidas; no existen
triggers ni columnas calculadas ocultas que deban recrearse en PostgreSQL.

## Datos que deben migrarse

Se copian las 28 tablas declaradas, incluidos:

- usuarios y hashes de contraseña;
- catálogos, asignaciones y vigencias;
- facturación y justificaciones;
- proyecciones, jornadas, precios, variables y tarifaciones;
- feriados y distribución PLP;
- proformas e importaciones de seguimiento, incluidos sus BLOB de Excel;
- historial de cambios y normalizaciones de nombres;
- tablas de Directorio, dotaciones e indicadores.

Los IDs se preservan porque existen claves foráneas e historial que los
referencian. El migrador actualiza las secuencias de PostgreSQL al máximo ID
copiado.

## Migración recomendada

1. Detener escrituras en la aplicación de origen.
2. Crear un backup consistente de SQLite.
3. Crear una base PostgreSQL vacía con codificación UTF-8.
4. Configurar una cuenta temporal con permisos de creación y carga.
5. Ejecutar el migrador desde el repositorio:

```powershell
python scripts/migrar_base_datos.py `
  --source-url "sqlite:///C:/ruta/instance/facturacion.db" `
  --target-url "postgresql+psycopg://usuario:password@host:5432/facturacion"
```

El destino debe estar vacío. El script no borra ni mezcla datos existentes. La
copia se ejecuta en transacción, conserva IDs, reinicia secuencias y termina con
una comparación de esquema, cantidad de filas y SHA-256 de cada tabla.

Para crear solamente el esquema, un DBA puede ejecutar
`docs/esquema_base_datos_postgresql.sql` y luego usar el mismo migrador sobre las
tablas vacías.

## Verificación de paridad

La línea base actual se regenera únicamente cuando una actualización operativa
autorizada cambia la fuente:

```powershell
python scripts/verificar_paridad_bases.py `
  --write-manifest docs/base_actual_manifest.json
```

Para comparar directamente SQLite y PostgreSQL:

```powershell
python scripts/verificar_paridad_bases.py `
  --source-url "sqlite:///C:/ruta/instance/facturacion.db" `
  --target-url "postgresql+psycopg://usuario:password@host:5432/facturacion"
```

Para comprobar una copia de SQLite contra el manifiesto entregado:

```powershell
python scripts/verificar_paridad_bases.py `
  --source-url "sqlite:///C:/ruta/instance/facturacion.db" `
  --manifest docs/base_actual_manifest.json
```

El comparador normaliza fechas, booleanos, Unicode y escalas `NUMERIC`; los BLOB
se comparan por tamaño y SHA-256. Nunca imprime la contraseña contenida en una
URL de conexión.

## Validación funcional posterior

Con `DATABASE_URL` apuntando al destino:

```powershell
python scripts/verificar_entrega.py
python scripts/verificar_handoff.py
python scripts/verificar_matriz_segmentos.py
python scripts/verificar_proforma_seguimiento.py
python scripts/verificar_feriados_facturacion.py
python scripts/verificar_resumen_horas.py
```

Si se recibe una nueva versión del libro operativo, se concilia contra la
solapa anual con este comando. Sin `--apply` funciona como auditoría y debe
informar `filas_actualizadas: 0` después de una carga correcta:

```powershell
python scripts/reprocesar_facturacion_2026.py "RUTA_EXCEL" --year 2026 --apply
python scripts/reprocesar_facturacion_2026.py "RUTA_EXCEL" --year 2026
```

La asociación usa mes, cliente, servicio y tipo de jornada; no depende de que
las horas continúen iguales. Cada aplicación registra el nombre y SHA-256 del
archivo en `historial_cambios`. Las cargas creadas solo en la app se conservan
si no existe una fila equivalente en el archivo.

Luego se valida en navegador:

1. login y permisos;
2. Datos Maestros y edición de jefatura/segmento;
3. Resumen por segmento, Resumen por jefatura y Servicios por jefatura;
4. carga de una proforma en simulación y publicación;
5. feriado, jornadas laborales y facturación;
6. edición de Next Gen;
7. historial y deshacer;
8. exportaciones de Directorio y Proyectados.

## Reglas que deben conservarse

- `asignaciones_comerciales` gobierna jefe, gerente, segmento y vigencia.
- El bono de Personal es adicional realizado y no integra el objetivo teórico.
- Una carga manual con `importe_fijo` y sin `control_objetivo_total` usa ese
  monto como objetivo monetario de horas; las horas objetivo y facturadas siguen
  controlándose por separado. Un objetivo explícito de una importación conserva
  el valor de origen. Bonos y penalizaciones mantienen su efecto en el desvío.
- Las horas planificadas PLP son manuales y se distribuyen en Objetivo Masivo.
- Los feriados activos recalculan jornadas y horas proyectadas.
- Una carga mensual PLP reemplaza el mes completo dentro de su alcance.
- Los importes monetarios se redondean con `ROUND_HALF_UP` a dos decimales.
- La Matriz replica el bloque de valor hora del Excel sobre importes agregados:
  `VH Objetivo = Total Obj / Horas Objetivo`,
  `VH Realizado = Total Real / Horas Realizadas` y
  `% Valor hora = VH Realizado / VH Objetivo`. `Total Obj` incluye horas y
  variable objetivo; `Total Real` incluye horas, variable productivo, bonos y
  penalizaciones. Tarifación, Next Gen y otros no integran estos cálculos.
- `facturacion_anio.otros` conserva el signo informado: los valores positivos
  aumentan el Total Facturado y los negativos lo reducen. Las justificaciones
  de tipo `otros` deben conservar el mismo signo y no modifican el Total Real
  comparable utilizado para valor hora y cumplimiento.
- Las normalizaciones de Proyectados no alteran nombres ni importes de origen.
- Next Gen conserva la cotización aplicada por producto y mes.

## Despliegue

En producción se usa una sola instancia lógica detrás del proxy o balanceador,
una `SECRET_KEY` persistente y HTTPS. Las migraciones o normalizaciones no deben
ejecutarse desde dos procesos simultáneamente. Antes del primer arranque sobre
PostgreSQL se aplica el DDL o el migrador; después se inicia la aplicación con
una cuenta de ejecución con los permisos mínimos necesarios.

No se versionan `.env`, logs, bases temporales ni credenciales. Los respaldos de
datos reales deben almacenarse en el repositorio de backups definido por el área
responsable y no dentro del repositorio de código.

## Criterio de aceptación

Controles ejecutados al preparar esta entrega el 26 de noviembre de 2026

| Control | Resultado |
| --- | --- |
| Entrega, rutas, seguridad y DDL SQLite | OK |
| Importación, reemplazo y deshacer de proformas | OK |
| Cierres de tráfico y publicación de definitivas | OK |
| Resumen de horas sobre la copia de entrega | OK |
| Matriz por segmento y jefatura | OK |
| Handoff de esquema de 28 tablas | OK |
| Paridad de la copia contra el manifiesto | OK |
| Build y ejecución con Docker Engine | Pendiente en el entorno destino |
| Paridad contra PostgreSQL destino | Pendiente tras la migración |

El manifiesto certifica el contenido de la copia preparada. La paridad contra
PostgreSQL se verifica después de migrar con `--target-url`. Las pruebas con
usuarios y la revisión visual de todas las pantallas se completan en la
aceptación del destino.

- `verificar_handoff.py` finaliza con `HANDOFF OK`.
- `verificar_paridad_bases.py` finaliza con `PARIDAD OK`.
- No faltan tablas, columnas, índices o claves foráneas.
- Todas las tablas tienen la misma cantidad de filas y huella SHA-256.
- Los seis controles funcionales anteriores finalizan sin errores.
- La aplicación inicia con `APP_ENV=production` y una clave persistente.
- Desarrollo conserva el manifiesto y el backup de origen hasta la aceptación.
