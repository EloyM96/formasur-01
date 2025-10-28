# Extensión e integraciones avanzadas

Este documento está orientado a becarios y desarrolladores que necesiten ampliar el sistema con nuevos canales, conectores o automatizaciones. Explica los contratos JSON existentes, cómo empaquetar adaptadores en otros lenguajes (incluido Java) y qué piezas deben tocarse para integrar Moodle u otras fuentes de datos.

## 1. Extender reglas y playbooks

1. **Añadir nuevas reglas**. Crea un fichero YAML en `app/rules/rulesets/` siguiendo el formato `rules: [{id, description, when}]`. El motor `RuleSet.from_yaml` cargará automáticamente el conjunto y lo evaluará en cada fila.【F:app/rules/engine.py†L53-L81】
2. **Actualizar mapeos**. Si el XLSX incluye columnas nuevas, edita el YAML correspondiente en `workflows/mappings/`. El `WorkflowRunner` renombrará las columnas en tiempo de ejecución, por lo que no es necesario modificar código Python.【F:app/workflows/runner.py†L94-L132】
3. **Duplicar playbooks**. Clona `workflows/playbooks/sample_prl_playbook.yaml` y ajusta `trigger`, `source`, `actions` y `quiet_hours` según las necesidades del flujo.【F:workflows/playbooks/sample_prl_playbook.yaml†L1-L44】

## 2. Crear adaptadores de notificación

El dispatcher invoca adaptadores registrados bajo un canal (`email`, `whatsapp`, etc.). Cada adaptador expone un método `send(payload)` que recibe un JSON con el contexto de la notificación.【F:app/notify/dispatcher.py†L90-L224】

### 2.1 Adaptadores CLI (ideal para Java, Go o scripts corporativos)

- Utiliza `CLIAdapter` para ejecutar un proceso externo que lee JSON por `stdin` y escribe JSON por `stdout`. El test `tests/test_cli_adapter.py` muestra un ejemplo mínimo.【F:app/notify/adapters/cli.py†L1-L26】【F:tests/test_cli_adapter.py†L1-L40】
- El payload que envía el dispatcher incluye claves como `action`, `channel`, `template`, `variables` y metadatos del playbook. El adaptador debe devolver, como mínimo, `status` (`ok`/`error`) y opcionalmente `message_id` o `error`.
- Para simular WhatsApp en desarrollo existe `WhatsAppCLIAdapter`, que ejecuta un script Python con respuesta determinista. Puedes reemplazarlo por tu JAR Java manteniendo la misma interfaz.【F:app/notify/adapters/whatsapp_cli.py†L1-L34】【F:tests/test_whatsapp_adapter.py†L1-L32】

**Contrato sugerido (JSON):**
```json
{
  "action": "send",
  "channel": "whatsapp",
  "template": "aviso_vencimiento",
  "to": "+34999999999",
  "variables": {"nombre": "Ana", "curso": "PRL Básico"},
  "metadata": {"playbook": "sample_prl_playbook", "job_id": "..."}
}
```

**Respuesta esperada:**
```json
{"status": "ok", "message_id": "provider-123"}
```

### 2.2 Adaptadores HTTP o SMTP

- `app/notify/adapters/email_smtp.py` implementa envíos via SMTP usando `smtplib`. Puedes usarlo como referencia para añadir autenticación TLS, plantillas HTML o multicanal.【F:app/notify/adapters/email_smtp.py†L1-L120】
- Si prefieres un servicio HTTP (por ejemplo, un microservicio Java Spring Boot), crea un adaptador similar que use `httpx` y publique la misma interfaz `send(payload)`.

## 3. Integrar nuevos sistemas externos

### 3.1 Moodle Web Services

- Activa `MOODLE_API_ENABLED` y configura `MOODLE_TOKEN`/`MOODLE_REST_BASE_URL` en `.env`.
- `MoodleRESTClient` gestiona la autenticación y maneja los errores devueltos por Moodle, por lo que solo necesitas implementar los endpoints adicionales que requieras.【F:app/connectors/moodle/rest.py†L1-L62】
- `CourseSyncService` es la pieza central: cuando la API está activada consulta Moodle, transforma la respuesta en el mismo formato que el XLSX y reusa el pipeline de ingesta, evitando duplicar código.【F:app/services/sync_courses.py†L1-L123】
- Programa sincronizaciones periódicas con `schedule_moodle_sync_jobs`. Tras cada sincronización, se ejecuta el playbook que definas para mantener notificaciones actualizadas.【F:app/jobs/moodle_sync.py†L1-L47】

#### Checklist de despliegue

1. Verifica que la variable `MOODLE_API_ENABLED` esté alineada con el entorno objetivo (mantenerla en `false` en pruebas locales y activarla en preproducción/producción cuando la API esté lista).
2. Define `MOODLE_TOKEN` con un valor válido para el entorno, idealmente mediante secretos gestionados y no hardcodeados.
3. Confirma que las respuestas de Moodle incluyan listas sin excepciones ni códigos de error; cualquier payload con `{"exception": ...}` debe bloquear el despliegue hasta que soporte técnico confirme su corrección.
4. Añade validaciones automáticas en los pipelines (por ejemplo, tests o jobs de verificación) que ejecuten el conector con criterios básicos y aseguren que el formato JSON coincide con lo esperado.

#### Ejemplo paso a paso de `CourseSyncService.sync()`

**Modo API (`MOODLE_API_ENABLED=true`):**

1. El servicio detecta que `use_moodle_api` es `True` porque existe `MoodleRESTClient` configurado con `MOODLE_TOKEN` y URL base.
2. Se invoca `_from_rest_api()`, que a su vez llama a `fetch_courses()` y recibe la lista de cursos en bruto desde Moodle.
3. Cada entrada se transforma mediante `_map_rest_course`, normalizando nombres, fechas y atributos extra.
4. Se devuelve un `CourseSyncResult` con `source="moodle"` y `dry_run=False`, permitiendo que los playbooks ejecuten acciones reales.

**Modo XLSX (`MOODLE_API_ENABLED=false`):**

1. Al deshabilitar la API, `use_moodle_api` retorna `False` y `sync()` exige un `source_path` apuntando al XLSX exportado.
2. `_from_xlsx()` lee el fichero con `pandas`, valida que incluya `name`, `hours_required` y `deadline_date` y recorre cada fila.
3. `_map_xlsx_row` convierte las filas a `CourseModel`, generando atributos adicionales si existen columnas personalizadas.
4. El resultado final es un `CourseSyncResult` con `source="xlsx"` y `dry_run=True`, manteniendo los playbooks en modo seguro hasta habilitar la API.

### 3.2 Otros orígenes (Prevengos, CRM, etc.)

- Utiliza el mismo patrón que con Moodle: crea un cliente en `app/connectors/<nombre>/` con métodos claros, encapsula la lógica de mapeo en un servicio (`app/services/...`) y reutiliza `WorkflowRunner` para desencadenar acciones.
- Documenta los contratos JSON o CSV en un fichero dentro de `docs/` o `workflows/` para que el resto del equipo conozca el formato esperado.

## 4. Buenas prácticas para becarios y extensiones Java

1. **Empezar por los tests**. Antes de escribir código Java, replica el contrato en Python con un test en `tests/test_<canal>_adapter.py`. Cuando pase, implementa el adaptador real y asegúrate de que los tests siguen verdes.
2. **Generar JARs auto-contenidos**. Si el adaptador Java depende de bibliotecas externas, usa `mvn package` o `gradle shadowJar` para obtener un ejecutable único. Configura `CLIAdapter(command=["java", "-jar", "tu-adapter.jar"])` para invocarlo.【F:app/notify/adapters/cli.py†L1-L26】
3. **Registrar el adaptador**. En la inicialización del dispatcher, añade el adaptador al diccionario de canales. Si usas FastAPI, puedes hacerlo al crear la instancia en el contenedor de dependencias o en un módulo específico.
4. **Documentar el contrato**. Añade un apartado en `docs/extensibility-guide.md` (este archivo) o crea un doc propio con ejemplos de entrada/salida para que otros becarios puedan iterar sin ambigüedades.

## 5. Checklist de extensibilidad

- [ ] Reglas nuevas con identificadores descriptivos y documentación en YAML.
- [ ] Playbooks actualizados con comentarios sobre su objetivo y ventanas de silencio.
- [ ] Adaptadores registrados y testeados con escenarios de éxito y error.
- [ ] Integraciones externas protegidas por feature flags (`settings`) y con logs suficientes para su diagnóstico.
- [ ] Documentación actualizada en `docs/` y ejemplos reproducibles en los tests.

Siguiendo estas pautas puedes extender prl-notifier con nuevas capacidades sin romper los flujos existentes ni dejar zonas grises para los operarios o docentes que dependen del sistema.
