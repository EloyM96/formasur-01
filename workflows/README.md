# Workflows

Contendrá los playbooks y mapeos declarativos (YAML) que alimentan el motor de reglas y notificaciones.

- `playbooks/sample_prl_playbook.yaml`: blueprint mínimo con trigger CRON, quiet hours y acciones de ejemplo.
- `mappings/moodle_prl.yaml`: mapea columnas del XLSX a nombres internos usados por los modelos y reglas.

- [Backlog inicial — Semana 1](./backlog/initial-backlog.md)

## RGPD y operaciones

- Mantén los playbooks libres de PII: utiliza identificadores internos (`contact_id`, `job_id`) y deja que el motor haga el _lookup_ contra las tablas normalizadas (`contacts`, `enrollments`).
- Documenta en cada playbook las ventanas de silencio y la base legal empleada (consentimiento, interés legítimo, etc.) para facilitar las revisiones de cumplimiento.
- Versiona los mapeos indicando qué campos se consideran sensibles y cuándo deben anonimizarse en exportaciones u hojas de cálculo compartidas.
- Los pipelines de notificaciones registran automáticamente eventos en `job_events`, por lo que las tareas operativas (reintentos, cancelaciones) deben referenciar siempre el `job_id` en lugar de duplicar información personal.
