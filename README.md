# Sistema de Control de Facturacion

Aplicacion web para control de facturacion con dashboard ejecutivo, carga de datos,
datos maestros, control de registros y backend Flask protegido.

## Guia para Usuarios de Finanzas

Esta aplicacion ayuda a controlar la facturacion mensual comparando lo que se
deberia facturar contra lo que efectivamente se factura. Esta pensada para que
equipos financieros, de control de gestion o responsables de cuentas puedan ver
rapidamente si los importes, horas y ajustes de cada cliente o campania estan
alineados con el objetivo esperado.

En terminos simples, la app responde preguntas como:

- Cuanto se esperaba facturar en un periodo.
- Cuanto se facturo realmente.
- Donde estan los desvios positivos o negativos.
- Que cliente, gerente, jefe de site, campania o tipo de negocio explica esos desvios.
- Si hay penalizaciones, bonos, ajustes u horas que impactan en el resultado final.

### Que hace la app

La app centraliza registros de facturacion y los convierte en reportes faciles
de revisar. Permite cargar datos, consultar un tablero ejecutivo, filtrar la
informacion y exportar resultados para analisis o seguimiento.

Las vistas principales permiten:

- Ver KPIs generales de facturacion, cumplimiento y desvio.
- Revisar la evolucion mensual.
- Comparar total objetivo contra total real.
- Analizar aperturas por cliente, gerencia, jefe de site, campania, sub campania
  y tipo de negocio.
- Detectar alertas o diferencias relevantes.
- Controlar y corregir registros cargados.

### Como funciona en general

1. Se cargan los datos de facturacion, ya sea manualmente o mediante archivo
   Excel/CSV.
2. La app valida los campos principales, como fechas, importes, horas y datos
   comerciales.
3. Cada registro queda asociado a datos maestros: cliente, gerente, jefe de site,
   campania, sub campania y tipo de negocio.
4. Con esa informacion, calcula totales objetivo, totales reales, porcentajes de
   cumplimiento y desvios.
5. El usuario puede filtrar, revisar, comparar y exportar la informacion segun
   el analisis que necesite.


### Para que sirve en el trabajo diario

Sirve como una herramienta de seguimiento y control. En vez de revisar archivos
separados o conciliaciones manuales, el equipo puede consultar una misma fuente,
filtrar por periodo o responsable, encontrar diferencias y exportar la vista
necesaria para compartir o profundizar el analisis.

No reemplaza la definicion financiera del negocio ni la validacion final del
equipo responsable. Su objetivo es ordenar la informacion, aplicar reglas
consistentes y hacer visibles los desvios para tomar decisiones mas rapido.

El proyecto esta en migracion progresiva a Next.js:

- Next.js sirve la experiencia principal en `http://127.0.0.1:3000`.
- Flask mantiene la API, autenticacion, base SQLite y pantallas aun no migradas en `http://127.0.0.1:8009`.

## Estructura

```text
Dashboard/
+-- app/                    # Backend Flask
|   +-- __init__.py         # Configuracion Flask, SQLAlchemy y seguridad
|   +-- models.py           # Modelos de datos
|   +-- routes.py           # Rutas Flask y endpoints API
|   +-- templates/          # Pantallas Flask no migradas o de respaldo
+-- next-app/               # Frontend Next.js
|   +-- app/                # App Router
|   +-- components/         # Componentes React
|   +-- lib/api.js          # Cliente API hacia Flask
+-- scripts/dev.mjs         # Levanta Flask + Next en desarrollo
+-- run.py                  # Entrada Flask
+-- requirements.txt        # Dependencias Python
+-- package.json            # Scripts raiz
+-- dev.ps1                 # Ayuda Windows si PowerShell no encuentra npm
+-- README.md
```

## Requisitos

- Python 3.8+
- pip
- Node.js con npm instalado

En Windows, si `npm` no se reconoce, instalar Node.js o verificar que exista:

```text
C:\Program Files\nodejs\npm.cmd
```

## Instalacion

1. Crear y activar entorno virtual, recomendado:

```powershell
python -m venv venv
venv\Scripts\activate
```

En Linux/Mac:

```bash
python -m venv venv
source venv/bin/activate
```

2. Instalar dependencias Python:

```bash
pip install -r requirements.txt
```

3. Instalar dependencias Next.js:

```bash
npm --prefix next-app install
```

4. Levantar la aplicacion completa:

```bash
npm run dev
```

Este comando levanta:

- Next.js: `http://127.0.0.1:3000`
- Flask/API: `http://127.0.0.1:8009`
- Recarga automatica de Next, Python y templates Flask al guardar cambios.

En Windows, si PowerShell no encuentra `npm`, usar:

```powershell
.\dev.ps1
```

## Scripts

```bash
npm run dev        # Flask + Next
npm run next:dev   # Solo Next.js
npm run flask:dev  # Solo Flask/API
```

Tambien se puede levantar solo Flask con autorecarga:

```powershell
$env:FLASK_RELOAD="1"; $env:TEMPLATES_AUTO_RELOAD="1"; python run.py
```

## Uso Local

Abrir:

```text
http://127.0.0.1:3000
```

Si Next muestra aviso de sesion, iniciar sesion primero en Flask:

```text
http://127.0.0.1:8009/login
```

Luego volver a:

```text
http://127.0.0.1:3000
```

Durante la migracion, las pantallas no migradas siguen disponibles en:

```text
http://127.0.0.1:8009
```

## Funcionalidad

### Dashboard

- KPIs principales: total facturado, total teorico, desvio y cumplimiento.
- Grafico de evolucion mensual.
- Tabla resumen por mes.
- Filtros por mes, cliente, gerente, jefe de site, campania, sub campania y tipo de negocio.
- Agrupacion por cliente.
- Alertas de cumplimiento, desvio y horas sobre objetivo.
- Exportacion a Excel respetando filtros activos.

### Carga de Datos

- Carga manual de registros.
- Carga masiva desde plantilla Excel/CSV.
- Validaciones de importes y horas.
- Deteccion de registros existentes al importar.
- Alerta antes de reemplazar datos existentes.
- La verificacion de reemplazo usa coincidencia exacta por:

```text
fecha + cliente + gerente + jefe de site + campania + sub campania
```

### Datos Maestros

- Alta de asociaciones comerciales.
- Edicion y eliminacion con confirmacion de contrasena.
- Filtros para ubicar rapido asociaciones por cliente, gerente, jefe de site, campania, sub campania y tipo de negocio.
- Al editar una asociacion, se actualizan las cargas vinculadas.
- Al eliminar una asociacion, se eliminan las cargas vinculadas.

### Control

- Tabla detallada de registros.
- Filtros comerciales, incluido tipo de negocio.
- Edicion y eliminacion con confirmacion de contrasena.
- Exportacion a Excel.
- Penalizaciones tratadas como descuento: aunque se carguen positivas, se restan del total facturado.

### Matriz de Proyecciones

- Proyección mensual por cliente y campaña.
- Cliente y campaña se toman de datos maestros existentes.
- El usuario carga año, mes, dotación requerida, horas requeridas y porcentaje de cumplimiento.
- Las horas proyectadas se calculan como `horas requeridas * porcentaje de cumplimiento / 100`.
- Este módulo permite acentos y la letra `Ñ/ñ` en los textos visibles y en los valores de cliente/campaña.

## Seguridad

- Flask escucha solo en `127.0.0.1` por defecto mediante `FLASK_HOST=127.0.0.1`.
- No usar `192.168.x.x:8009` con datos sensibles salvo que exista HTTPS y proteccion de red.
- `FLASK_DEBUG` queda apagado por defecto.
- La clave local de pruebas solo se acepta si se configura `DEV_ACTION_KEY`.
- CORS queda limitado a `127.0.0.1` y `localhost` en los puertos permitidos.
- Cookies de sesion con `HttpOnly`, `SameSite=Lax` y vencimiento configurable.
- Headers de seguridad: CSP, `X-Frame-Options`, `nosniff`, `Referrer-Policy` y `Permissions-Policy`.
- Acciones `POST`, `PUT`, `PATCH` y `DELETE` requieren token CSRF.
- Cambios sensibles requieren permisos y confirmacion con contrasena.
- Usuarios e historial quedan restringidos al rol `administrador`.
- Logout usa `POST` con CSRF.
- Login con limite de intentos fallidos por IP/email.
- Cargas de archivos limitadas con `MAX_CONTENT_LENGTH`.

Para produccion:

```text
SECRET_KEY=un-secreto-largo
SESSION_COOKIE_SECURE=1
FLASK_DEBUG=0
```

Servir siempre detras de HTTPS.

## Endpoints API Principales

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/api/auth/me` | Usuario actual y CSRF |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/logout` | Logout |
| POST | `/api/cargar` | Cargar nuevo registro |
| POST | `/api/importar_datos` | Importar Excel/CSV |
| GET | `/api/datos` | Obtener registros con filtros |
| GET | `/api/resumen` | Resumen mensual |
| GET | `/api/kpis` | KPIs generales |
| GET | `/api/grafico` | Datos para grafico |
| GET | `/api/filtros` | Opciones dinamicas para filtros |
| GET | `/api/por-cliente` | Resumen por cliente |
| GET | `/api/alertas` | Alertas automaticas |
| GET | `/api/exportar_excel` | Exportar registros filtrados |
| GET | `/api/asignaciones` | Listar asociaciones |
| POST | `/api/asignaciones` | Crear asociacion |
| PUT | `/api/asignaciones/<id>` | Editar/activar/desactivar asociacion |
| DELETE | `/api/asignaciones/<id>` | Eliminar asociacion |
| PUT | `/api/datos/<id>` | Editar registro |
| DELETE | `/api/datos/<id>` | Eliminar registro |

## Variables Utiles

| Variable | Uso |
|----------|-----|
| `FLASK_HOST` | Host Flask. Default: `127.0.0.1` |
| `PORT` / `FLASK_PORT` | Puerto Flask. Dev usa `8009` |
| `FLASK_RELOAD` | Activa autorecarga Flask en desarrollo |
| `TEMPLATES_AUTO_RELOAD` | Recarga templates Flask |
| `NEXT_PUBLIC_API_BASE` | URL publica/local del backend para Next |
| `SESSION_MINUTES` | Minutos de inactividad antes de vencer la sesion. Default: `60` |
| `SECRET_KEY` | Clave de sesion Flask |
| `CORS_ORIGINS` | Origins permitidos |
| `SESSION_COOKIE_SECURE` | Cookie segura en HTTPS |

## Despliegue Multiusuario y Base de Datos

Para uso real por varias personas, la app debe funcionar como una instancia
centralizada:

```text
Usuarios en sus maquinas
  |
  | navegador web
  v
Servidor central Linux o Windows
  |
  v
Base de datos central
```

Cada usuario trabaja desde su navegador. No se debe instalar una base local por
persona, porque eso genera informacion separada, diferencias entre usuarios y
perdida de trazabilidad.

La base recomendada para produccion es PostgreSQL. SQLite queda solo para
desarrollo local o pruebas.

### Configuracion de Base

Linux o Windows con PostgreSQL:

```env
DATABASE_URL=postgresql+psycopg://dashboard_user:password_seguro@localhost:5432/dashboard_facturacion
SECRET_KEY=clave_larga_segura
SESSION_COOKIE_SECURE=1
FLASK_DEBUG=0
CORS_ORIGINS=https://tu-dominio.com
NEXT_PUBLIC_API_BASE=https://tu-dominio.com
```

Windows local o pruebas con SQLite:

```env
DATABASE_URL=sqlite:///facturacion.db
```

En SQLite local, el archivo queda dentro de:

```text
instance/facturacion.db
```

### Tabla Principal

Tabla: `facturacion_2026`

```sql
CREATE TABLE facturacion_2026 (
    id SERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    mes VARCHAR(20) NOT NULL,
    cliente VARCHAR(100) NOT NULL,
    gerente VARCHAR(100),
    jefe_site VARCHAR(100),
    campania VARCHAR(100),
    subcampania VARCHAR(100),
    tipo_negocio VARCHAR(100),
    tipo_jornada VARCHAR(50) NOT NULL,
    horas_objetivo DOUBLE PRECISION NOT NULL,
    horas_facturadas DOUBLE PRECISION NOT NULL,
    horas_penalizadas DOUBLE PRECISION DEFAULT 0,
    valor_hora_objetivo DOUBLE PRECISION,
    valor_hora DOUBLE PRECISION NOT NULL,
    tarifacion DOUBLE PRECISION,
    importe_fijo DOUBLE PRECISION,
    variable_objetivo DOUBLE PRECISION DEFAULT 0,
    variable_productivo DOUBLE PRECISION DEFAULT 0,
    bonos DOUBLE PRECISION DEFAULT 0,
    penalizaciones DOUBLE PRECISION DEFAULT 0,
    netx_gen DOUBLE PRECISION DEFAULT 0,
    otros DOUBLE PRECISION DEFAULT 0
);
```

Nota: el campo tecnico se llama `netx_gen` por compatibilidad con la base
existente, pero en la interfaz y reportes se muestra como `Next Gen`.

### Datos Maestros

Tabla: `asignaciones_comerciales`

```sql
CREATE TABLE asignaciones_comerciales (
    id SERIAL PRIMARY KEY,
    cliente VARCHAR(100) NOT NULL,
    gerente VARCHAR(100) NOT NULL,
    jefe_site VARCHAR(100) NOT NULL,
    campania VARCHAR(100) NOT NULL,
    subcampania VARCHAR(100) NOT NULL,
    tipo_negocio VARCHAR(100),
    activa BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### Usuarios

Tabla: `usuarios`

```sql
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    email VARCHAR(160) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol VARCHAR(30) NOT NULL DEFAULT 'usuario',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Roles usados por la app:

```text
administrador
superusuario
usuario
```

### Justificaciones

Tabla: `justificaciones_ajustes`

```sql
CREATE TABLE justificaciones_ajustes (
    id SERIAL PRIMARY KEY,
    facturacion_id INTEGER NOT NULL REFERENCES facturacion_2026(id),
    tipo VARCHAR(30) NOT NULL,
    cantidad DOUBLE PRECISION DEFAULT 1,
    precio DOUBLE PRECISION DEFAULT 0,
    importe DOUBLE PRECISION NOT NULL,
    descripcion TEXT NOT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Tipos esperados:

```text
bonos
penalizaciones
otros
```

### Historial

Tabla: `historial_cambios`

```sql
CREATE TABLE historial_cambios (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios(id),
    usuario_nombre VARCHAR(120),
    usuario_email VARCHAR(160),
    accion VARCHAR(30) NOT NULL,
    entidad VARCHAR(80) NOT NULL,
    entidad_id VARCHAR(50),
    resumen VARCHAR(255) NOT NULL,
    detalle TEXT,
    antes TEXT,
    despues TEXT,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### Matriz de Proyecciones

Tabla: `matriz_proyecciones`

```sql
CREATE TABLE matriz_proyecciones (
    id SERIAL PRIMARY KEY,
    cliente VARCHAR(100) NOT NULL,
    campania VARCHAR(100) NOT NULL,
    year INTEGER NOT NULL,
    mes VARCHAR(7) NOT NULL,
    dotacion_requerida DOUBLE PRECISION NOT NULL DEFAULT 0,
    horas_requeridas DOUBLE PRECISION NOT NULL DEFAULT 0,
    porcentaje_cumplimiento DOUBLE PRECISION NOT NULL DEFAULT 100,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_matriz_proyecciones_cliente_campania_mes UNIQUE (cliente, campania, mes)
);
```

`horas_proyectadas` no se guarda como columna fisica. La app lo calcula como:

```text
horas_requeridas * porcentaje_cumplimiento / 100
```

### Headers de Importacion

Para cargar datos por Excel/CSV, la plantilla visible espera:

```text
Fecha de carga
Mes facturacion
Cliente
Gerente
Jefe de Site
Campaña
Sub campaña
Tipo de negocio
Tipo de VH
Horas objetivo
Horas facturadas
Horas Penalizacion ADH
Valor hora objetivo
Valor hora facturado
Tarificacion
Importe fijo facturado
Variable Objetivo
Variable Productivo
Bonos
Penalizaciones
Next Gen
Otros
```

Si se arma un CSV con nombres tecnicos, usar:

```text
fecha,mes,cliente,gerente,jefe_site,campania,subcampania,tipo_negocio,tipo_jornada,horas_objetivo,horas_facturadas,horas_penalizadas,valor_hora_objetivo,valor_hora,tarifacion,importe_fijo,variable_objetivo,variable_productivo,bonos,penalizaciones,netx_gen,otros
```

### Recomendacion Operativa

La app puede crear tablas al arrancar con `db.create_all()`, pero para un
entorno productivo conviene administrar cambios de esquema con migraciones
formales. Mantener PostgreSQL centralizado permite que todos los usuarios vean y
actualicen la misma informacion desde sus propias maquinas.

## Produccion

La app completa necesita dos procesos o un despliegue coordinado:

- Frontend Next.js.
- Backend Flask con base de datos persistente.

No alcanza con GitHub Pages para la app completa porque Flask, SQLite y `/api/*` necesitan un proceso Python. Si se usa Render u otro hosting para Flask, configurar una base persistente o un disco persistente para `instance/`.

## Checklist Rapida

- `npm run dev` levanta Next en `3000` y Flask en `8009`.
- `http://127.0.0.1:3000` abre el frontend Next.
- `http://127.0.0.1:8009/login` permite iniciar sesion.
- `POST` sin `X-CSRF-Token` devuelve `403`.
- `POST` con `Origin` externo devuelve `403`.
- `http://192.168.x.x:8009` no responde salvo que configures `FLASK_HOST=0.0.0.0`.
- En produccion, la cookie debe verse como `HttpOnly`, `SameSite=Lax` y `Secure`.
