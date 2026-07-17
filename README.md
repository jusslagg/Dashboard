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
| `personal_distribucion_horas` | `PersonalDistribucionHoras` | Guarda por año, mes y clasificación PLP el porcentaje de horas diurnas; la nocturnidad es la diferencia hasta 100%. |
| `matriz_precios` | `ProyeccionPrecio` | Guarda precios mensuales por cliente/campaña, alcance, precio final e importe fijo mensual. |
| `variables_campanias` | `VariableCampania` | Guarda el porcentaje variable mensual por cliente/campaña. |
| `tarifaciones_campanias` | `TarifacionCampania` | Guarda montos mensuales positivos o negativos que se suman a Facturación horas. |
| `next_gen_dolar` | `NextGenDolar` | Guarda el valor del dólar utilizado por Next Gen para cada mes y año. |
| `next_gen_productos` | `NextGenProducto` | Guarda cantidades mensuales en USD por cliente, campaña y producto Next Gen. |
| `sites_proyecciones` | `SiteProyeccion` | Guarda la regularización manual del site o gerencia de una campaña proyectada. |
| `feriados_operativos` | `FeriadoOperativo` | Guarda feriados o días no operativos que afectan los días objetivo de las proyecciones. |

### Mapa de carga y destino

| Tabla | Dónde se carga | A dónde apunta / qué alimenta |
| --- | --- | --- |
| `usuarios` | Usuarios o configuración inicial | Login, sesiones, permisos e identificación del historial. |
| `asignaciones_comerciales` | Datos maestros | Formularios, filtros, sites, clientes y campañas de todos los módulos. |
| `facturacion_2026` | Cargar datos, importación de facturación o edición en Control | Dashboard, Control, Comparativo, Matriz, Justificaciones y exportaciones reales. |
| `justificaciones_ajustes` | Justificaciones | Un registro concreto de `facturacion_2026`; ajusta y explica bonos, penalizaciones u otros conceptos. |
| `feriados_operativos` | Calendario operativo | Días objetivo, horas y dotaciones de `matriz_proyecciones`. |
| `matriz_proyecciones` | Matriz de proyecciones, importación general o importación PLP | Control proyecciones y base de horas de Facturación horas. |
| `matriz_proyecciones_jornadas` | Aperturas de jornada dentro de una proyección | Suma de horas y dotaciones de su registro padre en `matriz_proyecciones`. |
| `personal_distribucion_horas` | Matriz de proyecciones > PLP > porcentajes | Apertura diurna/nocturna de las proyecciones Personal y sus cálculos posteriores. |
| `matriz_precios` | Matriz de precios o importación anual | Valoriza horas proyectadas, nocturnidad e importes fijos en Facturación horas. |
| `variables_campanias` | Variable > % Variable o importación anual | Estimación variable y total consolidado de Facturación horas. |
| `tarifaciones_campanias` | Variable > Tarifación o importación anual | Ajuste monetario sumado o restado en Facturación horas. |
| `next_gen_dolar` | Variable > Next Gen o importación anual | Cotización mensual usada para convertir productos Next Gen a pesos. |
| `next_gen_productos` | Variable > Next Gen o importación anual | Importe Next Gen en pesos y total consolidado de Facturación horas. |
| `sites_proyecciones` | Edición directa de la columna Site en Facturación horas | Reagrupa todos los meses y conceptos consolidados de la campaña. |
| `historial_cambios` | Automática; no se carga manualmente | Auditoría y restauración de snapshots en operaciones compatibles con Deshacer. |

### Ficha de colecciones para la base de datos

Esta sección resume qué necesita cada tabla/colección para que la base quede armada correctamente.

#### `usuarios`

- **Propósito**: administrar acceso, roles y estado de los usuarios.
- **Campos clave**: `nombre`, `email`, `password_hash`, `rol`, `activo`.
- **Obligatorio para iniciar**: sí. Debe existir al menos un usuario administrador.
- **Reglas importantes**: el email debe ser único; la contraseña se guarda como hash; los roles habilitan o bloquean acciones sensibles.
- **Carga manual recomendada**: solo usuarios reales o de administración.

#### `asignaciones_comerciales`

- **Propósito**: catálogo maestro que define combinaciones válidas de cliente, gerente/site, jefe, campaña, subcampaña y tipo de negocio.
- **Campos clave**: `cliente`, `gerente`, `jefe_site`, `campania`, `subcampania`, `tipo_negocio`, `activa`.
- **Obligatorio para iniciar**: sí, antes de proyecciones, precios y variables.
- **Reglas importantes**: cliente y campaña deben escribirse igual que en facturación, proyecciones y precios; una asociación inactiva no debería usarse para cargas nuevas.
- **Uso histórico**: si cambia el jefe desde un mes puntual, usar **Aplicar desde mes** para no pisar meses anteriores.

#### `facturacion_2026`

- **Propósito**: guardar la facturación real cargada por mes y dimensión comercial.
- **Campos clave**: `fecha`, `mes`, `cliente`, `gerente`, `jefe_site`, `campania`, `subcampania`, `tipo_negocio`, `tipo_jornada`, horas e importes.
- **Obligatorio para iniciar**: sí, si se quiere usar Dashboard, Control, Comparativo, Matriz, Justificaciones y exportaciones.
- **Reglas importantes**: `mes` debe estar en formato `YYYY-MM`; las dimensiones comerciales deben coincidir con `asignaciones_comerciales`; penalizaciones se tratan como descuento.
- **Datos mínimos útiles**: fecha, mes, cliente, gerente, jefe, campaña, subcampaña, tipo de jornada, horas objetivo, horas facturadas y valor hora.

#### `justificaciones_ajustes`

- **Propósito**: explicar ajustes, bonos, penalizaciones u otros conceptos asociados a una carga real.
- **Campos clave**: `facturacion_id`, `tipo`, `cantidad`, `precio`, `importe`, `descripcion`.
- **Obligatorio para iniciar**: no.
- **Reglas importantes**: cada justificación debe apuntar a un registro existente de `facturacion_2026`; en penalizaciones, el importe impacta como descuento.
- **Carga manual recomendada**: solo cuando un desvío o ajuste necesite respaldo.

#### `matriz_proyecciones`

- **Propósito**: guardar la planificación mensual de horas y dotaciones por cliente/campaña.
- **Campos clave**: `cliente`, `campania`, `year`, `mes`, `dotacion_requerida`, `carga_semanal`, `carga_horaria`, `dias_objetivo`, `horas_requeridas`, `porcentaje_cumplimiento`.
- **Obligatorio para iniciar**: sí, si se usan Proyectados, Facturación horas, Variable o Control proyecciones.
- **Clave funcional**: `cliente + campania + mes`.
- **Reglas importantes**: `mes` debe estar en formato `YYYY-MM`; cliente/campaña deben existir en Datos maestros; feriados activos pueden recalcular días objetivo.

#### `matriz_proyecciones_jornadas`

- **Propósito**: abrir una proyección en varias jornadas cuando una campaña tiene más de una configuración horaria dentro del mismo mes.
- **Campos clave**: `proyeccion_id`, `dotacion_requerida`, `carga_semanal`, `carga_horaria`, `dias_objetivo`, `horas_requeridas`.
- **Obligatorio para iniciar**: no.
- **Reglas importantes**: cada fila depende de una proyección existente en `matriz_proyecciones`.
- **Cuándo usarla**: solo cuando una misma campaña/mes necesita separar jornadas.

#### `personal_distribucion_horas`

- **Propósito**: definir la apertura diurna/nocturna de las proyecciones PLP de Personal.
- **Campos clave**: `servicio`, `year`, `mes`, `porcentaje_diurno`.
- **Clasificaciones admitidas**: `Personal CX`, `Personal`, `Personal Soporte` y `Personal SMB`.
- **Clave funcional**: `servicio + mes`.
- **Regla principal**: `porcentaje_nocturno = 100 - porcentaje_diurno`.
- **Destino**: recalcula las aperturas principal y `nocturnidad` de `matriz_proyecciones`; ambas alimentan Matriz de precios, Facturación horas, Variable y Control proyecciones.
- **Cambio de año**: si el año seleccionado no tiene valores propios, la pantalla propone los porcentajes del año anterior. Al guardarlos se crean registros para el nuevo año sin modificar el histórico.
- **Carga manual recomendada**: revisar los doce porcentajes de cada clasificación antes de importar o recalcular PLP.

#### `matriz_precios`

- **Propósito**: guardar precios mensuales para calcular facturación proyectada.
- **Campos clave**: `site`, `cliente`, `campania`, `year`, `mes`, `precio_base`, `alcance_porcentaje`, `precio_final`, `importe_fijo_mensual`.
- **Obligatorio para iniciar**: sí, si se quiere calcular Facturación horas.
- **Clave funcional**: `cliente + campania + mes`.
- **Reglas importantes**: debe coincidir con `matriz_proyecciones` en cliente/campaña/mes; `alcance_porcentaje` normalmente es `100`; `importe_fijo_mensual` puede quedar en `0`.

#### `variables_campanias`

- **Propósito**: guardar el porcentaje variable mensual aplicado sobre Facturación horas.
- **Campos clave**: `site`, `cliente`, `campania`, `year`, `mes`, `porcentaje`.
- **Obligatorio para iniciar**: no, salvo que se necesite calcular variables.
- **Clave funcional**: `cliente + campania + mes`.
- **Reglas importantes**: la campaña debe existir en Facturación horas; el porcentaje puede ser `0`; los cambios quedan auditados y pueden deshacerse desde Historial cuando aplica.

#### `tarifaciones_campanias`

- **Propósito**: guardar ajustes monetarios independientes de las horas y del porcentaje variable.
- **Campos clave**: `site`, `cliente`, `campania`, `concepto`, `year`, `mes`, `monto`.
- **Clave funcional**: `cliente + campania + concepto + mes`.
- **Reglas importantes**: el monto conserva su signo; un valor positivo suma y uno negativo resta. La coincidencia con Facturación horas ignora mayúsculas, minúsculas y acentos.
- **Destino**: se incorpora al mismo renglón consolidado de la campaña en Facturación horas.
- **Carga**: se puede ingresar manualmente o importar todo el año desde la subpestaña **Tarifación**.
- **Auditoría**: las creaciones, ediciones e importaciones quedan identificadas como Tarifación en Historial y se pueden deshacer.

#### `feriados_operativos`

- **Propósito**: registrar días no operativos que impactan en los días objetivo de proyecciones.
- **Campos clave**: `year`, `fecha`, `nombre`, `tipo`, `activo`.
- **Obligatorio para iniciar**: no, salvo que las proyecciones deban descontar feriados.
- **Clave funcional**: `fecha`.
- **Reglas importantes**: solo feriados activos impactan cálculos; al agregar o eliminar un feriado activo, se recalculan proyecciones del mes afectado.

#### `historial_cambios`

- **Propósito**: auditar operaciones relevantes y guardar snapshots para trazabilidad.
- **Campos clave**: `usuario_id`, `usuario_nombre`, `usuario_email`, `accion`, `entidad`, `entidad_id`, `resumen`, `detalle`, `antes`, `despues`.
- **Obligatorio para iniciar**: no se carga manualmente.
- **Reglas importantes**: la aplicación lo completa automáticamente; permite revisar cambios y deshacer algunas operaciones soportadas.
- **Uso esperado**: auditoría de creación, edición, eliminación, importaciones, inflación, precios, variables y proyecciones.

### Datos mínimos para iniciar

Para una base nueva, el orden recomendado de carga es:

1. `usuarios`: crear al menos un usuario `administrador`.
2. `asignaciones_comerciales`: cargar el maestro comercial base.
3. `facturacion_2026`: cargar registros reales si se quiere usar Dashboard, Control, Matriz, Comparativo y Justificaciones.
4. `feriados_operativos`: cargar feriados si las proyecciones deben descontar días no operativos.
5. `matriz_proyecciones`: cargar horas y dotaciones proyectadas por mes.
6. `personal_distribucion_horas`: configurar los porcentajes diurnos/nocturnos de PLP para el año correspondiente.
7. `matriz_precios`: cargar precios por mes para cruzar contra las horas proyectadas, incluyendo los nombres de nocturnidad cuando tengan un precio específico.
8. `variables_campanias`: cargar porcentajes variables una vez que exista Facturación horas.
9. `tarifaciones_campanias`: cargar ajustes monetarios mensuales positivos o negativos cuando correspondan.

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

#### Cambios de jefe de site con vigencia mensual

Cuando una campaña cambia de responsable a partir de un mes determinado, no se debe pisar toda la asociación histórica. En Datos maestros se puede editar la asociación y completar **Aplicar desde mes** con formato `YYYY-MM`.

Ejemplo:

- `Santander Chat` estuvo bajo la jefatura de `Ismael Rissi` hasta `2026-05`.
- Desde `2026-06` pasa a `Mariela Ditto`.

Al editar la asociación y cargar `2026-06` en **Aplicar desde mes**, el sistema:

- mantiene los registros anteriores a junio con `Ismael Rissi`;
- actualiza desde junio en adelante con `Mariela Ditto`;
- crea o activa una nueva asociación para la combinación vigente;
- registra la operación en Historial.

Si **Aplicar desde mes** queda vacío, la edición se comporta como una actualización general de la asociación y de sus cargas vinculadas.

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
| `tiene_nocturnidad` | Indica si la proyección se abre en horas diurnas y nocturnas. |
| `porcentaje_nocturnidad` | Porcentaje nocturno aplicado; en PLP se obtiene desde la distribución mensual. |
| `tipo_plp` | Clasificación PLP: Personal CX, Personal, Personal Soporte o Personal SMB. |
| `horas_carga_manual` | Identifica que las horas fueron ingresadas directamente, como ocurre en PLP. |
| `dias_objetivo_manual` | Reemplazo opcional de los días calculados para campañas que operan solo una parte del mes. |
| `horas_requeridas_manual` | Reemplazo opcional del total calculado desde dotación, días y jornada. |

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

En el formulario general, **Días hábiles manuales** y **Horas requeridas manuales** son opcionales. Si quedan vacíos, se usa el cálculo automático. Si se informan, tienen prioridad y permanecen guardados al editar o recalcular la proyección. Esto permite representar altas a mitad de mes, cierres anticipados u otras ventanas operativas parciales.

En PLP el `cliente` siempre se guarda como `Personal`. `tipo_plp` identifica la clasificación y `campania` conserva el nombre operativo importado, por ejemplo `MÓVIL TELEFÓNICO`. En pantalla, todos los servicios de una misma clasificación y mes se acumulan en dos renglones: la clasificación principal y la misma clasificación con el sufijo `nocturnidad`.

### `personal_distribucion_horas`

Campos principales:

| Campo | Descripción |
| --- | --- |
| `servicio` | Clasificación PLP: Personal CX, Personal, Personal Soporte o Personal SMB. |
| `year` | Año al que pertenece la distribución. |
| `mes` | Mes en formato `YYYY-MM`. |
| `porcentaje_diurno` | Proporción de horas que queda en el renglón principal. |
| `porcentaje_nocturno` | Valor calculado como `100 - porcentaje_diurno`; no se carga directamente. |

Los porcentajes se administran desde **Matriz de proyecciones > PLP**. Cambiar un porcentaje recalcula todas las proyecciones PLP coincidentes del mes. Los datos de años anteriores permanecen intactos.

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

### `tarifaciones_campanias`

Campos principales:

| Campo | Descripción |
| --- | --- |
| `site` | Site o gerencia de agrupación. |
| `cliente` | Cuenta comercial. |
| `campania` | Nombre que debe coincidir con la campaña de Facturación horas. |
| `concepto` | Etiqueta del ajuste, por ejemplo `Tarifación` o `Penalidad ADH`. |
| `year`, `mes` | Período del importe. |
| `monto` | Importe con signo: positivo suma y negativo resta. |

La tabla no reemplaza el campo `tarifacion` de la facturación real: `tarifaciones_campanias` pertenece exclusivamente al circuito proyectado y se integra en Facturación horas.

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
- Las proyecciones PLP siempre usan `Personal` como cliente y una de las cuatro clasificaciones admitidas en `tipo_plp`; el nombre operativo queda en `campania`.
- `personal_distribucion_horas` divide las horas PLP en principal y nocturnidad antes del cruce con precios.
- `matriz_precios` debe coincidir en cliente/campaña/mes con `matriz_proyecciones` para que Facturación horas calcule.
- `variables_campanias` se carga sobre campañas que ya aparecen en Facturación horas.
- `tarifaciones_campanias` se cruza por cliente/campaña/mes y suma o resta el monto al consolidado de Facturación horas.
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

Cuando cambia el jefe de una campaña, permite indicar desde qué mes aplica el cambio para preservar el histórico mensual. Por ejemplo, si `Santander Chat` cambia de `Ismael Rissi` a `Mariela Ditto` desde junio, se edita la asociación, se cambia el jefe y se completa **Aplicar desde mes** con `2026-06`. Los meses anteriores quedan asociados al jefe anterior.

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

#### Subpestaña PLP

Es el circuito exclusivo para campañas cuyo cliente es `Personal`. Las clasificaciones válidas son `Personal CX`, `Personal`, `Personal Soporte` y `Personal SMB`.

Cada registro conserva el nombre operativo de la campaña, el mes y las horas cargadas, pero el listado acumula los nombres operativos de una misma clasificación. La apertura se muestra en dos renglones:

- clasificación principal: horas correspondientes al porcentaje diurno;
- `clasificación nocturnidad`: horas restantes hasta completar el 100%.

La jornada comienza predefinida en `L a V` y `6` horas, pero ambos campos son editables. Los días objetivo salen de los días laborales del mes, descontando feriados activos. La dotación se recalcula así:

```text
dotación requerida = horas requeridas / días laborales / horas de jornada
```

El porcentaje de cumplimiento es editable y afecta las horas proyectadas finales. El resumen mensual PLP acumula las horas base importadas al 100% para poder cotejarlas contra el archivo original.

La importación anual acepta `.xlsx` o `.csv` con estas columnas:

```text
Clasificación PLP | MES | CAMPAÑA | HORAS | Carga semanal | Horas jornada | % cumplimiento
```

Si se vuelve a importar la misma combinación `clasificación + campaña + mes`, se actualiza el registro existente en lugar de duplicarlo.

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

La vista final consolida en una sola línea por campaña:

```text
total campaña = facturación de horas + estimación variable + tarifaciones
```

En PLP, las horas principales y nocturnas se calculan con su precio correspondiente y luego se consolidan bajo la clasificación base. La asociación de variables y tarifaciones ignora diferencias de mayúsculas, minúsculas y acentos. `Multicuentas` y `Gerencia Multicampaña` se presentan bajo la misma agrupación comercial.

La identificación es editable directamente desde el lápiz de la columna **Site**. Allí se pueden regularizar el site, el cliente y la campaña. El cliente/campaña ingresado funciona como nombre canónico: si varias identificaciones de origen se asignan al mismo nombre, sus Horas, Variable, Tarifación y Next Gen se consolidan y suman en una única línea para cada mes. La regularización se guarda en `sites_proyecciones`, no modifica los nombres históricos de las tablas de origen, queda registrada en Historial y puede deshacerse.

Las proyecciones comunes se calculan por cada apertura de campaña, respetando su precio y porcentaje variable, y después se consolidan bajo el cliente. Si una apertura no tiene proyección propia para un mes, se utiliza la proyección base del cliente como respaldo. PLP conserva como excepción sus clasificaciones Personal, Personal CX, Personal Soporte y Personal SMB.

Permite:

- filtrar por site, cliente, campaña y concepto;
- ver totales anuales;
- ver evolución mensual;
- revisar detalle por campaña;
- identificar campañas sin precio o sin cruce;
- usar la información como base para el cálculo de Variable.

### Variable

El módulo tiene tres subpestañas relacionadas, pero cada una conserva su propio dato:

- **% Variable**: porcentaje mensual guardado en `variables_campanias`.
- **Estimación variable**: resultado monetario calculado; no es otra carga independiente.
- **Tarifación**: monto mensual positivo o negativo guardado en `tarifaciones_campanias`.
- **Next Gen**: cantidades mensuales en USD por producto, valorizadas con el dólar de cada mes.

La subpestaña **% Variable** permite cargar un porcentaje mensual por campaña sobre el resultado de Facturación horas.

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

La plantilla anual de variables contiene `Cuenta`, `Site`, `Cliente` y una columna por mes. Acepta porcentajes como `5`, `5%` o el valor decimal de Excel `0,05`. Al reimportar, se actualiza la combinación de campaña y mes existente. Al seleccionar un año nuevo sin valores propios, se toman como propuesta los últimos porcentajes disponibles del año anterior; los cambios posteriores no alteran el histórico.

#### Estimación variable

No requiere una tabla adicional. Se calcula sobre la facturación de horas de la misma campaña y mes:

```text
estimación variable = facturación horas * porcentaje / 100
```

Para PLP, las campañas principales y nocturnas pueden tener porcentajes propios. El resultado se consolida finalmente en el renglón de su clasificación base.

#### Tarifación

Permite ingresar o importar un monto adicional por campaña, concepto y mes:

```text
facturación consolidada = horas + estimación variable + monto de tarifación
```

Los montos negativos restan y los positivos suman. La plantilla anual incluye `Cuenta`, `Site`, `Cliente`, `Concepto` y los doce meses. Reimportar una misma combinación actualiza el valor existente.

#### Next Gen

Permite editar el valor mensual del dólar y cargar uno o varios productos por campaña. Cada producto conserva su cantidad mensual en USD y muestra el resultado convertido a pesos:

```text
Next Gen en pesos = cantidad USD del producto * valor del dólar del mes
```

Los productos de una misma campaña se acumulan y el resultado se incorpora como concepto `Next Gen` en Facturación horas. La plantilla anual replica el cuadro operativo: una columna `CLIENTE` para identificar el producto y doce columnas mensuales en USD. El valor del dólar se administra por mes desde la parte superior de la pestaña. Al reimportar, el sistema conserva la campaña asociada al producto y actualiza cada mes existente.

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
- cambios e importaciones de porcentajes variables;
- cambios e importaciones de tarifación;
- importaciones PLP y cambios de distribución diurna/nocturna.

Desde Historial se puede deshacer, cuando aplica, cambios de:

- Matriz de proyecciones;
- Matriz de precios;
- Variable.
- Tarifación.

El deshacer restaura el estado anterior guardado en el snapshot del historial. Si el registro no existía, se recrea; si debía eliminarse, se elimina; si debía modificarse, se restaura el valor previo.

## Importaciones y plantillas

El sistema ofrece plantillas para evitar errores de estructura.

Plantillas disponibles:

- carga de facturación;
- matriz de proyecciones;
- matriz de precios.
- proyecciones anuales PLP;
- porcentajes variables anuales;
- tarifaciones anuales.

Destino de cada importación:

| Plantilla | Tabla principal | Pantalla de destino | Resultado posterior |
| --- | --- | --- | --- |
| Facturación real | `facturacion_2026` | Cargar datos / Control | Dashboard, Comparativo, Matriz y exportaciones. |
| Matriz de proyecciones | `matriz_proyecciones` y, si aplica, `matriz_proyecciones_jornadas` | Proyectados > Matriz de proyecciones | Control proyecciones y Facturación horas. |
| Proyecciones PLP | `matriz_proyecciones` con `cliente=Personal` y `tipo_plp` | Proyectados > Matriz de proyecciones > PLP | Resumen PLP, aperturas diurnas/nocturnas y Facturación horas. |
| Matriz de precios | `matriz_precios` | Proyectados > Matriz de precios | Precio de las horas y de las aperturas nocturnas. |
| Variables | `variables_campanias` | Variable > % Variable | Variable > Estimación variable y Facturación horas. |
| Tarifación | `tarifaciones_campanias` | Variable > Tarifación | Suma o resta en Facturación horas. |
| Next Gen | `next_gen_dolar` y `next_gen_productos` | Variable > Next Gen | Convierte USD a pesos y suma el resultado en Facturación horas. |

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

### Proyección PLP

```text
horas diurnas = horas base * porcentaje diurno / 100
horas nocturnas = horas base * (100 - porcentaje diurno) / 100
horas proyectadas finales = horas base * porcentaje de cumplimiento / 100
dotación = horas base / días laborales / horas de jornada
```

Las aperturas diurna y nocturna se valorizan con el precio mensual que coincida con cada nombre. El resumen operativo PLP muestra las horas base al 100%; el cumplimiento se aplica en el circuito de proyección y facturación.

### Consolidado proyectado

```text
importe horas = horas proyectadas * precio final
estimación variable = importe horas * porcentaje variable / 100
total campaña = importe horas + estimación variable + Next Gen + tarifaciones
```

Una tarifación negativa funciona como descuento. No se debe confundir con el porcentaje variable ni con el campo de tarifación de la facturación real.

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
/api/proyecciones-plp/template
/api/proyecciones-plp/importar
/api/personal-distribucion
/api/matriz-precios
/api/matriz-precios/inflacion
/api/resumen-proyeccion
/api/variables
/api/variables/template
/api/variables/importar
/api/tarifaciones
/api/tarifaciones/template
/api/tarifaciones/importar
/api/next-gen
/api/next-gen/template
/api/next-gen/importar
/api/sites-proyeccion
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
7. Para Personal, seleccionar el año, revisar la distribución diurna/nocturna e importar las proyecciones PLP.
8. Cargar Matriz de precios, incluyendo precios nocturnos cuando correspondan.
9. Revisar Facturación horas.
10. Descargar o importar la plantilla de `% Variable` y revisar Estimación variable.
11. Cargar o importar Tarifación con el signo correspondiente.
12. Volver a Facturación horas y validar el consolidado `Horas + Variable + Tarifación`.
13. Revisar Control proyecciones para validar horas y dotaciones.
14. Usar Historial para auditar o deshacer cambios.

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
