# Frontend PWA

Semilla de la PWA en Next.js para el proyecto **PRL Notifier**. Incluye Tailwind CSS, tipado con TypeScript y un
formulario básico de subida de ficheros listo para conectar con FastAPI.

## Scripts disponibles

```bash
npm run dev     # Arranca el entorno de desarrollo
npm run build   # Genera el build de producción
npm run start   # Sirve la build generada
npm run lint    # Ejecuta las reglas de ESLint
```

## Características clave

- Estructura `app/` con componentes reutilizables en `src/components`.
- Formulario accesible de subida de ficheros que conversa con `/api/upload`.
- Manifest y metadatos para evolución a PWA instalable.
- Tailwind CSS configurado para iteraciones rápidas de UI.

## Próximos pasos sugeridos

1. Conectar el endpoint `/api/upload` con el backend FastAPI y almacenamiento persistente.
2. Añadir validaciones y previsualización del contenido importado.
3. Cubrir los flujos críticos con pruebas end-to-end y monitorización.
