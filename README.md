# prl-notifier

Plataforma monolítica para la gestión integral de la prevención de riesgos laborales (PRL) en entornos formativos. Este repositorio consolida backend, frontend, automatizaciones y documentación operativa necesarios para importar datos desde Moodle, evaluar el cumplimiento normativo con reglas declarativas y orquestar campañas de notificación multicanal.

> **Licencia propietaria**: Todo el contenido está protegido por derechos de autor de Eloy Moya Martínez. El uso, distribución o modificación requiere autorización previa y expresa. Consulta el archivo [LICENSE](LICENSE) para las condiciones completas.

## Tabla de contenidos

- [Visión general](#visión-general)
- [Arquitectura funcional](#arquitectura-funcional)
- [Componentes principales](#componentes-principales)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Requisitos previos](#requisitos-previos)
- [Configuración inicial](#configuración-inicial)
- [Puesta en marcha rápida](#puesta-en-marcha-rápida)
- [Ejecución en desarrollo](#ejecución-en-desarrollo)
- [Despliegue y operación](#despliegue-y-operación)
- [Flujo de negocio PRL](#flujo-de-negocio-prl)
- [Extensibilidad y personalización](#extensibilidad-y-personalización)
- [Observabilidad y seguridad](#observabilidad-y-seguridad)
- [Guía de resolución de problemas](#guía-de-resolución-de-problemas)
- [Documentación adicional](#documentación-adicional)
- [Licencia](#licencia)

## Visión general

El objetivo del MVP de **prl-notifier** es automatizar el seguimiento de la PRL para organizaciones educativas. El sistema facilita a personal técnico y no técnico:

- Ingerir hojas de cálculo XLSX exportadas desde Moodle con información del alumnado y su estado formativo.
- Evaluar el cumplimiento de la PRL mediante un motor de reglas declarativo respaldado por YAML.
- Coordinar y auditar notificaciones multicanal para alumnado, tutores y personal de coordinación.
- Unificar todo el ciclo de vida en un único repositorio versionado que agiliza la entrega continua.

## Arquitectura funcional

```
[XLSX Moodle] → [Ingesta y normalización] → [Motor de reglas declarativas]
                      │                          │
                      ▼                          ▼
               [Base de datos] ↔ [API FastAPI] ↔ [Scheduler y Jobs]
                      │                          │
                      ▼                          ▼
                 [Notificaciones] ← [Playbooks YAML]
```

El backend FastAPI expone contratos JSON consumidos por una interfaz Next.js. Los playbooks YAML describen el calendario, las fuentes de datos y las acciones de notificación. Toda la automatización reside en un monolito Python que comparte versión y pipelines con el frontend para garantizar consistencia.

## Componentes principales

| Área              | Descripción                                                                                     |
|-------------------|-------------------------------------------------------------------------------------------------|
| Ingesta           | Conversión de XLSX a modelos internos (`app/modules/ingest/`).                                 |
| Reglas            | Evaluación declarativa (`app/rules/engine.py` + `app/rules/rulesets/`).                         |
| API REST          | Servicios para cursos, matrículas y notificaciones (`app/api/`).                                |
| Programación      | Jobs con ventanas de silencio y repetición (`app/jobs/`).                                       |
| Notificaciones    | Adaptadores para CLI, email u otros canales (`app/notify/adapters/`).                          |
| Frontend          | UI Next.js bajo `frontend/` que consume los contratos JSON expuestos.                           |
| Infraestructura   | Contenedores Docker, Compose y migraciones (`docker/`, `docker-compose.yml`, `migrations/`).    |

## Estructura del repositorio

```
.
├── app/                  # Monolito FastAPI con módulos de negocio, conectores y servicios
├── frontend/             # Aplicación Next.js que consume la API REST
├── docker/               # Imagenes base y scripts de construcción
├── docker-compose.yml    # Orquestación local de API, Postgres y Redis
├── docs/                 # Documentación extendida para operación y pruebas
├── migrations/           # Migraciones de base de datos (Alembic)
├── tests/                # Cobertura automatizada del backend
├── workflows/            # Playbooks y mappings YAML para jobs y reglas
├── LICENSE               # Licencia propietaria
└── README.md             # Este documento
```

## Requisitos previos

- Docker 24+ y Docker Compose Plugin.
- Python 3.11+ con `pip` y `uvicorn` para ejecución local.
- Node.js 18+ y `pnpm`/`npm` para trabajar con el frontend.
- Acceso a un servidor PostgreSQL y Redis (proporcionados por Docker Compose en entornos locales).

## Configuración inicial

1. Clona el repositorio y crea tu archivo de variables de entorno:
   ```bash
   cp .env.example .env
   ```
2. Ajusta las variables en `.env` para conectar con Moodle, definir tokens y parámetros de notificación.
3. Si vas a consumir la API de Moodle, registra `MOODLE_TOKEN`, `MOODLE_REST_BASE_URL` y `MOODLE_SOAP_WSDL_URL` en `app/config.py` o en tu `.env`.

## Puesta en marcha rápida

La forma más sencilla de validar el stack completo es mediante Docker Compose:

```bash
docker compose up -d
```

Este comando levanta la API FastAPI, la base de datos PostgreSQL, Redis y los workers necesarios. Los contenedores se reinician automáticamente para garantizar disponibilidad mínima.

## Ejecución en desarrollo

1. Activa un entorno virtual y instala dependencias:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -U pip
   pip install -e .[dev]
   ```
2. Inicia la API con recarga automática:
   ```bash
   uvicorn app.main:app --reload
   ```
3. Lanza el frontend en paralelo (desde `frontend/`):
   ```bash
   pnpm install
   pnpm dev
   ```
4. Ejecuta los tests para asegurar la regresión mínima:
   ```bash
   pytest
   ```

## Despliegue y operación

- **Producción en contenedores**: construye las imágenes en `docker/` y publica en tu registro privado. Ajusta las variables de entorno para apuntar a servicios gestionados (RDS, ElastiCache, etc.).
- **Escalado horizontal**: separa los workers RQ del API Web cuando el volumen de notificaciones crezca. Redis actúa como cola y permite lanzar varias réplicas.
- **Automatización**: los playbooks en `workflows/playbooks/` definen cron, fuentes y acciones. Versionarlos junto al código garantiza reproducibilidad.
- **Backups y migraciones**: ejecuta `alembic upgrade head` antes de cada despliegue. Automatiza backups de PostgreSQL y configúralos en tus pipelines.

## Flujo de negocio PRL

1. **Carga de datos** (`POST /uploads`): el XLSX se valida contra el mapeo definido en `workflows/mappings/`. Se registra la subida y se invoca el cargador correspondiente.
2. **Normalización**: `app/modules/ingest/course_loader.py` transforma filas en entidades (`courses`, `enrollments`, `students`). Campos ausentes se derivan o marcan para revisión manual.
3. **Evaluación de reglas**: `app/rules/engine.py` evalúa las condiciones declaradas en YAML y anota incumplimientos, hitos próximos y métricas agregadas.
4. **Monitoreo y reporting**: endpoints como `GET /courses`, `GET /courses/{id}` y `GET /students/non-compliance` ofrecen paneles listos para integrarse con el frontend.
5. **Notificaciones**: los jobs definidos en `app/jobs/` y los adaptadores en `app/notify/adapters/` gestionan envíos por correo, mensajería y otros canales.
6. **Seguimiento**: `GET /notifications` y las tablas `jobs` / `job_events` permiten auditar cada envío y correlacionarlo con reglas y playbooks.

## Extensibilidad y personalización

- **Nuevas reglas**: añade YAML en `app/rules/rulesets/` y referencias en tus playbooks. Las expresiones disponen de helpers como `today`, `parse_date` y `days_until`.
- **Mapeos de datos**: mantiene los archivos en `workflows/mappings/` para desacoplar la estructura del XLSX de tus modelos internos.
- **Playbooks**: duplica `workflows/playbooks/sample_prl_playbook.yaml`, define `cron`, `source` y acciones (`notify`, `enqueue`, etc.) y asígnalos a tus rulesets.
- **Adaptadores de notificación**: extiende `app/notify/adapters/` para integrar SMS, WhatsApp, bots corporativos o cualquier canal que hable JSON ↔ JSON.
- **Integración con Moodle**: habilita `MOODLE_API_ENABLED=true` para que `CourseSyncService` sincronice automáticamente cursos y matrículas usando los servicios REST/SOAP oficiales.

## Observabilidad y seguridad

- **Logging estructurado**: `app/logging.py` inicializa `structlog` con contexto enriquecido (`job_id`, `channel`, `status`).
- **Trazabilidad de jobs**: la cola RQ documenta estados (`queued`, `sent`, `error`) en base de datos para análisis retroactivo.
- **Cumplimiento RGPD**: minimización de datos personales, retención controlada y logs que evitan exponer PII. Ajusta las ventanas de silencio y reglas de consentimiento en `workflows/`.

## Guía de resolución de problemas

| Síntoma | Diagnóstico | Acción recomendada |
|---------|-------------|--------------------|
| Importación falla al subir XLSX | Los encabezados no coinciden con el mapeo | Revisar `workflows/mappings/*.yaml` y actualizar las columnas. |
| Jobs no se ejecutan | Ventana de silencio activa o Redis desconectado | Confirmar configuración de `quiet_hours` y estado del contenedor Redis. |
| Notificaciones duplicadas | Playbook con cron solapado | Revisar `workflows/playbooks/` y ajustar la cadencia o agrega control de idempotencia. |
| API devuelve 500 | Migraciones desactualizadas | Ejecutar `alembic upgrade head` y reiniciar el servicio. |

## Documentación adicional

- [docs/README.md](docs/README.md): índice completo con visión general, arquitectura extendida y manuales operativos.
- [docs/beta_operational_manual.md](docs/beta_operational_manual.md): procedimientos detallados para ingesta, reglas, API y notificaciones.
- Carpeta `tests/`: ejemplos mínimos de uso que sirven como punto de partida para ampliar cobertura.

## Licencia

Este proyecto está protegido por la **Licencia de Uso Restringido de Eloy Moya Martínez**. No se concede permiso para copiar, modificar, distribuir o utilizar el software sin autorización previa, expresa y por escrito. Consulta [LICENSE](LICENSE) para conocer los términos completos y el proceso de solicitud.
