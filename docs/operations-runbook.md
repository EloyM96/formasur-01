# Operaciones diarias y runbook

Este runbook guía a cualquier operario o responsable académico a través de las tareas habituales del sistema. Las instrucciones están pensadas para personas sin experiencia previa en desarrollo, pero incluyen enlaces a los módulos por si un perfil técnico necesita profundizar.

## 1. Preparar el entorno

1. **Crear fichero de variables**. Copia la plantilla de entorno y rellena valores mínimos (`DATABASE_URL`, `REDIS_URL`, credenciales SMTP si vas a enviar correos reales):
   ```bash
   cp .env.example .env
   ```
2. **Levantar servicios básicos**. Ejecuta Docker Compose para disponer de Postgres, Redis y la API FastAPI:
   ```bash
   docker compose up -d
   ```
   Si prefieres entorno local, puedes lanzar la API con `uvicorn app.main:app --reload` desde un virtualenv.
3. **Abrir la interfaz web**. Accede a `http://localhost:3000` (Next.js) o utiliza herramientas como `curl`/Postman para probar los endpoints.

> La configuración que consume la API se encuentra en `app/config.py`. Ahí se activan/desactivan integraciones como Moodle y se definen URLs de Redis o SMTP.【F:app/config.py†L1-L26】

## 2. Cargar un XLSX de Moodle

1. Desde la UI, selecciona “Subir XLSX” o realiza una petición `POST /uploads` con el fichero como multipart.
2. El backend validará la extensión y el tamaño antes de guardarlo en disco y registrar la subida en `uploaded_files`. Los metadatos se devuelven como respuesta JSON (total de filas, errores detectados, columnas faltantes).【F:app/api/uploads.py†L28-L88】
3. Si hay columnas ausentes, corrige el XLSX según el mapeo `workflows/mappings/moodle_prl.yaml` y vuelve a subirlo.【F:workflows/mappings/moodle_prl.yaml†L1-L9】

## 3. Revisar la simulación (dry-run)

1. Ve a la opción “Simular” en la UI o invoca `POST /workflows/dry-run` indicando el playbook a ejecutar y si deseas sobreescribir la ruta del XLSX.
2. El `WorkflowRunner` cargará el playbook, aplicará el mapeo y evaluará las reglas para cada fila. La respuesta incluye total de filas, acciones que coinciden y desglose por canal.【F:app/workflows/runner.py†L21-L93】
3. Usa los contadores para decidir si procede ejecutar el envío real. Ninguna notificación se manda en modo *dry-run*.

## 4. Ejecutar un playbook en vivo

1. Lanza `POST /workflows/run` con el nombre del playbook y confirma la ejecución.
2. El dispatcher comprobará si estás fuera de las quiet hours definidas en el YAML. Si estás dentro del horario restringido, el sistema registrará el salto y no encolará notificaciones.【F:app/notify/dispatcher.py†L147-L196】【F:app/jobs/scheduler.py†L1-L56】
3. En caso contrario, cada acción `notify` se encola en Redis/RQ junto con un identificador de job. Puedes monitorizar la cola con `rq info` o revisando la tabla `jobs` en la base de datos.

## 5. Consultar resultados y auditoría

1. **Panel de cursos** (`GET /courses`): muestra métricas agregadas por curso (matrículas, incumplimientos, contadores por canal).【F:app/api/courses.py†L49-L199】
2. **Detalle de matrículas** (`GET /courses/{id}`): lista cada alumno, sus violaciones de reglas y el historial de avisos relacionados.【F:app/api/courses.py†L149-L226】
3. **Historial global** (`GET /notifications`): filtra por canal, estado, playbook o fechas. Ideal para exportar registros o auditar incidencias.【F:app/api/notifications.py†L1-L87】
4. **Eventos de job** (`jobs`, `job_events`): consulta estas tablas para diagnosticar reintentos o errores de adaptadores.【F:app/models.py†L198-L262】

## 6. Activar sincronización automática con Moodle

1. Configura las variables `MOODLE_API_ENABLED`, `MOODLE_TOKEN` y `MOODLE_REST_BASE_URL` en `.env`.
2. Define los jobs que quieras programar pasando instancias de `MoodleSyncJobDefinition` al scheduler. Cada job indica el playbook que debe ejecutarse tras sincronizar datos.【F:app/jobs/moodle_sync.py†L1-L47】
3. `CourseSyncService` detectará automáticamente el modo (XLSX o API REST) y devolverá un resumen de cursos sincronizados. Ese resumen se loguea y permite hacer *dry-run* si se desea.【F:app/services/sync_courses.py†L1-L123】
4. Revisa los logs estructurados (`app/logging.py`) para confirmar que la sincronización ha finalizado y que se ha lanzado el playbook esperado.

## 7. Recuperación ante fallos

- **Errores en adaptadores**: aparecerán como `status="error"` en `notifications` y en `job_events`. El dispatcher incluye el mensaje del adaptador para facilitar la diagnosis.【F:app/notify/dispatcher.py†L197-L224】
- **Quiet hours**: si la ejecución cae dentro de la ventana de silencio, el resumen indicará `skipped_quiet_hours`. Puedes relanzar el playbook fuera de horario o ajustar la configuración.
- **Reprocesar XLSX**: basta con subir un fichero corregido; la ingesta es idempotente y actualiza registros existentes sin duplicados.【F:app/modules/ingest/course_loader.py†L43-L215】

## 8. Checklist rápido antes de entregar resultados

- [ ] XLSX validado y sin columnas faltantes.
- [ ] Simulación revisada y aprobada por el responsable.
- [ ] Ejecución realizada fuera de quiet hours o con excepción autorizada.
- [ ] Contadores y auditoría verificados en `/notifications`.
- [ ] Logs sin errores pendientes y workers RQ sin jobs fallidos.

Siguiendo este runbook cualquier operario puede preparar datos, lanzar envíos y documentar los resultados sin necesidad de acceder directamente a la base de datos ni conocer los detalles internos del código.
