# Dashboard de Facturación

Aplicación web para controlar facturación, proyecciones, precios, dotaciones, horas operativas y desvíos comerciales. El sistema combina un backend Flask con base SQLite/PostgreSQL y una experiencia web pensada para uso interno de finanzas, operaciones y control de gestión.

La herramienta centraliza datos reales y proyectados para responder, de forma rápida, preguntas como:

- cuánto se facturó y cuánto se esperaba facturar;
- dónde están los desvíos por cliente, campaña, site o tipo de negocio;
- qué horas, precios, dotaciones, feriados, variables o penalizaciones explican el resultado;
- qué cambios se hicieron y cómo deshacerlos desde el historial.

## Estado del proyecto

El proyecto tiene dos frentes:

- **Flask**: backend principal, autenticación, base de datos, APIs y pantallas operativas.
- **Next.js**: frontend en migración progresiva para algunas vistas modernas.

En el uso actual, la mayor parte de las funcionalidades operativas se trabajan desde Flask.

## Estructura

```text
Dashboard/
├─ app/
│  ├─ __init__.py              # Configuración Flask, seguridad, CORS, CSRF y migraciones simples
│  ├─ models.py                # Modelos SQLAlchemy y reglas de cálculo
│  ├─ routes.py                # Rutas HTML, APIs, importaciones, historial y exportaciones
│  └─ templates/               # Pantallas Flask
├─ instance/
│  └─ facturacion.db           # Base SQLite local por defecto
├─ next-app/                   # Frontend Next.js en migración
├─ scripts/
│  └─ dev.mjs                  # Levanta Flask + Next en desarrollo
├─ run.py                      # Entrada Flask
├─ requirements.txt            # Dependencias Python
├─ package.json                # Scripts npm del proyecto
├─ .env.example                # Variables de entorno sugeridas
└─ README.md
```

## Requisitos

- Python 3.8 o superior.
- pip.
- Node.js con npm, si se quiere levantar también Next.js.
- Navegador moderno.

En Windows, si `npm` no aparece en PowerShell, revisar que exista:

```text
C:\Program Files\nodejs\npm.cmd
```

## Instalación local

Crear y activar entorno virtual:

```powershell
python -m venv venv
venv\Scripts\activate
```

Instalar dependencias Python:

```powershell
pip install -r requirements.txt
```

Instalar dependencias del frontend Next.js:

```powershell
npm --prefix next-app install
```

Crear `.env` desde el ejemplo si hace falta:

```powershell
copy .env.example .env
```

## Cómo levantar el proyecto

### Opción recomendada: todo junto

Desde la carpeta raíz del proyecto:

```powershell
npm run dev
```

Esto levanta:

- Flask/API en `http://127.0.0.1:8009`
- Next.js en `http://127.0.0.1:3000`

Si PowerShell no encuentra `npm`, se puede usar:

```powershell
.\dev.ps1
```

### Solo Flask

```powershell
python run.py
```

Por defecto Flask levanta en:

```text
http://127.0.0.1:8009
```

Para usar otro puerto, por ejemplo `8010`:

```powershell
$env:PORT="8010"
python run.py
```

### Solo Next.js

```powershell
npm run next:dev
```

### Scripts disponibles

```powershell
npm run dev        # Flask + Next.js
npm run flask:dev  # Solo Flask
npm run next:dev   # Solo Next.js
npm run start      # Alias de npm run dev
```

## Variables de entorno principales

```text
SECRET_KEY=clave-secreta-local
DATABASE_URL=sqlite:///facturacion.db
CORS_ORIGINS=http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:8009,http://localhost:8009
FLASK_HOST=127.0.0.1
PORT=8009
FLASK_DEBUG=0
FLASK_RELOAD=0
TEMPLATES_AUTO_RELOAD=0
SESSION_COOKIE_SECURE=0
SESSION_MINUTES=60
MAX_CONTENT_LENGTH=10485760
```

Para PostgreSQL:

```text
DATABASE_URL=postgresql+psycopg://usuario:password@host:5432/facturacion
```

## Usuarios y permisos

El sistema tiene autenticación propia y roles definidos en base de datos.

Roles principales:

- **superusuario**: acceso amplio de administración.
- **administrador**: administra usuarios, historial y acciones sensibles.
- **editor**: puede cargar, editar y gestionar datos operativos.
- **lector**: consulta información sin modificar datos.

Acciones sensibles como edición, eliminación o deshacer cambios requieren sesión activa, token CSRF y permisos suficientes.

## Base de datos, tablas y datos necesarios

La aplicación usa SQLAlchemy. En SQLite o PostgreSQL estos datos viven como **tablas**. Si más adelante se migra a una base documental, se pueden pensar como **colecciones** con la misma responsabilidad funcional.

Al iniciar, Flask crea las tablas que falten y aplica algunos ajustes simples de esquema. Aun así, para que la herramienta tenga información útil, hay datos mínimos que conviene cargar en cada módulo.

### Resumen de tablas/colecciones

| Tabla / colección | Modelo | Para qué sirve |
| --- | --- | --- |
| `usuarios` | `Usuario` | Guarda usuarios, roles, estado activo y hash de contraseña. |
| `historial_cambios` | `HistorialCambio` | Registra cambios, snapshots anteriores/posteriores y permite deshacer operaciones soportadas. |
| `facturacion_2026` | `Facturacion2026` | Guarda la facturación real cargada: horas, importes, bonos, penalizaciones, variables y datos comerciales. |
| `justificaciones_ajustes` | `JustificacionAjuste` | Guarda explicaciones o ajustes asociados a un registro de facturación. |
| `asignaciones_comerciales` | `AsignacionComercial` | Catálogo maestro de cliente, gerente, jefe de site, campaña, subcampaña y tipo de negocio. |
| `matriz_proyecciones` | `ProyeccionMatriz` | Guarda la planificación mensual por cliente/campaña: dotación, carga horaria, días objetivo, horas requeridas y cumplimiento. |
| `matriz_proyecciones_jornadas` | `ProyeccionMatrizJornada` | Guarda aperturas de jornadas dentro de una proyección cuando una campaña necesita más de una configuración horaria. |
| `matriz_precios` | `ProyeccionPrecio` | Guarda precios mensuales por cliente/campaña, alcance, precio final e importe fijo mensual. |
| `variables_campanias` | `VariableCampania` | Guarda el porcentaje variable mensual por cliente/campaña. |
| `feriados_operativos` | `FeriadoOperativo` | Guarda feriados o días no operativos que afectan los días objetivo de las proyecciones. |

### Datos mínimos para iniciar

Para una base nueva, el orden recomendado de carga es:

1. `usuarios`: crear al menos un usuario `administrador`.
2. `asignaciones_comerciales`: cargar el maestro comercial base.
3. `facturacion_2026`: cargar registros reales si se quiere usar Dashboard, Control, Matriz, Comparativo y Justificaciones.
4. `feriados_operativos`: cargar feriados si las proyecciones deben descontar días no operativos.
5. `matriz_proyecciones`: cargar horas y dotaciones proyectadas por mes.
6. `matriz_precios`: cargar precios por mes para cruzar contra las horas proyectadas.
7. `variables_campanias`: cargar porcentajes variables una vez que exista Facturación horas.

### `usuarios`

Campos principales:

| Campo | Descripción |
| --- | --- |
| `nombre` | Nombre visible del usuario. |
| `email` | Email único para iniciar sesión. |
| `password_hash` | Contraseña hasheada, nunca texto plano. |
| `rol` | Rol del usuario. Valores usados: `administrador`, `superusuario`, `usuario`. |
| `activo` | Define si puede iniciar sesión. |

Datos que necesitás agregar:

- al menos un administrador;
- usuarios operativos según quién cargue o consulte información.

### `asignaciones_comerciales`

Es la tabla maestra más importante para ordenar la aplicación.

Campos principales:

| Campo | Descripción |
| --- | --- |
| `cliente` | Cliente comercial. |
| `gerente` | Gerencia o site principal usado para agrupación. |
| `jefe_site` | Responsable o jefe de site. |
| `campania` | Campaña, con soporte para acentos y Ñ. |
| `subcampania` | Subcampaña o apertura secundaria. |
| `tipo_negocio` | Clasificación operativa/comercial. |
| `activa` | Indica si aparece en formularios y filtros. |

Datos que necesitás agregar:

- una fila por combinación comercial válida;
- cliente y campaña exactamente como se van a usar luego en facturación, proyecciones y precios;
- site/gerente correcto para que los filtros agrupen bien.

Esta tabla alimenta formularios de carga, filtros, Matriz de proyecciones, Matriz de precios, Facturación horas, Variable y Control proyecciones.

### `facturacion_2026`

Guarda la facturación real.

Campos principales:

| Campo | Descripción |
| --- | --- |
| `fecha` | Fecha del registro. |
| `mes` | Mes de análisis. |
| `cliente`, `gerente`, `jefe_site`, `campania`, `subcampania`, `tipo_negocio` | Dimensiones comerciales. |
| `tipo_jornada` | Tipo de jornada o tipo VH. |
| `horas_objetivo` | Horas esperadas. |
| `horas_facturadas` | Horas efectivamente facturadas. |
| `horas_penalizadas` | Horas descontadas por penalización. |
| `valor_hora_objetivo` | Valor hora esperado. |
| `valor_hora` | Valor hora alcanzado/facturado. |
| `tarifacion` | Ajuste adicional de tarifación. |
| `importe_fijo` | Importe fijo si no aplica cálculo por horas. |
| `variable_objetivo` | Bono/variable objetivo. |
| `variable_productivo` | Variable productiva real. |
| `bonos` | Bonos facturados. |
| `penalizaciones` | Penalizaciones, tratadas como descuento. |
| `netx_gen`, `otros` | Otros importes de apertura. |

Datos que necesitás agregar:

- registros reales por mes;
- horas e importes necesarios para calcular objetivo, real, desvío y cumplimiento;
- dimensiones comerciales consistentes con `asignaciones_comerciales`.

Esta tabla alimenta Dashboard, Control, Comparativo, Matriz, Justificaciones y exportaciones.

### `justificaciones_ajustes`

Guarda explicaciones o ajustes vinculados a un registro de `facturacion_2026`.

Campos principales:

| Campo | Descripción |
| --- | --- |
| `facturacion_id` | Registro de facturación asociado. |
| `tipo` | Tipo de ajuste, por ejemplo penalización, bono u otro concepto. |
| `cantidad` | Cantidad del ajuste. |
| `precio` | Precio unitario. |
| `importe` | Importe total. |
| `descripcion` | Explicación del ajuste. |

Datos que necesitás agregar:

- solo cuando un registro necesita explicación, ajuste o soporte documental;
- en penalizaciones, el sistema interpreta el importe como descuento.

### `feriados_operativos`

Guarda fechas no operativas para el cálculo de días objetivo.

Campos principales:

| Campo | Descripción |
| --- | --- |
| `year` | Año del feriado. |
| `fecha` | Fecha exacta. |
| `nombre` | Nombre o descripción. |
| `tipo` | Clasificación, por defecto `Manual`. |
| `activo` | Indica si impacta en cálculos. |

Datos que necesitás agregar:

- feriados nacionales, propios o no operativos que deban descontarse;
- una fila por fecha.

Cuando se agrega o elimina un feriado activo, se recalculan las proyecciones del mes afectado.

### `matriz_proyecciones`

Guarda la planificación mensual de cada cliente/campaña.

Campos principales:

| Campo | Descripción |
| --- | --- |
| `cliente` | Cliente proyectado. |
| `campania` | Campaña proyectada. |
| `year` | Año de planificación. |
| `mes` | Mes en formato `YYYY-MM`. |
| `dotacion_requerida` | Dotación necesaria del mes. |
| `carga_semanal` | Esquema semanal, por ejemplo `L a V`. |
| `carga_horaria` | Horas por día o jornada. |
| `dias_objetivo` | Días operativos del mes. |
| `horas_requeridas` | Horas esperadas antes de cumplimiento. |
| `porcentaje_cumplimiento` | Porcentaje aplicado sobre horas requeridas. |

Clave única:

```text
cliente + campania + mes
```

Datos que necesitás agregar:

- una fila por cliente/campaña/mes;
- dotación requerida para usar Control proyecciones en pestaña Dotaciones;
- horas requeridas y porcentaje de cumplimiento para calcular Horas;
- cliente y campaña alineados con `asignaciones_comerciales`.

Esta tabla alimenta Matriz de proyecciones, Control proyecciones y Facturación horas.

### `matriz_proyecciones_jornadas`

Guarda aperturas internas de jornada para una proyección.

Campos principales:

| Campo | Descripción |
| --- | --- |
| `proyeccion_id` | Proyección principal asociada. |
| `dotacion_requerida` | Dotación de esa jornada. |
| `carga_semanal` | Esquema semanal de esa jornada. |
| `carga_horaria` | Carga horaria de esa jornada. |
| `dias_objetivo` | Días objetivo de esa jornada. |
| `horas_requeridas` | Horas requeridas de esa jornada. |

Datos que necesitás agregar:

- solo si una campaña tiene más de una jornada o configuración dentro del mismo mes;
- si no hay apertura, alcanza con `matriz_proyecciones`.

### `matriz_precios`

Guarda precios mensuales para cruzar contra horas proyectadas.

Campos principales:

| Campo | Descripción |
| --- | --- |
| `site` | Site/gerencia usado para agrupación. |
| `cliente` | Cliente. |
| `campania` | Campaña. |
| `year` | Año. |
| `mes` | Mes en formato `YYYY-MM`. |
| `precio_base` | Precio cargado base. |
| `alcance_porcentaje` | Porcentaje de alcance aplicado al precio. |
| `precio_final` | Precio calculado. |
| `importe_fijo_mensual` | Importe fijo alternativo o adicional del mes. |

Clave única:

```text
cliente + campania + mes
```

Datos que necesitás agregar:

- una fila por cliente/campaña/mes con precio;
- `alcance_porcentaje` normalmente en `100`;
- `importe_fijo_mensual` en `0` si no aplica;
- precios de todos los meses necesarios para que Facturación horas calcule completo.

Esta tabla alimenta Facturación horas. También recibe impacto de inflación o deflación global desde un mes hacia adelante.

### `variables_campanias`

Guarda el porcentaje variable mensual aplicado sobre Facturación horas.

Campos principales:

| Campo | Descripción |
| --- | --- |
| `site` | Site/gerencia de la campaña. |
| `cliente` | Cliente. |
| `campania` | Campaña. |
| `year` | Año. |
| `mes` | Mes en formato `YYYY-MM`. |
| `porcentaje` | Porcentaje variable aplicado. |

Clave única:

```text
cliente + campania + mes
```

Datos que necesitás agregar:

- una fila por campaña/mes cuando tenga variable;
- se puede guardar `0`;
- la campaña debe existir en Facturación horas para ese año.

Esta tabla alimenta el módulo Variable y puede deshacerse desde Historial.

### `historial_cambios`

Guarda auditoría de operaciones.

Campos principales:

| Campo | Descripción |
| --- | --- |
| `usuario_id`, `usuario_nombre`, `usuario_email` | Usuario que ejecutó la acción. |
| `accion` | Tipo de operación: creación, edición, eliminación, importación, etc. |
| `entidad` | Módulo afectado. |
| `entidad_id` | Identificador del registro o movimiento. |
| `resumen` | Texto corto para mostrar en Historial. |
| `detalle` | Detalle adicional. |
| `antes` | Snapshot anterior en JSON. |
| `despues` | Snapshot posterior en JSON. |

Datos que necesitás agregar:

- normalmente ninguno manualmente;
- la aplicación lo completa automáticamente cuando se realizan cambios.

## Dependencias entre tablas

Para que los módulos funcionen correctamente:

- `asignaciones_comerciales` debe cargarse antes de proyecciones, precios y variables.
- `matriz_proyecciones` necesita cliente/campaña existentes en el maestro.
- `matriz_precios` debe coincidir en cliente/campaña/mes con `matriz_proyecciones` para que Facturación horas calcule.
- `variables_campanias` se carga sobre campañas que ya aparecen en Facturación horas.
- `feriados_operativos` afecta el cálculo de días objetivo de `matriz_proyecciones`.
- `historial_cambios` no es una tabla de carga manual: audita operaciones del sistema.

## Módulos funcionales

### Dashboard

Pantalla ejecutiva para seguimiento general.

Permite:

- ver KPIs de facturación;
- consultar total real, total teórico, desvío y cumplimiento;
- analizar evolución mensual;
- revisar alertas;
- filtrar por mes, cliente, gerente, jefe de site, campaña, subcampaña y tipo de negocio;
- abrir lecturas por cliente o por agrupaciones comerciales.

### Cargar datos

Módulo para ingresar registros de facturación real.

Incluye:

- carga manual;
- carga masiva desde archivo;
- validación de fechas, importes, horas y datos comerciales;
- detección de registros existentes;
- reemplazo controlado;
- normalización de números con coma o punto;
- soporte para acentos, Ñ y nombres comerciales reales.

La coincidencia para detectar posibles reemplazos se basa en campos comerciales y fecha del registro.

### Datos maestros

Administra las asociaciones comerciales que ordenan la información.

Permite mantener:

- cliente;
- gerente;
- jefe de site;
- campaña;
- subcampaña;
- tipo de negocio;
- estado activo/inactivo.

Estas asociaciones alimentan filtros, formularios y agrupaciones de los módulos proyectados.

### Control

Vista detallada de registros reales cargados.

Permite:

- buscar registros;
- filtrar por dimensiones comerciales;
- editar datos cargados;
- eliminar registros con control de permisos;
- exportar información;
- revisar importes calculados.

### Justificaciones

Módulo para documentar ajustes, desvíos o diferencias.

Permite:

- asociar justificaciones a registros;
- cargar cantidad, precio e importe;
- controlar penalizaciones y ajustes;
- mantener explicación auditable de cambios o diferencias.

### Comparativo

Vista de análisis entre objetivo, real y desvíos.

Sirve para:

- comparar cumplimiento;
- revisar diferencias por cliente o campaña;
- detectar desvíos relevantes;
- analizar meses o responsables específicos.

### Matriz

Vista matricial de facturación real.

Permite analizar la información cargada en una estructura más compacta, útil para revisión mensual y cruces por dimensiones comerciales.

## Proyectados

Los módulos de Proyectados trabajan con planificación futura o estimada. Están pensados para construir un escenario mensual de horas, dotaciones, precios, variables y facturación esperada.

### Matriz de proyecciones

Carga la planificación mensual por cliente y campaña.

Campos principales:

- año;
- mes;
- cliente;
- campaña;
- dotación requerida;
- carga semanal;
- carga horaria;
- días objetivo;
- horas requeridas;
- porcentaje de cumplimiento;
- horas proyectadas.

Regla principal:

```text
horas proyectadas = horas requeridas * porcentaje de cumplimiento / 100
```

El módulo también considera calendario operativo y feriados para recalcular días objetivo cuando corresponde.

Funciones disponibles:

- carga manual por campaña;
- importación desde plantilla;
- descarga de plantilla;
- eliminación individual;
- eliminación masiva del año;
- deshacer último cambio;
- registro en historial.

### Calendario operativo

Administra feriados o días no operativos.

Permite:

- cargar feriados por fecha;
- indicar descripción;
- activar o eliminar feriados;
- recalcular proyecciones afectadas;
- impactar en días objetivo y horas proyectadas.

Cuando se agrega o elimina un feriado, el sistema recalcula las proyecciones del mes afectado.

### Matriz de precios

Carga precios mensuales por campaña.

Permite:

- cargar precio por cliente/campaña/mes;
- cargar importe fijo mensual;
- importar desde plantilla;
- descargar plantilla;
- eliminar precios;
- aplicar inflación global desde un mes hacia adelante;
- usar índices positivos, cero o negativos.

Regla de inflación:

```text
nuevo precio = precio actual + (precio actual * índice / 100)
```

El índice se aplica a todos los precios desde el mes elegido hacia adelante. Si el índice es negativo, funciona como deflación. Si es `0`, mantiene los precios sin cambios pero registra la operación cuando corresponde.

Los cálculos monetarios usan redondeo consistente para evitar diferencias entre campañas con el mismo precio base.

### Facturación horas

Antes llamada Resumen. Muestra el cruce entre proyecciones y precios.

Calcula:

```text
facturación horas = horas proyectadas * precio mensual
```

También contempla importes fijos cuando están cargados.

Permite:

- filtrar por site, cliente, campaña y concepto;
- ver totales anuales;
- ver evolución mensual;
- revisar detalle por campaña;
- identificar campañas sin precio o sin cruce;
- usar la información como base para el cálculo de Variable.

### Variable

Permite cargar un porcentaje mensual por campaña sobre el resultado de Facturación horas.

La pantalla muestra solo campañas que existen en Facturación horas, para evitar cargar variables sobre campañas sin base de cálculo.

Campos:

- campaña;
- mes;
- porcentaje variable.

Regla:

```text
resultado variable = facturación horas del mes * porcentaje variable / 100
```

Características:

- el porcentaje puede ser `0`;
- el input selecciona el valor al hacer foco para facilitar la carga;
- los resultados se muestran por mes;
- los números se muestran centrados;
- se puede deshacer desde Historial;
- soporta acentos y Ñ en cliente, campaña y site.

### Control proyecciones

Módulo separado de Variable para revisar lo cargado en Matriz de proyecciones.

Tiene dos pestañas:

- **Horas**: muestra horas proyectadas por campaña y mes.
- **Dotaciones**: muestra dotación requerida por campaña y mes.

La información se trae directo desde las proyecciones cargadas. No calcula facturación ni variables: es una vista de control operativo para validar que la planificación mensual esté bien cargada.

Permite:

- filtrar por site;
- filtrar por cliente;
- filtrar por campaña;
- buscar por texto;
- ver total anual;
- ver totales por mes;
- alternar entre horas y dotaciones sin salir del módulo.

## Historial y deshacer

El sistema registra cambios relevantes en `HistorialCambio`.

Se registran operaciones como:

- creación;
- edición;
- eliminación;
- importación;
- eliminación masiva;
- inflación aplicada;
- cambios de variable;
- cambios de proyecciones;
- cambios de precios.

Desde Historial se puede deshacer, cuando aplica, cambios de:

- Matriz de proyecciones;
- Matriz de precios;
- Variable.

El deshacer restaura el estado anterior guardado en el snapshot del historial. Si el registro no existía, se recrea; si debía eliminarse, se elimina; si debía modificarse, se restaura el valor previo.

## Importaciones y plantillas

El sistema ofrece plantillas para evitar errores de estructura.

Plantillas disponibles:

- carga de facturación;
- matriz de proyecciones;
- matriz de precios.

Formatos soportados según el módulo:

- `.xlsx`;
- `.csv`;
- HTML tabular copiado desde Excel, cuando el parser lo permite.

Las importaciones validan encabezados, meses y campos obligatorios antes de guardar.

## Exportaciones

La aplicación permite exportar información a Excel desde módulos de control y análisis.

Las exportaciones respetan filtros activos cuando el endpoint lo contempla.

## Cálculos principales

### Facturación real

El modelo de facturación calcula, entre otros:

- valor hora alcanzado;
- valor hora objetivo;
- objetivo de facturación horas;
- objetivo de facturación bono;
- facturado horas;
- facturado bono;
- variable productivo;
- penalizaciones;
- total real;
- total teórico;
- desvío;
- porcentaje de cumplimiento.

### Penalizaciones

Las penalizaciones impactan como descuento. Aunque se carguen como valor positivo, el cálculo las resta del total correspondiente.

### Redondeo monetario

Los importes monetarios proyectados usan redondeo centralizado para evitar diferencias pequeñas entre campañas con el mismo precio base.

## APIs principales

Rutas HTML:

```text
/login
/
/cargar
/catalogos
/control
/justificaciones
/comparativo
/matriz
/matriz-proyecciones
/matriz-precios
/resumen
/variable
/control-proyecciones
/calendario-operativo
/historial
/usuarios
```

APIs destacadas:

```text
/api/auth/login
/api/auth/logout
/api/auth/me
/api/datos
/api/cargar
/api/resumen
/api/kpis
/api/grafico
/api/filtros
/api/comparativo
/api/matriz
/api/matriz-proyecciones
/api/matriz-precios
/api/matriz-precios/inflacion
/api/resumen-proyeccion
/api/variables
/api/control-proyecciones
/api/calendario-operativo
/api/historial
/api/historial/<id>/deshacer
/api/exportar_excel
/api/template_carga
/api/importar_datos
/api/asignaciones
/api/clientes
/api/gerentes
/api/meses
```

## Seguridad

Medidas incluidas:

- Flask escucha en `127.0.0.1` por defecto;
- sesiones con cookie `HttpOnly`;
- `SameSite=Lax`;
- CSRF obligatorio en métodos de escritura;
- validación de `Origin`/`Referer`;
- CORS limitado a orígenes configurados;
- límite de tamaño de archivo;
- rate limit simple para intentos de login;
- headers de seguridad;
- permisos por rol;
- confirmaciones para acciones sensibles.

Para producción:

```text
SECRET_KEY=generar-una-clave-segura
SESSION_COOKIE_SECURE=1
FLASK_DEBUG=0
FLASK_RELOAD=0
TEMPLATES_AUTO_RELOAD=0
```

Servir siempre detrás de HTTPS y con una base de datos administrada.

## Flujo recomendado de uso

1. Cargar o revisar Datos maestros.
2. Cargar facturación real en Cargar datos.
3. Controlar registros desde Control.
4. Revisar Dashboard, Comparativo y Matriz.
5. Cargar Matriz de proyecciones.
6. Configurar Calendario operativo.
7. Cargar Matriz de precios.
8. Revisar Facturación horas.
9. Cargar Variable.
10. Revisar Control proyecciones para validar horas y dotaciones.
11. Usar Historial para auditar o deshacer cambios.

## Problemas frecuentes

### `npm` no se reconoce

Instalar Node.js o ejecutar:

```powershell
.\dev.ps1
```

### La app usa otro puerto

Configurar `PORT` antes de iniciar Flask:

```powershell
$env:PORT="8010"
python run.py
```

### No veo cambios en templates

En desarrollo, activar recarga:

```powershell
$env:FLASK_RELOAD="1"
$env:TEMPLATES_AUTO_RELOAD="1"
python run.py
```

O reiniciar el servidor.

### Error de permisos con SQLite

Verificar que el proceso que ejecuta Flask tenga permiso de escritura sobre:

```text
instance/facturacion.db
```

### No puedo guardar desde el navegador

Revisar:

- sesión iniciada;
- permisos del rol;
- token CSRF presente;
- origen permitido en `CORS_ORIGINS`;
- que se esté usando `127.0.0.1` o `localhost` según configuración.

## Notas de desarrollo

- El backend está concentrado en `app/routes.py` y `app/models.py`.
- La base local se crea y ajusta automáticamente al iniciar la app.
- Las pantallas Flask usan templates Jinja en `app/templates`.
- El frontend Next.js vive en `next-app`.
- Evitar editar manualmente la base salvo que sea necesario.
- Mantener textos visibles en español con acentos y Ñ.
- No dejar cambios de `__pycache__` ni logs como parte de commits.
