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

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulta [LICENSE](LICENSE) para más detalles.
