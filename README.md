# prl-notifier

## Objetivo del MVP

El objetivo del MVP de **prl-notifier** es automatizar el seguimiento de la prevención de riesgos laborales mediante:

- Ingesta de hojas de cálculo XLSX exportadas desde Moodle con la información del alumnado y su estado en los cursos obligatorios.
- Aplicación de un motor de reglas declarativo que permita definir condiciones de cumplimiento y próximos hitos.
- Emisión de avisos multicanal (correo electrónico, mensajería y notificaciones internas) para alumnado, tutores y equipo de coordinación.

## Recomendación arquitectónica

Para maximizar la velocidad de entrega y mantener la coherencia entre backend y frontend desde el primer día, se recomienda un **monolito FastAPI** que exponga contratos JSON estables consumidos por una **UI Next.js**. Este enfoque prioriza:

- Un único proyecto Python que concentre los módulos de ingesta, reglas y notificaciones, incluyendo los jobs y tareas background necesarios.
- Un frontend desacoplado pero versionado dentro del mismo repositorio, consumiendo únicamente contratos JSON documentados.
- Sincronización continua entre backend y frontend al compartir ciclos de despliegue y pipelines dentro del monorepo.

Esta recomendación debe emplearse como referencia constante a lo largo del desarrollo del MVP.

## Estructura inicial

El repositorio incluye la estructura base del monolito FastAPI con carpetas para módulos, reglas, notificaciones, jobs, frontend Next.js, workflows declarativos, migraciones y artefactos de despliegue.

## Stubs de referencia listos para ejecutar

Para acelerar el onboarding del equipo se incluyen pruebas de concepto ejecutables que cubren los contratos descritos en el documento de arquitectura:

- **Modelos ORM/Pydantic** (`app/models.py`): entidad `Student` en SQLAlchemy 2.0 y su equivalente `StudentModel` en Pydantic para serializar filas provenientes de la BD o del import XLSX.
- **Motor de reglas** (`app/rules/engine.py`): carga el YAML `app/rules/rulesets/sample.yaml` y evalúa expresiones simples con helpers (`today`, `parse_date`, `days_until`).
- **Scheduler con quiet hours** (`app/jobs/scheduler.py`): envuelve APScheduler y bloquea ejecuciones dentro de la franja declarada en los playbooks.
- **Adaptador CLI** (`app/notify/adapters/cli.py`): ejecuta procesos externos que hablen JSON ↔ JSON por stdin/stdout.

### Cómo extender los stubs con reglas y playbooks YAML

1. **Duplica el playbook de ejemplo** `workflows/playbooks/sample_prl_playbook.yaml` y ajusta el `cron`, `source` y las acciones para el flujo deseado. Cada playbook debe apuntar a un `ruleset` y un `mapping`.
2. **Declara nuevos rulesets** en `app/rules/rulesets/` siguiendo la clave `rules`. Las expresiones `when` tienen acceso al diccionario `row` con los campos mapeados y a los helpers del motor.
3. **Mantén los mapeos de columnas** en `workflows/mappings/` para aislar los nombres de los XLSX del modelo interno consumido por el `StudentModel` y las reglas.
4. **Conecta acciones personalizadas** creando adaptadores adicionales dentro de `app/notify/adapters/` reutilizando la firma de `CLIAdapter` o exportando clases equivalentes (por ejemplo un `EmailSMTPAdapter`).
5. **Registra jobs** mediante `Scheduler.schedule_interval` empleando las quiet hours definidas en el playbook para coordinar la ejecución con la cola de notificaciones.

Revisa los tests en `tests/` para ver ejemplos mínimos de uso y como punto de partida para ampliar la cobertura con escenarios reales.

## Puesta en marcha rápida

1. Clona el repositorio y crea el archivo de variables de entorno a partir de la plantilla:

   ```bash
   cp .env.example .env
   ```

2. Levanta la infraestructura mínima (API, Postgres y Redis) con Docker Compose:

   ```bash
   docker compose up -d
   ```

3. En un entorno de desarrollo local también puedes lanzar la aplicación con recarga automática:

   ```bash
   uvicorn app.main:app --reload
   ```

Con estos pasos el equipo dispone de una API funcional en minutos y una base homogénea para ejecutar pruebas, migraciones y jobs de cola.

## Integración con Moodle

El monolito incluye una capa de conectores (`app/connectors/moodle/`) preparada para consumir los servicios REST y SOAP de Moodle mediante token. La activación de la API se controla desde variables de entorno expuestas en `app/config.py`:

- `MOODLE_API_ENABLED`: activa el uso de la API oficial en lugar de los ficheros XLSX exportados manualmente.
- `MOODLE_TOKEN`: token emitido por Moodle para los servicios web.
- `MOODLE_REST_BASE_URL`: URL base del endpoint REST (`https://moodle.example/webservice`).
- `MOODLE_SOAP_WSDL_URL`: WSDL del servicio SOAP legacy en caso de necesitarlo.

Mientras `MOODLE_API_ENABLED` permanezca en `false` el sistema seguirá ingiriendo hojas de cálculo (`source: xlsx`) y los playbooks se ejecutarán automáticamente en modo *dry-run*. Esto permite validar reglas y umbrales con datos históricos antes de conectar el flujo completo de notificaciones.

Cuando se habilite la API, el servicio `CourseSyncService` centralizará la lectura de cursos y los jobs planificados en `app/jobs/moodle_sync.py` lanzarán los playbooks indicados respetando la configuración de ventanas de silencio.

## Observabilidad y trazabilidad

- El backend inicializa **logging estructurado con structlog** y emite eventos JSON enriquecidos con `job_id`, `job_name` y canal de entrega para seguir cada notificación desde el _enqueue_ hasta la confirmación del adaptador.
- Los workers de RQ propagan automáticamente el identificador de job y registran los hitos `queued`, `sent`, `error`, etc. en la base de datos (`jobs` + `job_events`).
- Las auditorías de notificaciones enlazan cada evento con su job correspondiente, lo que permite correlacionar métricas, reintentos y diagnósticos operativos sin exponer información sensible.

## Consideraciones RGPD y operativas

- **Minimización de datos**: la tabla `contacts` almacena únicamente la información estrictamente necesaria (nombre, canales de contacto y atributos opcionales) y separa los cursos/inscripciones en entidades dedicadas (`courses`, `enrollments`).
- **Retención y acceso**: las notificaciones se auditan con payloads serializados y ligados a un `job_id`, facilitando exportaciones o borrados por estudiante/contacto bajo petición del interesado.
- **Privacidad en logs**: el logger estructurado evita volcar PII completa, utilizando claves agregadas (`job_id`, `channel`, `status`) para el análisis operativo.
- **Operaciones seguras**: la correlación de jobs habilita dashboards y alertas que no requieren copiar datos personales; además, los playbooks pueden documentar ventanas de silencio y reglas de consentimiento en `workflows/`.

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulta [LICENSE](LICENSE) para más detalles.
