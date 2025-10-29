# Backlog inicial — Semana 1

Visibilidad compartida de las tareas mínimas para arrancar el MVP y coordinar al equipo de becarios.

## Definition of Done (común)

### Calidad
- [ ] Logging estructurado (JSON) con correlación por `job_id` en cada feature.
- [ ] Gestión de reintentos con backoff exponencial documentada.
- [ ] Variables de entorno gestionadas vía `.env` + documentación de secretos.
- [ ] Estrategia de tests automatizados definida (unitarios, contract tests y smoke) y ejecutada en CI.

### Seguridad y RGPD
- [ ] Minimización de datos personales en modelos y logs.
- [ ] Procedimiento para atender solicitudes de acceso/borrado documentado.
- [ ] Configuración de cifrado en tránsito (HTTPS) preparada para despliegues.
- [ ] Revisión de cumplimiento RGPD (bases legales y consentimiento) validada con negocio.

## Issues registradas

| # | Issue | Responsable(s) | Objetivo semana 1 |
|---|-------|----------------|-------------------|
| 1 | Scaffold FastAPI + healthcheck | B3 | API lista para integraciones iniciales y despliegue local. |
| 2 | Subida de XLSX y guardado seguro | B3 · B5 | Aceptar cargas desde la PWA y persistir en almacenamiento temporal. |
| 3 | Parser XLSX + validaciones básicas | B5 | Detectar columnas obligatorias y producir reportes de errores tempranos. |
| 4 | Mapping YAML configurable | B5 | Soportar transformaciones declarativas alineadas con los playbooks. |
| 5 | Motor de reglas (puro) con helpers de fechas | B3 | Definir evaluación determinista reutilizable desde dry-run/ejecución. |
| 6 | Dry-run con resumen por canal | B1 · B3 | Mostrar simulación end-to-end antes de disparar notificaciones reales. |
| 7 | SMTP email (plantillas Jinja2) | B4 | Envío de correos transaccionales desde la cola de notificaciones. |
| 8 | Adaptador WhatsApp dummy (CLI) | B4 | Validar contrato CLI con respuesta mockeada para becarios Java. |
| 9 | RQ + Redis + backoff + quiet hours | B3 · B4 | Orquestar trabajos asíncronos respetando ventanas de silencio. |
| 10 | Auditoría de notificaciones + UI | B1 · B2 | Pantalla para seguimiento y filtros básicos de envíos. |
| 11 | Docker Compose (api/redis/sqlserver) | B3 · B4 | Facilitar entorno compartido reproducible para todo el equipo. |
| 12 | Tests mínimos + CI | B5 | Pipeline inicial (lint + unit) ejecutándose en cada push. |

## Asignación rápida por persona

- **B1 (Lead frontend):** Issue 6 (junto a B3) e Issue 10 (con B2). Coordina la integración con Next.js.
- **B2 (Frontend):** Issue 10 y soporte a B1 en flujos UI.
- **B3 (Backend core):** Issues 1, 2, 5, 6, 9 y 11 junto a B4.
- **B4 (Backend/adaptadores):** Issues 7, 8, 9 y 11.
- **B5 (Datos/QA/docs):** Issues 2, 3, 4 y 12.

> Cada issue debe cerrarse cumpliendo la Definition of Done y enlazando evidencias (logs, capturas, pruebas).
