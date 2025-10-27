# Estado actual y próximos pasos

## 1. Resumen del estado actual

- **Infraestructura FastAPI lista y testeada**: existe un `app.main` con healthcheck que carga la configuración y expone el endpoint `/health`, alineado con el objetivo del Issue 1 del backlog. 【F:app/main.py†L1-L18】【F:workflows/backlog/initial-backlog.md†L25-L27】
- **Configuración centralizada**: `app.config.Settings` define variables de entorno para la base de datos, Redis y SMTP, cumpliendo parte de la base para despliegues Docker Compose mencionados en el roadmap. 【F:app/config.py†L1-L24】【F:workflows/backlog/initial-backlog.md†L43-L44】
- **Modelos y motor de reglas funcionales**: Se dispone de modelos ORM/Pydantic (`Student`, `StudentModel`) y de un motor declarativo (`RuleSet`) con helpers de fechas y ruleset de ejemplo, cumpliendo parcialmente los Issues 3, 4 y 5. 【F:app/models.py†L1-L67】【F:app/rules/engine.py†L1-L95】【F:app/rules/rulesets/sample.yaml†L1-L7】【F:workflows/backlog/initial-backlog.md†L30-L36】
- **Workflows y mapeos de ejemplo**: Hay playbook y mapping YAML conectados con el motor de reglas, lo que facilita la orquestación declarativa descrita en el documento raíz. 【F:workflows/playbooks/sample_prl_playbook.yaml†L1-L20】【F:workflows/mappings/moodle_prl.yaml†L1-L5】【F:prl_notifier_arquitectura_roadmap_y_plan_de_becarios_mvp_→_crm.md†L57-L110】
- **Scheduler con quiet hours y adaptador CLI**: Los stubs de `Scheduler` y `CLIAdapter` ya están implementados y cubiertos por tests, aportando bases para los Issues 6, 8 y 9. 【F:app/jobs/scheduler.py†L1-L78】【F:app/notify/adapters/cli.py†L1-L26】【F:workflows/backlog/initial-backlog.md†L37-L42】
- **Cobertura de tests inicial**: `pytest` ejecuta cuatro pruebas unitarias que validan modelos, motor de reglas, scheduler y adaptador CLI, proporcionando base para el Issue 12 (CI pendiente). 【F:tests/test_models.py†L1-L36】【F:tests/test_rules_engine.py†L1-L53】【F:tests/test_scheduler.py†L1-L58】【F:tests/test_cli_adapter.py†L1-L66】【b29595†L1-L8】

## 2. Huecos detectados respecto al roadmap

- **Ingesta de XLSX y almacenamiento**: Falta un módulo/endpoint que reciba el XLSX (Issue 2) y lo persista para ser procesado por los playbooks. Actualmente solo hay rutas mínimas. 【F:app/main.py†L1-L18】【F:workflows/backlog/initial-backlog.md†L28-L32】
- **Parser y validaciones**: No existe aún un `xlsx_importer` que convierta los datos usando los mapeos declarativos, ni validaciones de calidad de datos (Issue 3). 【F:workflows/backlog/initial-backlog.md†L31-L33】
- **Motor de mapping declarativo**: Aunque hay YAML de mapeo, falta el código que lo aplique sobre filas de XLSX, por lo que el Issue 4 permanece abierto. 【F:workflows/mappings/moodle_prl.yaml†L1-L5】【F:workflows/backlog/initial-backlog.md†L33-L34】
- **Ejecución de playbooks**: No hay orquestador que combine source → mapping → rules → acciones, ni integración con la cola `QueueClient`, aún sin backend real (Issues 6 y 9). 【F:app/queue.py†L1-L17】【F:workflows/playbooks/sample_prl_playbook.yaml†L1-L20】【F:workflows/backlog/initial-backlog.md†L35-L42】
- **Canales de notificación reales**: Solo existe el adaptador CLI. No hay adaptadores SMTP ni WhatsApp HTTP ni plantillas. 【F:app/notify/adapters/cli.py†L1-L26】【F:workflows/backlog/initial-backlog.md†L37-L41】
- **Frontend Next.js**: Existe una semilla con formulario de subida que apunta a `/api/upload`, pero falta la integración real con FastAPI y las vistas de auditoría (Issues 2, 6, 10). 【F:frontend/README.md†L1-L23】【F:frontend/src/components/FileUploadForm.tsx†L1-L84】【F:workflows/backlog/initial-backlog.md†L28-L41】
- **Infra y CI**: Falta configurar Docker Compose operativo (servicios definidos pero sin documentación de uso) y pipeline CI que ejecute tests. 【F:docker-compose.yml†L1-L35】【F:workflows/backlog/initial-backlog.md†L41-L42】

## 3. Próximos pasos recomendados

1. **Implementar ingesta segura de XLSX (Issue 2)**
   - Añadir endpoint FastAPI para subir ficheros, guardarlos en almacenamiento temporal (`uploads/`).
   - Validar tamaño/estructura y registrar metadatos para trazabilidad.
   - Conectar con un servicio `xlsx_importer` que reciba ruta y mapping.

2. **Construir pipeline de parsing + mapping (Issues 3 y 4)**
   - Crear módulo `app/etl/xlsx_importer.py` que use `openpyxl/pandas` para convertir filas a diccionarios.
   - Implementar aplicación del mapping YAML para normalizar columnas y detectar faltantes.
   - Añadir validaciones básicas (campos obligatorios, formatos de fecha) con reportes reutilizables en backend/UI.

3. **Orquestación de playbooks y motor de reglas (Issues 5 y 6)**
   - Desarrollar un servicio `app/workflows/runner.py` que reciba un playbook, invoque el importer, aplique reglas y devuelva resultados por canal.
   - Preparar endpoints/API para ejecutar `dry-run` y `run`, reutilizando scheduler y quiet hours.
   - Serializar resultados para mostrarlos en la UI (resúmenes por canal, registros individuales).

4. **Integración con cola y adaptadores reales (Issues 7, 8, 9)**
   - Sustituir `QueueClient.enqueue` por integración con RQ/Redis usando `settings.queue_url`.
   - Implementar adaptador SMTP (plantillas Jinja2) y stub HTTP para WhatsApp, manteniendo contratos JSON.
   - Añadir manejo de reintentos/backoff y respeto de quiet hours en los workers.

5. **Primeras pantallas Next.js (Issues 2, 6, 10)**
   - Scaffold de UI para carga de XLSX, seguimiento de procesos y auditoría.
   - Consumir endpoints de backend para ver status de importaciones y resultados.
   - Configurar autenticación mínima (si aplica) y estados de error/éxito.

6. **Infraestructura compartida y CI (Issues 11 y 12)**
   - Completar `docker-compose.yml` con variables, volúmenes y documentación de puesta en marcha.
   - Configurar pipeline GitHub Actions que ejecute `pytest` y verificaciones estáticas.
   - Documentar `.env.example` con variables necesarias.

7. **Cumplimiento RGPD y Definition of Done común**
   - Incluir políticas de logging estructurado, minimización de datos y procedimientos RGPD en la documentación.
   - Añadir checklists en PR templates para asegurar cumplimiento de DoD. 【F:workflows/backlog/initial-backlog.md†L19-L24】

Con estas prioridades, el equipo puede avanzar siguiendo la arquitectura recomendada en el documento raíz y completar los entregables de la semana 1.
