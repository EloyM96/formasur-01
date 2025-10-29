# Integración bidireccional con Prevengos

Este documento describe cómo la plataforma `prl-notifier` se integra con Prevengos —el ERP de Prevención de Riesgos Laborales utilizado por Formasur— mediante ficheros CSV, servicios JSON y acceso a la base de datos SQL Server. Incluye la arquitectura técnica, los contratos de datos y los procedimientos de despliegue para garantizar una conexión robusta entre ambas aplicaciones.

## Resumen ejecutivo

- **Objetivo**: sincronizar expedientes de formación PRL entre Formasur y Prevengos para los módulos técnico, médico y de coordinación.
- **Canales soportados**: importación/exportación CSV, API JSON oficial ("servicio de datos") y acceso a tablas/vistas SQL Server expuestas por Prevengos.
- **Tecnologías**: núcleo en Python/FastAPI con extensiones Java (adaptadores CLI) capaces de ejecutarse en Windows y Android. Las bibliotecas Java deben empaquetarse como `jar` autónomos.
- **Seguridad**: desplegar únicamente sobre Prevengos >= **v2.48** debido a vulnerabilidades corregidas en 2024–2025. Verificar certificados TLS y rotar tokens API cada 90 días.

## Arquitectura lógica

```
+---------------------------+
|  PrevengosSyncService     |
|  (Python)                 |
|  - Orquestación           |
|  - Reglas de conciliación |
+---------------------------+
     ^            ^
     |            |
 CSVAdapter   PrevengosAPIClient
     |            |
     v            v
 CSV SFTP     Servicio JSON
               (/contracts,
                /training-records)
     ^
     |
PrevengosDBAdapter
(SQL Server staging)
```

1. **Núcleo compartido (`PrevengosTrainingRecord`)**. Modelo inmutable con claves `(employee_nif, contract_code, course_code)` y sello temporal `last_update`. Se usa en todos los canales.【F:app/integrations/prevengos/models.py†L11-L80】
2. **CSVAdapter**. Lee y escribe ficheros en la carpeta `data/prevengos/` con codificación `utf-8-sig`, preservando campos adicionales en el payload.【F:app/integrations/prevengos/csv_adapter.py†L11-L63】
3. **PrevengosAPIClient**. Encapsula llamadas HTTPx con autenticación Bearer, exponiendo `fetch_contract()` y `push_training_records()` para validar contratos y subir estados en tiempo real.【F:app/integrations/prevengos/api_client.py†L12-L68】
4. **PrevengosDBAdapter**. Ejecuta consultas parametrizadas contra SQL Server (o vistas equivalentes) para obtener el último snapshot o actualizar tablas de staging autorizadas.【F:app/integrations/prevengos/db_adapter.py†L13-L80】
5. **PrevengosSyncService**. Coordina conciliaciones, exportaciones y peticiones API; además aplica lógica de desempate por `last_update` para evitar sobrescribir datos recientes.【F:app/integrations/prevengos/service.py†L14-L72】

Las extensiones Java (ejecutadas a través de `CLIAdapter`) se sitúan como consumidores o productores adicionales de CSV o JSON. Cada adaptador debe leer `stdin` y escribir `stdout` con el mismo contrato descrito aquí y documentado en `docs/extensibility-guide.md`.

## Modelos y contratos de datos

| Campo             | Tipo       | Descripción                                                                      |
|-------------------|------------|----------------------------------------------------------------------------------|
| `employee_nif`    | `string`   | Identificador fiscal del trabajador (sin espacios).                             |
| `contract_code`   | `string`   | Código de contrato/cliente según Prevengos.                                     |
| `course_code`     | `string`   | Código corto del curso (p. ej. `PRL-BASICO`).                                    |
| `status`          | `string`   | `pending`, `in_progress`, `completed` o `expired`.                               |
| `hours_completed` | `float`    | Horas completadas certificadas por Prevengos.                                    |
| `last_update`     | `datetime` | Fecha y hora en formato `YYYY-MM-DDTHH:MM:SS+ZZZZ` (zona horaria de la sede).    |
| `extra.*`         | `string`   | Campos opcionales (mutua, centro de trabajo, observaciones, etc.).              |

### CSV

- Cabecera fija con los campos anteriores. Los campos `extra.*` se añaden automáticamente cuando existen en el dataset.
- Codificación `utf-8-sig` para ser compatible con Excel en Windows.
- El fichero por defecto es `data/prevengos/training_status.csv`, configurable mediante `PREVENGOS_CSV_PATH`.

### API JSON (servicio de datos)

- Endpoints confirmados: `GET /contracts/{contract_code}` y `POST /training-records`.
- Autenticación: `Authorization: Bearer <token>`.
- Respuestas `POST` devuelven un array JSON con el estado aceptado o los errores de validación por registro.

### SQL Server

- Tabla recomendada: `prl_training_status` (o vista equivalente) con columnas alineadas con el modelo.
- Operaciones soportadas: lectura (`fetch_training_records`) y escritura de staging mediante `MERGE`. La escritura debe habilitarse explícitamente por el soporte de Prevengos.

## Flujo operativo

1. **Captura diaria desde Prevengos**
   1. `PrevengosDBAdapter.fetch_training_records()` obtiene el snapshot actualizado desde SQL Server.
   2. `PrevengosSyncService.reconcile_with_database()` fusiona la información con el CSV local respetando el `last_update` más reciente.【F:app/integrations/prevengos/service.py†L38-L61】
   3. Las apps escritorio y Android consumen el CSV consolidado (directamente o vía adaptadores Java).

2. **Envío de actualizaciones a Prevengos**
   1. Los operarios validan cambios en la UI o en las apps móviles.
   2. `PrevengosSyncService.export_records(..., push_to_api=True)` genera el CSV y llama a `POST /training-records` si se ha configurado el cliente HTTP.【F:app/integrations/prevengos/service.py†L25-L37】
   3. Prevengos responde con el estado de cada registro; se almacenan para auditoría (pendiente de integración con `NotificationDispatcher`).

3. **Consultas puntuales**
   - Para validar un CIF o contrato, `PrevengosSyncService.fetch_contract_metadata()` usa la API y retorna un diccionario con el detalle del contrato para su consumo por la UI o por scripts Java.【F:app/integrations/prevengos/service.py†L63-L71】

## Configuración

Añade las siguientes variables a `.env` o a tu gestor de secretos:

```
PREVENGOS_CSV_PATH=data/prevengos/training_status.csv
PREVENGOS_API_BASE_URL=https://prevengos.local/api
PREVENGOS_API_TOKEN=xxxxxx
PREVENGOS_DB_DSN=Driver={ODBC Driver 18 for SQL Server};Server=SRV01;Database=Prevengos;Trusted_Connection=yes;
```

El fichero `app/config.py` expone las claves anteriores mediante `Settings` para que cualquier módulo pueda consumirlas.【F:app/config.py†L29-L36】

## Procedimiento de despliegue

1. **Seguridad**
   - Verificar que el portal "Prevenweb" ejecuta la versión >= 2.48 antes de habilitar la API pública.
   - Limitar las IPs con acceso al SQL Server de Prevengos y usar autenticación integrada o credenciales por servicio.
   - Monitorizar logs de autenticación y activar alertas ante más de 5 errores consecutivos por token.

2. **Conectividad**
   - Configurar conectividad SFTP o carpeta compartida para el intercambio de CSV entre el servidor Prevengos y la extensión Java.
   - Abrir únicamente los puertos necesarios para el API (`443`) y para SQL Server (`1433`), preferiblemente sobre VPN corporativa.

3. **Validación**
   - Ejecutar `pytest tests/test_prevengos_integration.py` para validar los contratos antes de mover a producción.
   - Realizar una prueba de carga de CSV con 1 000 registros para comprobar latencias y comportamiento de Excel.
   - Coordinar con el soporte de Prevengos cualquier cambio en los formatos; actualiza este documento si se añaden campos.

## Roadmap y consideraciones

- **Extensión Android/Java**: empaquetar los adaptadores CLI en un `jar` único y configurarlos a través de `app/notify/adapters/cli.py`. Documenta el comando exacto en `workflows/playbooks/`.
- **Monitoreo**: integrar métricas Prometheus para contar registros sincronizados por canal y tiempos de respuesta del API.
- **Resiliencia**: planificar reintentos exponenciales sobre fallos `503` del API y colas diferidas para escritura en SQL Server.

Con esta arquitectura, la integración con Prevengos queda documentada y lista para operar tanto en escritorio como en Android, reutilizando la lógica existente del monolito FastAPI y permitiendo que las extensiones Java trabajen en paralelo.
