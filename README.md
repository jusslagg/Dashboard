# Sistema de Control de Facturacion

Aplicacion web para control de facturacion con dashboard ejecutivo, carga de datos,
datos maestros, control de registros y backend Flask protegido.

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
