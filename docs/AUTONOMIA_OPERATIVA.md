# Revisión de autonomía operativa

## Actualización de entrega del 26 de noviembre de 2026

El circuito de Personal dispone de checklist por mes, accesos «Revisar» y
confirmación directa de publicación. Reconoce dos cierres de tráfico CAT, aplica
el general a Masivo/SMB y Personal Pay y el específico a Soporte. Los pendientes
de normalización se limitan a las proformas vigentes. La guía actual es
`guia_usuario.html` y el contrato de entrega está en `ENTREGA_DESARROLLO.md`.
La interfaz compartida incorpora búsqueda de pantallas y mejoras adaptables.
Las observaciones siguientes corresponden a la revisión histórica indicada.

Revisión del 28 de octubre de 2026. Objetivo: que el uso habitual se resuelva
desde la aplicación; el código se modifica cuando cambia el producto o una
regla de cálculo, y Tecnología administra su infraestructura.

## Resultado de la revisión

**El proyecto todavía no cumple completamente ese objetivo.** Tiene una base
funcional amplia, pero mezcla configuración de negocio, datos iniciales y
reglas específicas con lógica de aplicación. La revisión recorrió los modelos,
las 181 rutas del controlador principal, las pantallas Flask, los scripts
operativos, el frontend Next.js y los archivos de instalación/entrega.

La interfaz operativa actual es Flask. Next.js permanece en migración: no debe
considerarse una segunda fuente de datos ni un requisito para administrar las
pantallas actuales. Esta revisión no certifica todos los recorridos de todas
las pantallas: las pruebas ejecutadas se indican al final.

## Implementado en esta intervención

- **Centro de administración** en `/administracion`, accesible con el permiso
  de administrar usuarios. Reúne accesos a las tareas operativas y respeta los
  permisos de los módulos al mostrar accesos a Proyectados, Facturación y
  Directorio.
- **Año de apertura administrable** desde esa pantalla. Se guarda en la tabla
  `configuracion_operativa`; `APP_DEFAULT_YEAR` queda como valor inicial cuando
  todavía no existe una preferencia. Las vistas que usaban el año por defecto
  consultan el valor guardado. Los filtros explícitos conservan prioridad.
- **Historial, confirmación y concurrencia:** el cambio exige contraseña y CSRF,
  deja un movimiento en el historial y rechaza una edición basada en una
  versión anterior. Se consulta la preferencia por solicitud, sin depender de
  la memoria de un proceso del servidor.
- **Revisiones de configuración:** campañas activas sin modalidad de valor hora
  y meses proyectados sin fila de precio. Muestran cantidades y hasta 50 casos
  por categoría con enlace para revisarlos. Son avisos para revisar, no órdenes
  de corrección automática; un mes puede estar todavía en preparación.
- **Separación de responsabilidades:** la funcionalidad nueva vive en
  `administracion.py` y `operacion.py`, fuera del controlador de cálculos.
- **Entrega compatible:** el migrador permite una fuente anterior sin la nueva
  tabla de preferencias, creando esa tabla vacía en el destino. Las demás
  tablas del contrato siguen siendo obligatorias.

El cambio de año de apertura no copia proyecciones, no cambia fórmulas ni
precios, no cierra períodos y no altera `PLP_BASE_YEAR`. El nuevo año de
proyecciones se crea con el flujo que ya existe en su matriz.

## Matriz de tareas y responsables

| Tarea | Situación revisada | Resolución / responsable |
| --- | --- | --- |
| Crear cliente, campaña, subcampaña y asociación comercial | Alta y edición desde Datos Maestros. | Usuario con permiso; no requiere código. |
| Cambiar gerente/jefe y conservar meses anteriores | Edición con `vigencia_desde`, versiones de asignación. | Usuario desde Datos Maestros; revisar alcance antes de confirmar. |
| Definir segmento y grupo de Facturación horas | Campos en Datos Maestros. | Usuario. Evitar recurrir a scripts de reasignación para cambios nuevos. |
| Configurar valor hora variable/fijo | `Campania.valor_hora_variable`, pantalla y API existentes. | Usuario; nuevo centro señala modalidades pendientes. |
| Cargar/importar facturación | Pantalla de carga, validaciones e importación. | Usuario. Los formatos nuevos fuera del contrato requieren desarrollo. |
| Corregir facturación e historial | Control, justificaciones e historial existentes. | Usuario autorizado; no ejecutar SQL como procedimiento cotidiano. |
| Proyectar horas, dotaciones y jornadas | Matriz e importaciones con revisión. | Usuario; conservar las fórmulas actuales. |
| Crear año de proyecciones | `/api/matriz-proyecciones/nuevo-anio` y flujo de la matriz. | Usuario. Copia fotografía base, precios, variables y distribución; no copia feriados. |
| Elegir año de apertura | Antes dependía de `APP_DEFAULT_YEAR`. | Resuelto desde Centro de administración, con historial y confirmación. |
| Mantener precios e inflación | Matriz e importación existentes. | Usuario. Falta mejorar revisión del alcance y recuperación del guardado automático. |
| Feriados y calendario | Calendario operativo con altas y bajas. | Usuario. Revisar los feriados del nuevo año. |
| Variables, tarifación, Next Gen y cotizaciones | Pantallas, importaciones y edición masiva existentes. | Usuario; extender protección de borradores a formularios auxiliares. |
| Normalizar nombres Proyectados/Facturación | Vinculación en Datos Maestros, tabla e historial. | Usuario; mantener esta vía como fuente de correspondencias. |
| Alias ortográficos de gerentes y jefes | `config/name_aliases.json`, cargado al importar modelos. | Pendiente: gestión con vigencia/auditoría desde interfaz; hoy requiere actualización y reinicio. |
| Excepciones de cálculo disponibles | Tipos y porcentajes configurables en Datos Maestros. | Usuario para las opciones existentes; agregar un tipo de fórmula requiere desarrollo. |
| Reglas especiales de Personal/otras cuentas | Clasificación en `models.py`, `routes.py` y `personal_objetivos.py`. | Pendiente separar parámetros de fórmulas. Un cambio de fórmula siempre exige validación y paridad. |
| Usuarios, roles y permisos efectivos | Gestión en Usuarios; permisos personalizados existentes. | Usuario administrador. Cambiar la implementación de una autorización es desarrollo. |
| Indicadores, dotaciones e históricos operativos | Formularios e importación del libro operativo. | Usuario para los datos expuestos. Hay bases históricas que siguen en JSON. |
| Ratios, Share e históricos de comparación | Mezcla de tablas editables y JSON versionados en `app/data`. | Pendiente completar administración de series base, con origen, período y control de reemplazo. |
| Datos iniciales al consultar | Funciones `asegurar_*` insertan semillas durante GET. | Pendiente llevar a inicialización explícita y versionada; no debe reaparecer una fila eliminada deliberadamente. |
| Seguridad de sesiones y contraseña propia | Configuración de entorno y flujos de usuario existentes. | Usuario para contraseña; Tecnología para SECRET_KEY, HTTPS y duración/política corporativa. |
| Respaldos, restauración y migración de motor | Guía Docker y scripts de entrega. | Tecnología/DBA. No habilitar restauración de toda la base como una carga ordinaria. |
| Publicación de nuevas versiones | Docker/Git/registro corporativo. | Desarrollo/Infraestructura; el usuario operativo no necesita hacer push para cargar datos. |

## Dependencias que requieren trabajo adicional

### 1. Sustituir configuraciones de archivos por datos administrables

Los alias de responsables se leen una vez desde JSON. Las series históricas
de Directorio incluyen JSON con períodos y cuentas. Deben tener importación,
vista previa, validación, control de duplicados, trazabilidad y edición según
permisos antes de retirar los archivos como fuente habitual.

No conviene agregar un editor genérico de JSON o de fórmulas en pantalla:
trasladaría complejidad técnica al usuario. Cada parámetro necesita un nombre
de negocio, tipos/rangos permitidos y una explicación de su impacto.

### 2. Inicialización explícita y evolución de esquema

`ensure_schema` y las normalizaciones se ejecutan al arrancar la aplicación.
Algunas consultas llaman a `asegurar_*` y completan tablas con archivos de
referencia. Separar, en una siguiente migración, la instalación inicial de los
datos operativos y registrar qué versión de semillas fue aplicada. Los GET de
consulta deberían limitarse a leer.

La tabla nueva de preferencias se crea con `db.create_all`, igual que las
tablas actuales. Para la entrega empresarial, adoptar migraciones versionadas
ejecutadas una vez por despliegue, con respaldo previo y ensayo de restauración.
Esto es tarea técnica de actualización, no una tarea del usuario.

### 3. Vigencias y cierre de períodos

Ya existe vigencia para responsables. Extender un contrato equivalente a los
parámetros comerciales que puedan cambiar de mes a mes. Diseñar cierre y
reapertura de períodos con permiso específico y auditoría antes de impedir
ediciones históricas. Esta revisión no agregó cierres ni restricciones nuevas.

### 4. Corregir desde la interfaz, no desde scripts de mantenimiento

El repositorio contiene scripts para alinear maestros, normalizar nombres,
reasignar campañas y reprocesar importes. No deben convertirse en el modo
normal de trabajar. Distinguir reparaciones históricas irrepetibles de tareas
recurrentes. Para las recurrentes: vista previa de afectados, período de
vigencia, confirmación, ejecución transaccional e historial.

### 5. Separar módulos gradualmente

`routes.py` supera las 13.000 líneas y combina autenticación, importaciones,
maestros, cálculos, reportes y exportaciones. Evitar un reemplazo masivo:
extraer módulos conservando las URLs y probar paridad por dominio. Estructura
propuesta: autenticación/permisos, administración, maestros, facturación,
proyecciones/precios, Personal/importaciones, Directorio, auditoría/exportaciones.

Los cálculos deben permanecer en servicios con entradas y salidas verificables;
las pantallas editan parámetros admitidos, no código ejecutable.

## Orden de trabajo recomendado

### Continuidad con el paso de los años

El año operativo no debe exigir una modificación de código cada enero. En el
Centro de administración se puede elegir **año fijo** o **avance automático con
el año calendario**. El modo automático resuelve el año en cada solicitud y no
requiere reiniciar el servidor al cambiar de año. Utiliza el calendario del
servidor; Tecnología debe mantener su fecha y zona horaria correctamente.

Esto selecciona un período de trabajo, pero no crea ni reemplaza información.
El flujo anual sigue siendo explícito:

1. Revisar el último año y mes que se usarán como base.
2. Crear el año siguiente desde la matriz de Proyecciones. Si ya tiene datos,
   la creación se rechaza para evitar una sobrescritura.
3. Revisar dotaciones, precios, porcentajes y jornadas copiados. Los días se
   calculan para el calendario de destino, incluidos los años bisiestos.
4. Cargar/revisar los feriados propios del nuevo año; no se copian del anterior.
5. Completar las importaciones y configuraciones que correspondan al nuevo
   período. No tratar los meses sin registros como meses facturados en cero.
6. Conservar los años anteriores para consulta y comparación. Los cambios de
   responsables o reglas comerciales deben tener vigencia y trazabilidad.

Se probaron aperturas consecutivas **2027, 2028 y 2029**, la cantidad de días
laborables de febrero de 2028, la conservación de las fotografías anteriores,
la copia de precios/variables y el rechazo de aperturas repetidas o de destinos
que ya tienen precios, variables o distribución. Se comprobó además que abrir
2030 conserva y utiliza sus feriados previamente configurados. También se
simuló el avance del calendario a 2027, 2028 y 2035 sin reiniciar la aplicación,
manteniendo prioridad para un filtro explícito de un año anterior.

**Límite de alcance:** el modo automático no elimina las dependencias pendientes
de alias e históricos JSON ni convierte la plantilla base de Personal en una
plantilla anual versionada. Esas tareas siguen en el plan de estructura; antes
de declarar autonomía anual completa deben probarse sus importaciones para
cada formato y período, con reglas y versiones históricas conservadas.

### Prioridades restantes

1. **Hecho:** centro de tareas, año operativo y primeras revisiones.
2. **Siguiente:** revisión antes de guardar precios, errores y borradores en
   formularios auxiliares, administración de alias de responsables.
3. **Después:** series históricas administrables e inicialización versionada.
4. **Antes del uso empresarial definitivo:** migraciones versionadas, respaldo y
   restauración ensayados, vigencias, política de cierre y despliegue reproducible.

## Verificación y alcance

Las escrituras de prueba se realizan en bases aisladas. Se verifica acceso por
perfil, CSRF, contraseña, validación de año, conflicto entre versiones,
persistencia y lectura desde otra instancia, prioridad del filtro explícito,
historial y conservación de importes. En navegador se comprueban carga,
guardado, errores y adaptación a móvil. La prueba de arranque Docker existente
se mantiene como smoke en host; Docker Engine continúa ausente en esta PC.

El ZIP de entrega debe regenerarse después de esta intervención. El manifiesto
`base_actual_manifest.json` describe la fotografía de la entrega original; no
se reemplaza por un manifiesto de la base actual sin un nuevo traspaso acordado.
