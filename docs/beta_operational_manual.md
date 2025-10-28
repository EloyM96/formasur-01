# Manual operativo beta del flujo PRL

Este manual describe con precisión todas las piezas incluidas en el MVP para las pruebas beta. Resume cómo se ingiere el XLSX procedente de Moodle, cómo se persisten los datos en la base de datos SQL, qué API expone el backend para el seguimiento del alumnado y cómo se registran los avisos. Cada apartado enlaza con la implementación concreta para que puedas auditarla o extenderla.

## 1. Ingesta de hojas de cálculo XLSX

1. **Validación del fichero recibido**: el endpoint `POST /uploads` acepta exclusivamente ficheros `.xlsx`, comprueba el tamaño (máximo 5 MiB) y almacena el binario en `uploads/` antes de delegar en el cargador de cursos.【F:app/api/uploads.py†L28-L88】
2. **Mapeo de columnas configurable**: el fichero se compara con el mapeo YAML `workflows/mappings/moodle_prl.yaml` para asegurar que se incluyen todas las columnas críticas (`Nombre completo`, `Email`, `Horas cursadas`, etc.).【F:workflows/mappings/moodle_prl.yaml†L1-L9】【F:app/modules/ingest/xlsx_importer.py†L28-L67】
3. **Normalización y creación de entidades**:
   - Los valores se limpian y tipan (fechas, horas, teléfonos) con `_normalize_row` para evitar nulos o formatos inválidos.【F:app/modules/ingest/course_loader.py†L97-L166】
   - Se crean o actualizan cursos rellenando horas totales y fecha límite cuando el XLSX no lo aporta (se deducen de las horas cursadas o de la caducidad del certificado).【F:app/modules/ingest/course_loader.py†L42-L84】
   - Se sincronizan estudiantes y matrículas, guardando atributos adicionales (teléfono, caducidades) en JSON para consultas posteriores.【F:app/modules/ingest/course_loader.py†L86-L142】
4. **Resumen de ingesta**: el cargador devuelve contadores de cursos, estudiantes y matrículas creadas/actualizadas para mostrarlos inmediatamente tras la subida.【F:app/modules/ingest/course_loader.py†L18-L39】

## 2. Modelo de datos relacional

La base de datos SQL mantiene todas las entidades necesarias para el seguimiento operativo y el histórico de avisos. Los modelos ORM definen columnas, claves foráneas y metadatos.【F:app/models.py†L40-L170】

- `courses`: nombre, horas requeridas, fecha límite y origen (`xlsx` o `moodle`). Permite correcciones manuales posteriores.【F:app/models.py†L57-L82】
- `students`: datos personales básicos y fecha de caducidad del certificado vigente.【F:app/models.py†L84-L101】
- `enrollments`: relación curso ↔ alumno, progreso en horas, estado, atributos enriquecidos (teléfono, caducidades).【F:app/models.py†L103-L132】
- `notifications`: auditoría de avisos enviados, incluyendo canal, adaptador, estado, payload y relación con la matrícula y el job que lo generó.【F:app/models.py†L144-L196】
- `uploaded_files`, `contacts`, `jobs` y `job_events` completan el trazado end-to-end para reproducibilidad y métricas.【F:app/models.py†L40-L170】

## 3. Correcciones manuales del curso

El operario puede completar o ajustar datos ausentes mediante `PATCH /courses/{id}`, que permite fijar `deadline_date` y `hours_required` cuando el XLSX no los aporta o requieren corrección.【F:app/api/courses.py†L93-L147】

## 4. Seguimiento y métricas operativas

1. **Resumen agregado (`GET /courses`)**: devuelve los cursos ordenados por fecha límite con métricas agregadas (`total_enrollments`, `non_compliant_enrollments`, `zero_hours_enrollments`) y el conteo de avisos por canal ya enviados.【F:app/api/courses.py†L49-L92】【F:app/services/enrollments.py†L20-L76】
2. **Detalle por matrícula (`GET /courses/{id}`)**: para cada alumno muestra la evaluación de reglas, infracciones detectadas, si no ha registrado actividad (0 h) y los avisos emitidos (totales y por canal).【F:app/api/courses.py†L149-L199】
3. **Listado de incumplimientos (`GET /students/non-compliance`)**: aplica el ruleset `rules/rulesets/enrollments.yaml` para filtrar alumnos con certificados caducados, caducidades próximas u horas insuficientes, admitiendo filtros por curso, fechas, horas y regla específica.【F:app/api/students.py†L19-L104】
4. **Motor de reglas**: la evaluación se centraliza en `enrollment_service.evaluate_enrollment`, que serializa la matrícula y consulta el ruleset; cualquier regla marcada como `True` se considera infracción y se incluye en la respuesta.【F:app/services/enrollments.py†L20-L76】

## 5. Avisos multicanal y trazabilidad

- Los playbooks YAML pueden despachar acciones `notify` que el `NotificationDispatcher` enruta al adaptador configurado (CLI, SMTP, WhatsApp). Controla ventanas de silencio, reintentos y registra auditorías incluso en modo *dry-run*.【F:app/notify/dispatcher.py†L1-L200】
- Las auditorías quedan accesibles vía `GET /notifications`, con filtros por canal, estado, playbook, job y rango de fechas; además expone `/notifications/metadata` para poblar selectores en la UI.【F:app/api/notifications.py†L1-L87】
- Los conteos por curso/matrícula se obtienen con `summarize_notifications`, reutilizado por los endpoints de cursos para que el operario vea qué avisos se enviaron previamente.【F:app/services/enrollments.py†L78-L109】【F:app/api/courses.py†L201-L226】

## 6. Preparación para integrar Moodle

- La capa de conectores ya implementa un cliente REST parametrizable (`MoodleRESTClient`) y excepciones específicas para tratar errores de la API oficial.【F:app/connectors/moodle/rest.py†L1-L120】【F:app/connectors/moodle/exceptions.py†L1-L52】
- `CourseSyncService` decide dinámicamente si debe leer el XLSX o consumir la API REST. Mientras `MOODLE_API_ENABLED` sea `false`, opera en modo *dry-run* reutilizando el flujo descrito arriba; al activarse se mapearán los cursos directamente desde Moodle manteniendo el mismo contrato interno (`CourseModel`).【F:app/services/sync_courses.py†L1-L123】【F:app/config.py†L1-L25】
- Los jobs `moodle_sync` están listos para planificarse con APScheduler y poblar la cola de notificaciones respetando las quiet hours definidas en los playbooks.【F:app/jobs/moodle_sync.py†L1-L120】

## 7. Pruebas automatizadas

El repositorio incluye cobertura integral de extremo a extremo:

- `tests/test_uploads.py` valida la subida del XLSX, la creación de registros y los contadores de ingesta.【F:tests/test_uploads.py†L1-L114】
- `tests/test_courses_api.py`, `tests/test_students_api.py` y `tests/test_notifications_api.py` garantizan que los endpoints REST devuelven las métricas y filtros esperados.【F:tests/test_courses_api.py†L1-L120】【F:tests/test_students_api.py†L1-L160】【F:tests/test_notifications_api.py†L1-L140】
- `tests/test_moodle_connectors.py` y `tests/test_course_sync_service.py` simulan la transición hacia Moodle Web Services asegurando compatibilidad futura.【F:tests/test_moodle_connectors.py†L1-L160】【F:tests/test_course_sync_service.py†L1-L130】
- `tests/test_dispatcher.py` y `tests/test_workflow_runner.py` verifican el despacho de avisos, los contadores por canal y la ejecución de playbooks en modo beta.【F:tests/test_dispatcher.py†L1-L220】【F:tests/test_workflow_runner.py†L1-L190】

Para reproducir toda la batería basta con ejecutar `pytest`, que actualmente pasa 30 pruebas cubriendo ingesta, reglas y notificaciones.【744138†L1-L19】

