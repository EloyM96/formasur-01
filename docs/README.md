# Guía completa del repositorio

Este directorio reúne toda la documentación funcional y técnica del proyecto **prl-notifier**. Está organizada por rutas de aprendizaje para que cualquier perfil —desde operarios sin experiencia técnica hasta personal docente o desarrolladores senior— pueda comprender cómo se procesa la información, qué decisiones arquitectónicas se han tomado y cómo extender la plataforma.

## Índice sugerido

1. [Introducción y visión general](./overview.md) — contexto del problema, mapa de carpetas y flujo de datos extremo a extremo.
2. [Arquitectura y modelos de datos](./system-architecture.md) — detalle de los módulos backend, el motor de reglas, la cola de notificaciones y el esquema relacional.
3. [Operaciones diarias y runbook](./operations-runbook.md) — pasos para cargar XLSX, lanzar simulaciones, ejecutar playbooks y comprender los registros operativos.
4. [Pruebas, datos de ejemplo y QA](./testing-guide.md) — cómo preparar un entorno reproducible, ejecutar `pytest` y validar reglas o plantillas.
5. [Extensión e integraciones avanzadas](./extensibility-guide.md) — contratos JSON, adaptadores Java, conexión con Moodle Web Services y otros conectores.
6. [Integración bidireccional con Prevengos](./prevengos-integration.md) — arquitectura específica para el ERP de PRL, checklist de seguridad y configuración.

Cada documento enlaza con los módulos exactos del repositorio y con los playbooks declarativos del directorio `workflows/` para que puedas contrastar teoría con implementación. Si prefieres un recorrido paso a paso, sigue el índice en orden; si ya conoces la plataforma, ve directamente al tema de interés.

> **Consejo**: además de esta documentación, la guía operativa beta original se mantiene en [`docs/beta_operational_manual.md`](./beta_operational_manual.md) y complementa los escenarios descritos aquí con referencias directas a endpoints REST.
