import type { Metadata } from "next";
import Link from "next/link";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const metadata: Metadata = {
  title: "Detalle del curso",
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

type StudentEntry = {
  enrollment: {
    id: number | null;
    status: string;
    progress_hours: number;
    last_notified_at: string | null;
    deadline_date: string | null;
    hours_required: number | null;
    student: {
      id: number | null;
      full_name: string;
      email: string | null;
      certificate_expires_at: string | null;
    };
  };
  rule_results: Record<string, boolean>;
  violations: string[];
  has_no_activity: boolean;
  notifications: {
    total: number;
    by_channel: Record<string, number>;
  };
};

type CourseDetailResponse = {
  course: CoursePayload;
  students: StudentEntry[];
};

async function loadCourse(courseId: number): Promise<{ data: CourseDetailResponse | null; error: string | null }> {
  try {
    const response = await fetch(`${API_BASE_URL}/courses/${courseId}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`API respondió ${response.status}`);
    }

    const payload = (await response.json()) as CourseDetailResponse;
    return { data: payload, error: null };
  } catch (error) {
    return {
      data: null,
      error: error instanceof Error ? error.message : "No se pudo cargar el detalle del curso",
    };
  }
}

function formatDate(value: string | null): string {
  if (!value) {
    return "Sin fecha";
  }
  try {
    return new Intl.DateTimeFormat("es-ES", {
      dateStyle: "medium",
    }).format(new Date(value));
  } catch (_error) {
    return value;
  }
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "Sin registros";
  }
  try {
    return new Intl.DateTimeFormat("es-ES", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(value));
  } catch (_error) {
    return value;
  }
}

function formatHours(progress: number, required: number | null): string {
  const formattedProgress = progress.toLocaleString("es-ES", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
  if (required == null) {
    return `${formattedProgress} h`;
  }
  const formattedRequired = required.toLocaleString("es-ES");
  return `${formattedProgress} / ${formattedRequired} h`;
}

function renderViolations(violations: string[]): string {
  if (violations.length === 0) {
    return "Sin incidencias";
  }
  return violations.join(", ");
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

export default async function CourseDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const courseId = Number.parseInt(params.id, 10);
  if (Number.isNaN(courseId)) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-8 px-6 py-10">
        <p className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          El identificador del curso no es válido.
        </p>
      </main>
    );
  }

  const { data, error } = await loadCourse(courseId);

  if (error) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-8 px-6 py-10">
        <header className="space-y-2">
          <p className="text-sm font-semibold uppercase tracking-wide text-primary">Cursos</p>
          <h1 className="text-3xl font-bold text-slate-900">Detalle del curso</h1>
        </header>
        <p className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}. Inténtalo de nuevo más tarde.
        </p>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-8 px-6 py-10">
        <p className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-600">Cargando detalle del curso...</p>
      </main>
    );
  }

  const { course, students } = data;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-8 px-6 py-10">
      <header className="space-y-2">
        <p className="text-sm font-semibold uppercase tracking-wide text-primary">Cursos</p>
        <h1 className="text-3xl font-bold text-slate-900">{course.name}</h1>
        <p className="text-base text-slate-600">
          Revisa los alumnos matriculados, su progreso y las notificaciones emitidas para este curso.
        </p>
        <Link href="/courses" className="inline-flex items-center text-sm font-semibold text-primary hover:underline">
          ← Volver al listado de cursos
        </Link>
      </header>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Fecha límite</h2>
          <p className="mt-2 text-lg font-semibold text-slate-900">{formatDate(course.deadline_date)}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Horas requeridas</h2>
          <p className="mt-2 text-lg font-semibold text-slate-900">{course.hours_required}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Origen</h2>
          <p className="mt-2 text-lg font-semibold text-slate-900">{course.source}</p>
          {course.source_reference ? (
            <p className="text-xs text-slate-500">Referencia: {course.source_reference}</p>
          ) : null}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-slate-900">Alumnos matriculados</h2>
          <p className="text-sm text-slate-500">Total: {students.length}</p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Alumno
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Estado
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Progreso
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Certificado
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Última notificación
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Incidencias
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Notificaciones
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {students.map(({ enrollment, violations, has_no_activity, notifications }) => (
                <tr key={enrollment.id ?? `${enrollment.student.full_name}-${enrollment.student.email ?? "no-email"}`} className="align-top">
                  <td className="px-4 py-4 text-sm text-slate-700">
                    <div className="font-medium text-slate-900">{enrollment.student.full_name}</div>
                    <div className="text-xs text-slate-500">{enrollment.student.email ?? "Sin correo"}</div>
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-700">
                    <span className="inline-flex rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
                      {enrollment.status}
                    </span>
                    {has_no_activity ? (
                      <span className="ml-2 inline-flex rounded-full bg-amber-100 px-2 py-1 text-xs font-medium text-amber-800">
                        Sin actividad
                      </span>
                    ) : null}
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-700">
                    <div>{formatHours(enrollment.progress_hours, enrollment.hours_required)}</div>
                    <div className="text-xs text-slate-500">Límite: {formatDate(enrollment.deadline_date)}</div>
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-700">{formatDate(enrollment.student.certificate_expires_at)}</td>
                  <td className="px-4 py-4 text-sm text-slate-700">{formatDateTime(enrollment.last_notified_at)}</td>
                  <td className="px-4 py-4 text-sm text-slate-700">{renderViolations(violations)}</td>
                  <td className="px-4 py-4 text-sm text-slate-700">
                    <div>Total: {notifications.total}</div>
                    <div className="text-xs text-slate-500">{renderChannels(notifications.by_channel)}</div>
                  </td>
                </tr>
              ))}
              {students.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-sm text-slate-500">
                    No hay alumnos matriculados en este curso.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
