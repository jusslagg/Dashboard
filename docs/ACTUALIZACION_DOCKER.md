# Actualizaciones de Docker desde GitHub

Configuración del 27 de noviembre de 2026.

## Publicación de imágenes

El workflow `.github/workflows/docker.yml` se ejecuta con cada push de una rama.
Construye y prueba el contenedor antes de publicar en
`ghcr.io/jusslagg/dashboard`. Cada commit recibe una etiqueta `sha-<commit>`.
También se publica una etiqueta con el nombre de rama normalizado y `latest`
para la rama predeterminada del repositorio.

GitHub Actions usa `GITHUB_TOKEN` con permiso de escritura de paquetes.
El acceso al paquete se administra desde GitHub Packages. Antes de compartirlo,
comprobar su visibilidad y los permisos del destinatario.

## Actualización de esta PC

La tarea programada `Dashboard-Docker-AutoUpdate` comprueba cada minuto la rama
configurada en `.cache/docker-auto/config.json`. Inicialmente se utiliza
`integrar-proforma-soporte`, la rama de la versión operativa.

El script `scripts/actualizar_docker.py` descarga el commit publicado en un
repositorio aislado. Construye una imagen por commit y prueba su healthcheck
con una base de prueba. Antes de actualizar el servicio real crea una copia
consistente de SQLite en `.cache/docker-auto/backups`. Compose mantiene
el volumen de datos y la clave de sesión de `.env.docker`.

La tarea requiere una sesión iniciada en Windows, Docker Desktop funcionando
y acceso al remoto GitHub. Los archivos sin commit y los commits sin push
quedan fuera de la actualización. Un cambio en otra rama requiere modificar
la rama configurada.

El log está en `.cache/docker-auto/actualizaciones.log`. `estado.json` registra
el último commit publicado correctamente en el Docker local. Si el despliegue
falla, revisar el log y `docker compose --env-file .env.docker logs web`.
La revisión previa del contenedor evita desplegar errores de arranque básicos.
La aceptación funcional de cada cambio sigue siendo necesaria.

## Control manual

Para instalarla en esta PC o cambiar la rama, desde PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File scripts/configurar_actualizacion_docker.ps1 -Branch integrar-proforma-soporte
```

El instalador usa la identidad de la sesión actual y el Python de `.venv`.

```powershell
Start-ScheduledTask -TaskName Dashboard-Docker-AutoUpdate
Disable-ScheduledTask -TaskName Dashboard-Docker-AutoUpdate
Enable-ScheduledTask -TaskName Dashboard-Docker-AutoUpdate
Get-ScheduledTaskInfo -TaskName Dashboard-Docker-AutoUpdate
```

Para migrar a PostgreSQL debe incorporarse el respaldo del servidor antes de
activar este actualizador. El script actual exige SQLite para realizar el
respaldo previo.
