import Link from "next/link";

import { FileUploadForm } from "@/components/FileUploadForm";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-slate-100 via-slate-50 to-slate-200 p-6">
      <div className="w-full max-w-3xl space-y-10">
        <section className="space-y-4 text-center">
          <p className="text-sm font-semibold uppercase tracking-wide text-primary">Semana 1</p>
          <h1 className="text-3xl font-bold text-slate-900 sm:text-4xl">Semilla del frontend PRL Notifier</h1>
          <p className="text-base text-slate-600">
            PWA base en Next.js con soporte para subir ficheros preventivos y preparar la integración con
            FastAPI y los contratos JSON definidos en el roadmap.
          </p>
        </section>
        <FileUploadForm />
        <section className="rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Auditoría de notificaciones</h2>
          <p className="mt-2 text-sm text-slate-600">
            Consulta el histórico de envíos, filtra por canal y revisa el detalle de cada intento registrado en
            el backend.
          </p>
          <Link
            href="/notifications"
            className="mt-4 inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary/90"
          >
            Abrir panel de notificaciones
          </Link>
        </section>
        <section className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-600">
          <h2 className="text-base font-semibold text-slate-900">Próximos pasos sugeridos</h2>
          <ul className="mt-4 list-disc space-y-2 pl-5 text-left">
            <li>Conectar este formulario con el endpoint de ingesta de FastAPI.</li>
            <li>Persistir metadatos del fichero en PostgreSQL siguiendo el esquema acordado.</li>
            <li>Sincronizar reglas de validación desde los YAML del motor.</li>
            <li>Priorizar entregables de Semana 1 en el backlog compartido y coordinarse con los responsables asignados.</li>
          </ul>
        </section>
      </div>
    </main>
  );
}
