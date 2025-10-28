# Arquitectura y modelos de datos

Este documento profundiza en la arquitectura modular del monolito FastAPI, describe los componentes clave y detalla cómo se persisten los datos. Incluye referencias directas a los módulos del repositorio para que puedas inspeccionar el código al mismo tiempo que lees la explicación.

## Visión general del backend

El backend está diseñado como un monolito organizado por dominios. Cada paquete ofrece una responsabilidad clara y se comunica mediante contratos Python bien definidos:

- **Configuración**. `app/config.py` centraliza variables de entorno (BD, Redis, SMTP, Moodle).【F:app/config.py†L1-L26】
- **Registro y contexto**. `app/logging.py` configura logging estructurado y funciones auxiliares para propagar IDs de job.
- **API REST**. Los routers en `app/api/` exponen operaciones CRUD y endpoints de orquestación (`/courses`, `/students`, `/notifications`, `/uploads`, `/workflows`).【F:app/api/courses.py†L1-L199】【F:app/api/workflows.py†L1-L128】
- **Servicios de dominio**. `app/services/` empaqueta lógica reutilizable (serialización de matrículas, evaluación de reglas, sincronización con Moodle).【F:app/services/enrollments.py†L1-L110】
- **Ingesta**. `app/modules/ingest/` contiene funciones que validan XLSX, aplican mapeos YAML y crean entidades idempotentes.【F:app/modules/ingest/course_loader.py†L42-L142】
- **Reglas**. `app/rules/engine.py` evalúa expresiones declarativas y ofrece `RuleSet.from_yaml` para cargar reglas desde ficheros.【F:app/rules/engine.py†L53-L81】
- **Workflows**. `app/workflows/runner.py` interpreta playbooks YAML, aplica mapeos y construye el contexto que consumirá el dispatcher.【F:app/workflows/runner.py†L21-L132】
- **Notificaciones**. `app/notify/dispatcher.py` resuelve adaptadores, respeta quiet hours y registra auditorías. Los adaptadores viven en `app/notify/adapters/` (SMTP, CLI, HTTP).【F:app/notify/dispatcher.py†L90-L224】
- **Colas y scheduler**. `app/queue.py` expone la conexión Redis/RQ compartida y `app/jobs/scheduler.py` encapsula APScheduler con soporte para quiet hours.【F:app/queue.py†L1-L14】【F:app/jobs/scheduler.py†L1-L56】
- **Sincronización Moodle**. `app/jobs/moodle_sync.py` y `app/services/sync_courses.py` componen el flujo para pasar de ficheros XLSX a Web Services oficiales sin duplicar lógica.【F:app/jobs/moodle_sync.py†L1-L47】【F:app/services/sync_courses.py†L1-L123】

## Modelo de datos relacional

El esquema se define en `app/models.py` usando SQLAlchemy 2.0. Las tablas cubren el ciclo completo de cursos, alumnado y notificaciones:

- `courses`: metadatos del curso, horas requeridas, fecha límite y origen (`xlsx` o `moodle`).【F:app/models.py†L57-L82】
- `students`: datos personales básicos y caducidad del certificado vigente.【F:app/models.py†L84-L101】
- `enrollments`: relación curso ↔ alumno con horas cursadas, estado y fechas clave.【F:app/models.py†L103-L132】
- `notifications`: auditoría de avisos, canal, adaptador, estado y payload serializado.【F:app/models.py†L144-L196】
- `jobs` y `job_events`: trazabilidad de ejecuciones para reintentos y análisis.【F:app/models.py†L198-L262】
- `uploaded_files`: histórico de cargas XLSX (tamaño, hash, autor).【F:app/models.py†L40-L55】

Este diseño permite reconstruir cualquier envío y ofrece métricas por curso, matrícula o canal simplemente consultando las tablas agregadas.

## Motor de reglas y workflows declarativos

Las reglas viven en ficheros YAML (`app/rules/rulesets/`). El motor `RuleSet` carga cada regla con un identificador, descripción y expresión Python limitada. El `WorkflowRunner` combina reglas con mapeos y acciones definidas en `workflows/playbooks/*.yaml`:

1. Carga el playbook y valida rutas relativas a la carpeta `workflows/`.
2. Convierte el XLSX de origen en un DataFrame, renombra columnas según el mapeo y limpia tipos.
3. Evalúa las reglas para cada fila y crea `EvaluatedRow` con resultados booleanos.
4. Invoca al dispatcher con la lista de acciones (por ejemplo, `notify` con canal `email` o `whatsapp`).

Gracias a este enfoque declarativo, las reglas pueden versionarse sin tocar el código y los operarios pueden ejecutar simulaciones cambiando únicamente los YAML.【F:app/workflows/runner.py†L21-L132】

## Notificaciones y adaptadores

El `NotificationDispatcher` recibe filas evaluadas y decide qué acciones ejecutar. Sus responsabilidades principales son:

- Renderizar plantillas y contexto (`row`, `rule_results`) para cada acción.
- Respetar `quiet_hours` mediante el scheduler y registrar los saltos por ventana de silencio.【F:app/notify/dispatcher.py†L147-L196】
- Encolar trabajos en Redis/RQ cuando existe una cola configurada, propagando `job_id` y `job_name` para la trazabilidad.【F:app/notify/dispatcher.py†L197-L224】
- Persistir auditorías mediante un repositorio configurable (`NotificationAuditRepository`).

Los adaptadores concretos (SMTP, CLI, HTTP) comparten la interfaz `send(payload)` y se pueden implementar en otros lenguajes siempre que respeten el contrato JSON descrito en la guía de extensibilidad.

## Integración con Moodle

La transición de ficheros XLSX a Web Services está prevista desde el diseño:

- El cliente REST (`MoodleRESTClient`) encapsula autenticación por token y parseo de respuestas, detectando automáticamente los errores específicos que devuelve Moodle.【F:app/connectors/moodle/rest.py†L1-L62】
- `CourseSyncService` decide si debe leer un XLSX local (`source_path`) o realizar llamadas REST según el flag `moodle_api_enabled` en la configuración. El resultado se aplica al mismo pipeline de ingesta y workflows, lo que evita duplicidades.【F:app/services/sync_courses.py†L1-L123】
- `schedule_moodle_sync_jobs` permite planificar sincronizaciones periódicas que, una vez completadas, disparan el playbook indicado para mantener notificaciones y reportes actualizados.【F:app/jobs/moodle_sync.py†L1-L47】

## Interfaz web y consumo de la API

El frontend Next.js (carpeta `frontend/`) actúa como un panel para operarios. Consume los endpoints documentados en OpenAPI y muestra:

- **Carga y validación** de XLSX (`/uploads`).
- **Resumen de cursos** y métricas agregadas (`/courses`).
- **Detalle de alumnos** con reglas incumplidas (`/students/non-compliance`).
- **Historial de notificaciones** con filtros (`/notifications`).
- **Ejecución de playbooks** en modo simulación o ejecución real (`/workflows/dry-run` y `/workflows/run`).

Aunque la UI no está detallada en este documento, la API está preparada para ser consumida desde aplicaciones web o móviles gracias a las respuestas JSON estructuradas y a los contadores precomputados.

Con esta panorámica arquitectónica ya puedes navegar el repositorio con criterio, identificar dónde implementar nuevas reglas o adaptadores y entender qué tablas debes consultar para obtener métricas o auditorías.
