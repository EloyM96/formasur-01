# Introducción y visión general

Este documento resume la finalidad del proyecto y explica, con un lenguaje accesible, cómo circula la información desde que se recibe un fichero XLSX hasta que se generan notificaciones y reportes. Se recomienda leerlo completo antes de profundizar en otros apartados.

## ¿Qué problema resuelve prl-notifier?

La herramienta automatiza el seguimiento de la formación en prevención de riesgos laborales. Parte de los listados exportados desde Moodle u otras plataformas, detecta incidencias (por ejemplo, cursos caducados u horas pendientes) y sugiere avisos multicanal para el alumnado y el personal coordinador. Todo ello queda registrado para disponer de métricas fiables y para poder auditar el proceso.

## Mapa de carpetas esenciales

El repositorio sigue una estructura monolítica en Python que agrupa el backend FastAPI, los conectores, los playbooks declarativos y la interfaz web (Next.js). Esta es la jerarquía que conviene tener presente:

- `app/main.py`: punto de entrada FastAPI, agrupa los routers de cursos, estudiantes, notificaciones, cargas y workflows.【F:app/main.py†L1-L29】
- `app/api/`: endpoints REST accesibles por la interfaz web o integraciones internas.
- `app/modules/ingest/`: utilidades para validar XLSX y transformarlos en entidades internas.【F:app/modules/ingest/xlsx_importer.py†L1-L67】
- `app/modules/rules/` y `app/rules/`: motor declarativo que interpreta reglas en YAML.【F:app/rules/engine.py†L1-L81】
- `app/notify/`: despacho de avisos, adaptadores por canal y auditoría de entregas.【F:app/notify/dispatcher.py†L1-L134】
- `app/jobs/`: scheduler y jobs relacionados con Moodle o ejecuciones periódicas.【F:app/jobs/moodle_sync.py†L1-L47】
- `app/services/`: lógica de dominio reutilizable por los routers (serialización, métricas, sincronizaciones).【F:app/services/enrollments.py†L1-L78】
- `app/connectors/`: clientes para servicios externos como Moodle REST/SOAP.【F:app/connectors/moodle/rest.py†L1-L62】
- `workflows/`: playbooks y mapeos declarativos (YAML) que definen qué acciones ejecutar y cómo se interpretan los ficheros de origen.
- `frontend/`: shell Next.js preparado para cargar los datos expuestos por la API.

## Flujo de datos de extremo a extremo

1. **Recepción del XLSX**. Un operario carga el fichero mediante `POST /uploads`. El backend valida el formato, guarda el binario y genera un resumen con filas de ejemplo y columnas faltantes.【F:app/api/uploads.py†L28-L88】
2. **Mapeo y normalización**. El importador lee el XLSX con `pandas`, contrasta columnas con `workflows/mappings/moodle_prl.yaml` y genera un `ImportSummary` que indica si la carga es válida y qué datos deben revisarse.【F:app/modules/ingest/xlsx_importer.py†L31-L67】
3. **Persistencia**. El servicio de ingesta convierte cada fila en cursos, estudiantes y matrículas, garantizando idempotencia y guardando metadatos útiles (horas, caducidades, teléfono).【F:app/modules/ingest/course_loader.py†L43-L215】
4. **Evaluación de reglas**. Una vez persistidos los datos, el motor `RuleSet` analiza cada matrícula con reglas declarativas (`rulesets/*.yaml`) para detectar infracciones o eventos relevantes.【F:app/rules/engine.py†L53-L81】【F:app/workflows/runner.py†L64-L115】
5. **Orquestación de workflows**. Los playbooks en `workflows/playbooks/` describen cuándo ejecutar reglas, qué archivos usar y qué acciones se deben realizar. El `WorkflowRunner` carga el playbook, aplica el mapeo y prepara las filas evaluadas.【F:app/workflows/runner.py†L21-L93】
6. **Despacho de notificaciones**. El `NotificationDispatcher` interpreta las acciones `notify`, respeta las ventanas de silencio del scheduler y encola trabajos en Redis/RQ o realiza envíos directos según configuración.【F:app/notify/dispatcher.py†L90-L190】【F:app/jobs/scheduler.py†L1-L56】
7. **Auditoría y métricas**. Cada envío registra un rastro en base de datos (`notifications`, `jobs`, `job_events`). Los servicios de cursos agregan estos datos para mostrar contadores y estados a la UI.【F:app/services/enrollments.py†L80-L110】【F:app/api/courses.py†L49-L199】

El flujo anterior funciona tanto en modo *dry-run* (simulación) como en ejecución real. La UI web consume los endpoints REST para mostrar resúmenes, detalles por alumno y el historial de notificaciones.

## Roles y perfiles

- **Operarios**: suben XLSX, revisan simulaciones y aprueban envíos. Solo necesitan seguir los pasos descritos en el [runbook operativo](./operations-runbook.md).
- **Equipo docente / coordinación**: revisa métricas agregadas y auditorías para comprobar cumplimiento.
- **Becarios y desarrolladores**: amplían reglas, playbooks y adaptadores. El [manual de extensibilidad](./extensibility-guide.md) les proporciona contratos JSON y ejemplos de integración con Java.

Con esta visión general, ya sabes dónde reside cada pieza y cómo se conectan entre sí. Los siguientes documentos profundizan en los detalles técnicos, operativos y de integración.
