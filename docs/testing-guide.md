# Pruebas, datos de ejemplo y aseguramiento de calidad

Este documento explica cómo preparar datos de prueba, ejecutar la batería automatizada y validar manualmente los principales flujos. Es útil tanto para QA como para becarios que necesiten comprobar sus cambios antes de solicitar una revisión.

## 1. Requisitos previos

- Python 3.11 o superior con `pip` actualizado.
- Dependencias instaladas ejecutando `pip install -e .[dev]` desde la raíz del repositorio.
- Redis y Postgres disponibles si deseas reproducir pruebas que interactúan con RQ o la base de datos. Para la mayoría de tests se usan `sqlite:///:memory:` y `fakeredis`, por lo que no es obligatorio levantar servicios externos.

## 2. Ejecutar la suite automatizada

1. Desde la raíz del proyecto, lanza:
   ```bash
   pytest
   ```
2. La batería cubre ingesta de XLSX, APIs REST, motor de reglas, dispatcher de notificaciones, adaptadores (CLI, email, WhatsApp), sincronización con Moodle y programación de jobs.【F:tests/test_uploads.py†L1-L118】【F:tests/test_courses_api.py†L1-L136】【F:tests/test_dispatcher.py†L1-L214】
3. Si necesitas medir cobertura, ejecuta `pytest --cov=app --cov=tests` y revisa el informe HTML generado en `.htmlcov/`.

> Los fixtures compartidos se definen en `tests/conftest.py` e incluyen bases de datos temporales, colas en memoria y utilidades para construir playbooks de prueba.【F:tests/conftest.py†L1-L170】

## 2.1. Flujos recomendados

Cuando quieras validar cambios en áreas específicas sin esperar a que termine la suite completa, lanza subconjuntos orientados a los módulos responsables:

- Dispatcher de notificaciones: `pytest tests/test_dispatcher.py`. El flujo refleja las rutas principales de `app/notify/dispatcher.py`, incluyendo la orquestación de adaptadores y la coordinación con la cola RQ.【F:app/notify/dispatcher.py†L1-L200】
- Motor de reglas: `pytest tests/test_rules_engine.py`. Ayuda a validar que las evaluaciones delegadas en `app/rules/engine.py` siguen siendo deterministas frente a nuevos playbooks.【F:app/rules/engine.py†L1-L200】
- Cargador de hojas de cálculo: `pytest tests/test_uploads.py -k parse_xlsx` te permite comprobar rápidamente cambios en la ingesta de XLSX sin ejecutar escenarios completos.【F:app/modules/ingest/xlsx_importer.py†L1-L200】

## 3. Datos de ejemplo para pruebas manuales

- **XLSX de referencia**. Puedes generar uno siguiendo la misma plantilla que utiliza el fixture `valid_workbook` en los tests: crea un DataFrame con columnas como `Nombre completo`, `Email`, `Horas cursadas`, `Horas totales` y fechas ISO, luego exporta con `pandas.DataFrame.to_excel`. El fragmento exacto está en `tests/test_uploads.py` y sirve como guía.【F:tests/test_uploads.py†L52-L118】
- **Playbook de ejemplo**. `workflows/playbooks/sample_prl_playbook.yaml` define un flujo completo con quiet hours y acciones `notify`. Puedes duplicarlo para crear variaciones rápidas ajustando el `cron` y las plantillas.【F:workflows/playbooks/sample_prl_playbook.yaml†L1-L44】
- **Ruleset base**. `app/rules/rulesets/sample.yaml` ilustra cómo expresar reglas de caducidad y progresos en YAML.

Para validar un flujo extremo a extremo sin mover datos reales:

1. Carga el XLSX generado mediante `POST /uploads`.
2. Ejecuta `POST /workflows/dry-run` con `sample_prl_playbook`.
3. Revisa la respuesta y, si todo es correcto, lanza `POST /workflows/run`.
4. Consulta `GET /notifications` para comprobar los registros generados; se utilizarán adaptadores “dummy” que escriben en memoria durante los tests.【F:tests/test_notifications_api.py†L1-L120】

## 4. Verificación de integraciones externas

- **Moodle REST**. `tests/test_moodle_connectors.py` simula respuestas de Moodle y comprueba que `MoodleRESTClient` maneja errores y credenciales caducadas.【F:tests/test_moodle_connectors.py†L1-L160】
- **Jobs programados**. `tests/test_moodle_jobs.py` asegura que `schedule_moodle_sync_jobs` registra tareas con los intervalos correctos y respeta el modo *dry-run* cuando la API está deshabilitada.【F:tests/test_moodle_jobs.py†L1-L120】
- **Adaptadores CLI/HTTP**. Los tests de `app/notify/adapters` usan `subprocess` o clientes HTTP simulados para garantizar que el contrato JSON se respeta, permitiendo reemplazar la implementación por módulos en otros lenguajes sin romper compatibilidad.【F:tests/test_cli_adapter.py†L1-L92】【F:tests/test_whatsapp_adapter.py†L1-L118】

## 5. Checklist antes de subir cambios

- [ ] Ejecutar `pytest` y asegurarse de que no hay fallos.
- [ ] Añadir o actualizar fixtures si se introducen nuevos campos en los modelos o reglas.
- [ ] Documentar en `workflows/README.md` cualquier nuevo playbook o mapeo relevante.
- [ ] Mantener las anotaciones de tipo y los docstrings actualizados para facilitar el seguimiento en revisiones.

Seguir esta guía garantiza que las pruebas cubren los flujos críticos y que los datos de ejemplo están alineados con la documentación y el código fuente.

## Anexo. Preguntas frecuentes

- **¿Qué hacer si falta PyYAML?**. `parse_xlsx` necesita PyYAML para cargar el mapeo de columnas; instala la dependencia con `pip install PyYAML` o incluye el extra `.[dev]`. El módulo lanza un mensaje explícito ("PyYAML es necesario para cargar el fichero de mapeos") cuando detecta la ausencia de la librería para evitar fallos silenciosos.【F:app/modules/ingest/xlsx_importer.py†L1-L200】
