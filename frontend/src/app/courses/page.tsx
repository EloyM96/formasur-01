import type { Metadata } from "next";
import Link from "next/link";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const metadata: Metadata = {
  title: "Cursos disponibles",
};

type CourseSummaryResponse = {
  total: number;
  items: CourseSummaryItem[];
};

type CourseSummaryItem = {
  course: CoursePayload;
  metrics: {
    total_enrollments: number;
    non_compliant_enrollments: number;
    zero_hours_enrollments: number;
  };
  notifications: {
    total: number;
    by_channel: Record<string, number>;
  };
};

type CoursePayload = {
  id: number | null;
  name: string;
  hours_required: number;
  deadline_date: string;
  source: string;
  source_reference: string | null;
  attributes: Record<string, unknown> | null;
  created_at: string;
};

async function loadCourses(): Promise<{ data: CourseSummaryResponse | null; error: string | null }> {
  try {
    const response = await fetch(`${API_BASE_URL}/courses`, {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`API respondió ${response.status}`);
    }

    const payload = (await response.json()) as CourseSummaryResponse;
    return { data: payload, error: null };
  } catch (error) {
    return {
      data: null,
      error: error instanceof Error ? error.message : "No se pudo cargar el listado de cursos",
    };
  }
}

function formatDate(value: string): string {
  try {
    return new Intl.DateTimeFormat("es-ES", {
      dateStyle: "medium",
    }).format(new Date(value));
  } catch (_error) {
    return value;
  }
}

function renderChannels(summary: Record<string, number>): string {
  const entries = Object.entries(summary);
  if (entries.length === 0) {
    return "Sin notificaciones";
  }
  return entries
    .map(([channel, count]) => `${channel}: ${count}`)
    .join(", ");
}

export default async function CoursesPage() {
  const { data, error } = await loadCourses();

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-8 px-6 py-10">
      <header className="space-y-2">
        <p className="text-sm font-semibold uppercase tracking-wide text-primary">Catálogo</p>
        <h1 className="text-3xl font-bold text-slate-900">Cursos disponibles</h1>
        <p className="text-base text-slate-600">
          Explora la formación importada desde los ficheros y comprueba su estado actual directamente desde la base
          de datos.
        </p>
      </header>

      {error ? (
        <p className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}. Inténtalo de nuevo más tarde.
        </p>
      ) : null}

      <section className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {data?.items.map(({ course, metrics, notifications }) => (
          <article key={course.id ?? course.name} className="flex h-full flex-col justify-between rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="space-y-3">
              <div className="space-y-1">
                <h2 className="text-xl font-semibold text-slate-900">{course.name}</h2>
                <p className="text-sm text-slate-600">
                  Fecha límite: {course.deadline_date ? formatDate(course.deadline_date) : "Sin definir"}
                </p>
                <p className="text-sm text-slate-600">Horas requeridas: {course.hours_required}</p>
                <p className="text-xs uppercase tracking-wide text-slate-400">Fuente: {course.source}</p>
              </div>
              <dl className="grid grid-cols-2 gap-3 text-sm text-slate-700">
                <div className="rounded-lg bg-slate-50 p-3">
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Matrículas totales</dt>
                  <dd className="mt-1 text-lg font-semibold text-slate-900">{metrics.total_enrollments}</dd>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Incumplimientos</dt>
                  <dd className="mt-1 text-lg font-semibold text-slate-900">{metrics.non_compliant_enrollments}</dd>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Sin horas reportadas</dt>
                  <dd className="mt-1 text-lg font-semibold text-slate-900">{metrics.zero_hours_enrollments}</dd>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Notificaciones enviadas</dt>
                  <dd className="mt-1 text-lg font-semibold text-slate-900">{notifications.total}</dd>
                </div>
              </dl>
              <p className="text-xs text-slate-500">Detalle por canal: {renderChannels(notifications.by_channel)}</p>
            </div>
            <div className="mt-6 flex justify-end">
              {course.id ? (
                <Link
                  href={`/courses/${course.id}`}
                  className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary/90"
                >
                  Ver alumnos
                </Link>
              ) : (
                <span className="inline-flex items-center rounded-lg bg-slate-200 px-3 py-2 text-sm font-semibold text-slate-600">
                  Curso sin identificador
                </span>
              )}
            </div>
          </article>
        ))}
        {data && data.items.length === 0 ? (
          <p className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">
            No se encontraron cursos en la base de datos.
          </p>
        ) : null}
        {!data && !error ? (
          <p className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">
            Cargando información de cursos...
          </p>
        ) : null}
      </section>
    </main>
  );
}
