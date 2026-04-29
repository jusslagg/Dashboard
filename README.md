# Sistema de Control de Facturación

Aplicación web para control de facturación con dashboard de métricas clave mensuales.

## Estructura del Proyecto

```
Dashboard/
├── app/
│   ├── __init__.py      # Configuración de Flask y SQLAlchemy
│   ├── models.py        # Modelos de datos
│   ├── routes.py        # Rutas y endpoints API
│   └── templates/
│       ├── layout.html      # Plantilla base
│       ├── index.html       # Dashboard principal
│       ├── cargar.html      # Vista de carga de datos
│       └── control.html     # Vista de control
├── run.py               # Punto de entrada
├── requirements.txt     # Dependencias
└── README.md
```

## Requisitos

- Python 3.8+
- pip

## Instalación

1. **Crear entorno virtual (opcional pero recomendado):**
   ```bash
   python -m venv venv
   venv\Scripts\activate    # Windows
   # source venv/bin/activate  # Linux/Mac
   ```

2. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Ejecutar la aplicación:**
   ```bash
   python run.py
   ```

4. **Abrir en el navegador:**
   ```
   http://localhost:5000
   ```

## Uso

### 1. Cargar Datos de Ejemplo
Al iniciar la aplicación, haz clic en el botón **"Cargar Ejemplo"** en el sidebar para populate la base de datos con datos de prueba.

### 2. Dashboard (/)
- Ver KPIs principales: Total facturado, Total teórico, Desvío, % cumplimiento
- Gráfico de evolución mensual (Real vs Teórico)
- Tabla resumen por mes
- Filtros dinámicos por mes, cliente, gerente, jefe de site, campaña y sub campaña
- Agrupación ejecutiva por cliente con tabla y gráfico
- Alertas automáticas según cumplimiento, desvío y horas sobre objetivo
- Exportación a Excel respetando los filtros activos

### 3. Cargar Datos (/cargar)
- Formulario para ingresar nuevos registros
- Validaciones en tiempo real
- Vista previa de cálculos
- Selección de cliente, gerente, jefe de site, campaña y sub campaña desde datos maestros

### Datos Maestros (/catalogos)
- Alta de asociaciones cliente / gerente / jefe de site / campaña / sub campaña
- Edición y eliminación en cascada de asociaciones con clave `CAT2026`
- Al editar una asociación se actualizan las cargas vinculadas
- Al eliminar una asociación se eliminan las cargas vinculadas
- La carga de facturación usa estas asociaciones para evitar tipeo manual

### 4. Control (/control)
- Tabla detallada con todos los registros
- Filtros por mes, cliente, gerente, jefe de site, campaña y sub campaña
- Edición y eliminación de registros con clave `CAT2026`
- Si una carga editada usa una asociación nueva, se crea/reactiva en Datos Maestros
- Exportación a Excel con los filtros activos
- Indicadores visuales:
  - 🟡 Horas facturadas > Horas objetivo (alerta)
  - 🔴 Total real < 0 (error)

## Endpoints API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/cargar` | Cargar nuevo registro |
| GET | `/api/datos` | Obtener datos (soporta `?mes=`, `?cliente=` y `?gerente=`) |
| GET | `/api/resumen` | Resumen mensual (soporta `?mes=`, `?cliente=` y `?gerente=`) |
| GET | `/api/kpis` | KPIs generales (soporta `?mes=`, `?cliente=` y `?gerente=`) |
| GET | `/api/grafico` | Datos para gráfico (soporta `?mes=`, `?cliente=` y `?gerente=`) |
| GET | `/api/filtros` | Opciones dinámicas para filtros |
| GET | `/api/por-cliente` | Resumen agrupado por cliente |
| GET | `/api/alertas` | Alertas automáticas del dashboard |
| GET | `/api/exportar_excel` | Exportar registros filtrados a Excel |
| GET | `/api/asignaciones` | Lista de asociaciones predefinidas |
| POST | `/api/asignaciones` | Crear asociación cliente/gerente/jefe de site/campaña/sub campaña |
| PATCH | `/api/asignaciones/<id>` | Activar o desactivar asociación |
| PUT | `/api/datos/<id>` | Editar registro con clave `CAT2026` |
| DELETE | `/api/datos/<id>` | Eliminar registro con clave `CAT2026` |
| POST | `/api/seed` | Cargar datos de ejemplo |
| GET | `/api/clientes` | Lista de clientes |
| GET | `/api/gerentes` | Lista de gerentes |
| GET | `/api/meses` | Lista de meses |

## Modelo de Datos

Tabla: `facturacion_2026`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | Integer | PK |
| fecha | Date | Fecha del registro |
| mes | String | Mes derivado (YYYY-MM) |
| cliente | String | Nombre del cliente |
| gerente | String | Gerente responsable |
| jefe_site | String | Jefe de site responsable |
| campania | String | Campaña asociada |
| subcampania | String | Sub campaña asociada |
| tipo_jornada | String | Tipo de VH: Diurna/Nocturna/Feriado/Capacitación/Diurnas Feriado/Nocturnas Feriado/horas líder/radio |
| horas_objetivo | Float | Horas objetivo |
| horas_facturadas | Float | Horas facturadas |
| valor_hora | Float | Valor por hora |
| tarifacion | Float | Tarifa especial (opcional) |
| bonos | Float | Bonos adicionales |
| penalizaciones | Float | Penalizaciones |
| netx_gen | Float | NetX Gen |
| otros | Float | Otros conceptos |

### Cálculos

- **total_real** = (horas_facturadas × tarifacion/valor_hora) + bonos - penalizaciones + netx_gen + otros
- **total_teorico** = horas_objetivo × valor_hora
- **desvio** = total_real - total_teorico
- **porcentaje_cumplimiento** = (total_real / total_teorico) × 100

## Escalabilidad

- **Base de datos**: SQLite por defecto, configurable para PostgreSQL cambiando `SQLALCHEMY_DATABASE_URI`
- **Autenticación**: Preparado para agregar en el futuro (estructura modular con Blueprints)
- **Frontend**: Separado en templates con TailwindCSS y JavaScript vanilla

## Tecnologías

- Backend: Flask + SQLAlchemy
- Frontend: HTML + TailwindCSS + JavaScript
- Gráficos: Chart.js
- Base de datos: SQLite
# Deploy: GitHub Pages + Render

Esta app no puede correr completa en GitHub Pages porque Flask, SQLite y los endpoints `/api/*` necesitan un proceso Python. La estructura recomendada es:

```text
Dashboard/
  app/                  # Backend Flask + templates fuente
  docs/                 # Frontend estatico para GitHub Pages
    index.html
    cargar.html
    catalogos.html
    comparativo.html
    control.html
    assets/
      config.js         # URL publica del backend
      api-client.js     # Reescribe fetch('/api/...') hacia el backend
  instance/             # SQLite local, no para GitHub Pages
  build_static.py       # Regenera docs/ desde app/templates/
  Procfile              # Render: gunicorn run:app
  requirements.txt
  run.py
```

## GitHub Pages

1. En GitHub, configurar Pages con `Deploy from a branch`.
2. Branch: `main`.
3. Folder: `/docs`.
4. Editar `docs/assets/config.js` y poner la URL publica del backend Flask:

```js
window.API_BASE = 'https://tu-dashboard.onrender.com';
```

Si `window.API_BASE` queda vacio, GitHub Pages intentara llamar `/api/*` dentro de GitHub Pages y las pantallas cargaran sin datos.

## Render

Configurar un Web Service:

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn run:app
```

Variables recomendadas:

```text
CORS_ORIGINS=https://tu-usuario.github.io
```

Si usas SQLite en Render y queres conservar datos entre deploys, agregar un Persistent Disk montado en `instance/`. Sin disco persistente, la base puede recrearse al redeploy.

Para desarrollo local:

```bash
pip install -r requirements.txt
python run.py
```

Despues de cambiar templates, regenerar el frontend estatico:

```bash
python build_static.py
```
