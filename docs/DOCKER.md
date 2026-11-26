# Entrega y ejecución con Docker

Este contenedor ejecuta el sistema Flask completo: dashboard, Facturación,
Proyectados, usuarios, importaciones y exportaciones. Usa Waitress mediante
`python run.py`, escucha en el puerto interno **8009** y corre con UID/GID
**10001**, sin permisos de administrador. El frontend Next.js que está en
migración no es necesario para estas pantallas y no se incluye en esta imagen.

La imagen contiene el código, los recursos web, la configuración versionada y
la documentación utilizada por las pantallas de ayuda. La base actual, los
usuarios, las contraseñas de conexión y los archivos `.env` se entregan por
separado. La imagen no contiene la base de esta computadora.

## 1. Prueba local

Requisitos: Docker Engine o Docker Desktop con contenedores Linux y el plugin
Docker Compose. En Docker Desktop, iniciar el motor antes de ejecutar comandos.
Los comandos se ejecutan desde la raíz del proyecto.

```powershell
Copy-Item .env.docker.example .env.docker
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Pegar el resultado como `SECRET_KEY` en `.env.docker` y conservarlo entre
reinicios. No usar el valor de ejemplo de `.env.example`. Si Python no está en
el PATH de esta PC, usar `.venv/Scripts/python.exe` en su lugar.

```powershell
docker compose --env-file .env.docker config --quiet
docker compose --env-file .env.docker build --pull
```

Antes del primer arranque, elegir una de estas opciones:

- **Instalación nueva:** continuar con `up`. La aplicación crea el esquema y
  permite crear el primer administrador desde el navegador.
- **Conservar la información actual:** realizar primero el traslado de la base
  indicado en la sección 3. No crear un administrador nuevo en el destino.

```powershell
docker compose --env-file .env.docker up -d
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs --tail=100 web
```

Abrir **http://127.0.0.1:8010**. El puerto 8010 del host evita interferir con la
aplicación local que ya corre en 8009. Se puede cambiar con `DASHBOARD_PORT`.
El estado debe pasar a `healthy`: la comprobación consulta `/login`, incluida
su conexión a la base, sin importar nuevamente la aplicación.

El ejemplo usa `APP_ENV=development` para permitir la prueba por HTTP;
**el servidor sigue siendo Waitress y el depurador está desactivado**.

Para probar desde la misma Wi-Fi, establecer `DASHBOARD_BIND_IP=0.0.0.0`, volver
a ejecutar `up -d` y abrir `http://IP-DE-LA-PC:8010`. El firewall y la red de la
empresa deben permitir ese acceso.

## 2. Datos persistentes y actualizaciones

SQLite vive en `/opt/dashboard/instance/facturacion.db`, sobre el volumen
`dashboard_data`. Compose le agrega el nombre del proyecto como prefijo.
Las rutas `/opt/dashboard/app`, `/opt/dashboard/config` y `/opt/dashboard/docs`
pertenecen a la imagen; no se monta el código de esta PC.

```powershell
docker compose --env-file .env.docker up -d --build
docker compose --env-file .env.docker restart web
docker compose --env-file .env.docker down
```

Estos comandos conservan el volumen. **`down -v` elimina el volumen y su base**;
no utilizarlo para actualizar el sistema. Mantener el mismo nombre del proyecto
Compose para seguir usando el mismo volumen.

Antes de actualizar la imagen, hacer un respaldo: el arranque existente de la
aplicación aplica ajustes de esquema automáticamente. Volver a una imagen
anterior no revierte esos cambios de base.

Para obtener un respaldo consistente de SQLite con el contenedor iniciado:

```powershell
docker compose --env-file .env.docker exec web python -c "import sqlite3; s=sqlite3.connect('file:/opt/dashboard/instance/facturacion.db?mode=ro',uri=True); d=sqlite3.connect('/tmp/dashboard-backup.db'); s.backup(d); d.close(); s.close()"
docker compose --env-file .env.docker cp web:/tmp/dashboard-backup.db ./dashboard-backup.db
```

Mover el respaldo al almacenamiento autorizado por la empresa. Si se usa
PostgreSQL, utilizar el respaldo/restauración del servidor PostgreSQL en lugar
de estos comandos de SQLite.

## 3. Llevar la base existente al volumen

Esta versión agrega `configuracion_operativa` para las preferencias de usuario. El migrador admite una fuente anterior sin esa tabla y la crea vacía en destino; las tablas de negocio continúan siendo obligatorias. El año inicial viene de `APP_DEFAULT_YEAR` hasta que un administrador lo guarda desde el Centro de administración.

El traslado no se realiza durante el build ni se publica con la imagen. Incluye
usuarios, permisos, historial y datos operativos. Usar un destino nuevo/vacío.
Coordinar una pausa de edición durante el traslado y conservar un respaldo del
origen antes del cambio.

Con `DATABASE_URL=sqlite:////opt/dashboard/instance/facturacion.db`, construir la
imagen como en la sección 1 y ejecutar **antes de `up`**:

```powershell
docker compose --env-file .env.docker run --rm --no-deps --volume "./instance:/source:ro" web python scripts/migrar_base_datos.py --source-url sqlite:////source/facturacion.db --target-url sqlite:////opt/dashboard/instance/facturacion.db
```

El origen se monta en modo lectura y se usa el migrador ya existente del
proyecto. Verifica esquema, filas y huellas de contenido. El resultado esperado
es `MIGRACIÓN OK`; si el destino contiene datos, el migrador rechaza la copia.
No mezclar un destino ya utilizado con la base de origen.

Después:

```powershell
docker compose --env-file .env.docker up -d
```

Para PostgreSQL corporativo, configurar `DATABASE_URL` y seguir
[la entrega a Desarrollo y DBA](ENTREGA_DESARROLLO.md), usando las variables de
conexión del entorno autorizado. `localhost` dentro del contenedor apunta al
propio contenedor, no al servidor de base de datos ni a esta computadora.

## 4. Despliegue de empresa con HTTPS

Configurar en el entorno del servidor o en un `.env.docker` privado:

```dotenv
APP_ENV=production
SECRET_KEY=<secreto-largo-unico-y-persistente>
CORS_ORIGINS=https://dashboard.empresa.example
DASHBOARD_BIND_IP=127.0.0.1
DASHBOARD_PORT=8010
DATABASE_URL=<conexion-aprobada-por-la-empresa>
```

Colocar el proxy HTTPS de la empresa delante del puerto 8010. Si el proxy corre
en otro contenedor, utilizar su red interna o ajustar la publicación del puerto
según la infraestructura. El modo `production` exige una clave válida y activa
las cookies `Secure`: el acceso de usuarios debe hacerse mediante **HTTPS**,
incluso si el enlace entre proxy y aplicación usa HTTP.

La configuración SQLite admite una sola instancia de esta aplicación. Antes de
replicar el servicio, coordinar PostgreSQL, migraciones y el control de intentos
de acceso entre procesos; no ejecutar varias réplicas sobre el archivo SQLite.

## 5. Publicar la imagen en el registro de la empresa

Reemplazar las rutas y la versión por los datos asignados por infraestructura.
Autenticarse mediante el mecanismo aprobado; no guardar tokens en el proyecto.

```powershell
docker build -t registro.empresa.example/equipo/dashboard-facturacion:1.0.0 .
docker login registro.empresa.example
docker push registro.empresa.example/equipo/dashboard-facturacion:1.0.0
```

En el servidor, definir `DASHBOARD_IMAGE` con esa misma ruta y versión. Entregar
`compose.yaml` y un archivo de entorno privado configurado para ese servidor:

```powershell
docker compose --env-file .env.docker pull web
docker compose --env-file .env.docker up -d --no-build
```

Para una entrega sin registro, exportar la imagen y cargarla en el destino:

```powershell
docker image save -o dashboard-facturacion.image.tar dashboard-facturacion:local
docker image load -i dashboard-facturacion.image.tar
```

La imagen debe construirse para la arquitectura del servidor de destino. La
base y los secretos se trasladan por los canales internos autorizados, separados
del código y de la imagen.

## 6. Aceptación antes de habilitar usuarios

Entrega actualizada el 26 de noviembre de 2026. El paquete incluye los recursos
compartidos de usabilidad y el lector de cierres CAT. La guía de Personal y el
checklist están actualizados en `docs/guia_usuario.html` y su PDF.
Ejecutar los controles de Personal y handoff enumerados en
`docs/ENTREGA_DESARROLLO.md` antes de aceptar la versión.

1. `docker compose ... ps` muestra el servicio `healthy` y sin reinicios.
2. Se puede iniciar sesión y funcionan los permisos por rol.
3. Facturación, Proyectados y la apertura por clientes/campañas concilian con
   el origen para el mismo período y los mismos filtros.
4. Importación y exportación Excel funcionan con un archivo de prueba.
5. Un reinicio conserva los datos; el respaldo se puede restaurar en un
   entorno separado.
6. HTTPS permite conservar la sesión en modo `production`.

**Validación de esta entrega:** imagen Linux/amd64 construida el 26 de noviembre
de 2026. Se verificaron arranque real, healthcheck, usuario 10001:10001,
alta inicial, sesión segura, pantallas y PDF. Los datos de prueba persistieron
después de reiniciar el contenedor con un volumen aislado.
La migración a PostgreSQL y la aceptación en el servidor destino quedan a cargo
de Desarrollo.

La imagen se entrega como `dashboard-facturacion-2026-11-26.image.tar`,
acompañada por su SHA-256. Para importarla en otro equipo

```powershell
docker load -i dashboard-facturacion-2026-11-26.image.tar
```

Configurar `DASHBOARD_IMAGE=dashboard-facturacion:2026-11-26` en el archivo de
ambiente de Compose y arrancar con
`docker compose --env-file .env.docker up -d --no-build`.
La base operativa y los secretos se configuran por separado.

Referencias de configuración: [variables de entorno de Compose](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
y [volúmenes persistentes](https://docs.docker.com/reference/compose-file/volumes/).
