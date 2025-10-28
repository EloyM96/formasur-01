"use client";

import { useMemo, useState } from "react";

import type { NonComplianceResponse, StudentFilters } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type MessageState = { type: "success" | "error"; text: string } | null;

type StudentsClientViewProps = {
  data: NonComplianceResponse | null;
  error: string | null;
  filters: StudentFilters;
  ruleOptions: string[];
  playbook: string;
};

export function StudentsClientView({ data, error, filters, ruleOptions, playbook }: StudentsClientViewProps) {
  const [message, setMessage] = useState<MessageState>(null);
  const [loading, setLoading] = useState<"dry-run" | "execute" | null>(null);

  const hasRows = Boolean(!error && data && data.items.length > 0);

  const formattedRuleOptions = useMemo(() => Array.from(new Set(ruleOptions)), [ruleOptions]);

  const handleAction = async (mode: "dry-run" | "execute") => {
    setLoading(mode);
    setMessage(null);

    try {
      const endpoint = `${API_BASE_URL}/workflows/${playbook}/${mode === "dry-run" ? "dry-run" : "execute"}`;
      const response = await fetch(endpoint, { method: "POST" });
      if (!response.ok) {
        throw new Error(`API respondió ${response.status}`);
      }
      const payload = (await response.json()) as { enqueued_actions?: number; matched_actions?: number };
      const summary =
        mode === "dry-run"
          ? `Dry-run completado: ${payload.matched_actions ?? 0} coincidencias`
          : `Ejecución encolada: ${payload.enqueued_actions ?? 0} acciones`;
      setMessage({ type: "success", text: summary });
    } catch (actionError) {
      setMessage({
        type: "error",
        text:
          actionError instanceof Error
            ? actionError.message
            : "No se pudo ejecutar la acción solicitada",
      });
    } finally {
      setLoading(null);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-8 px-6 py-10">
      <header className="space-y-2">
        <p className="text-sm font-semibold uppercase tracking-wide text-primary">Cumplimiento</p>
        <h1 className="text-3xl font-bold text-slate-900">Alumnos en riesgo de incumplimiento</h1>
        <p className="text-base text-slate-600">
          Filtra matrículas con certificados vencidos o horas insuficientes y lanza notificaciones de seguimiento desde los playbooks.
        </p>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <form className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            <span>Curso</span>
            <input
              className="rounded-lg border border-slate-300 p-2 text-sm text-slate-700"
              name="course"
              placeholder="Curso"
              defaultValue={filters.course ?? ""}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            <span>Estado</span>
            <input
              className="rounded-lg border border-slate-300 p-2 text-sm text-slate-700"
              name="status"
              placeholder="Estado"
              defaultValue={filters.status ?? ""}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            <span>Fecha límite desde</span>
            <input
              className="rounded-lg border border-slate-300 p-2 text-sm text-slate-700"
              type="date"
              name="deadline_after"
              defaultValue={filters.deadline_after ?? ""}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            <span>Fecha límite hasta</span>
            <input
              className="rounded-lg border border-slate-300 p-2 text-sm text-slate-700"
              type="date"
              name="deadline_before"
              defaultValue={filters.deadline_before ?? ""}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            <span>Horas mínimas cursadas</span>
            <input
              className="rounded-lg border border-slate-300 p-2 text-sm text-slate-700"
              type="number"
              step="0.5"
              name="min_hours"
              placeholder="0"
              defaultValue={filters.min_hours ?? ""}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            <span>Horas máximas cursadas</span>
            <input
              className="rounded-lg border border-slate-300 p-2 text-sm text-slate-700"
              type="number"
              step="0.5"
              name="max_hours"
              placeholder=""
              defaultValue={filters.max_hours ?? ""}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            <span>Regla</span>
            <select
              className="rounded-lg border border-slate-300 bg-white p-2 text-sm text-slate-700"
              name="rule"
              defaultValue={filters.rule ?? ""}
            >
              <option value="">Todas</option>
              {formattedRuleOptions.map((rule) => (
                <option key={rule} value={rule}>
                  {rule}
                </option>
              ))}
            </select>
          </label>
          <div className="flex items-end gap-3">
            <button
              type="submit"
              className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary/90"
            >
              Aplicar filtros
            </button>
            <a className="text-sm font-semibold text-primary hover:text-primary/80" href="/students">
              Limpiar
            </a>
          </div>
        </form>
      </section>

      <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Listado de matrículas</h2>
            <p className="text-sm text-slate-600">
              {data ? `${data.total} coincidencia${data.total === 1 ? "" : "s"}` : "Sin resultados disponibles"}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => handleAction("dry-run")}
              disabled={loading !== null}
              className="rounded-lg border border-primary px-4 py-2 text-sm font-semibold text-primary transition hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading === "dry-run" ? "Simulando..." : "Dry-run"}
            </button>
            <button
              type="button"
              onClick={() => handleAction("execute")}
              disabled={loading !== null}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading === "execute" ? "Encolando..." : "Encolar"}
            </button>
          </div>
        </div>

        {message && (
          <p
            role="status"
            className={`text-sm ${message.type === "success" ? "text-emerald-600" : "text-red-600"}`}
          >
            {message.text}
          </p>
        )}

        {error && (
          <p className="text-sm text-red-600">No se pudieron cargar los alumnos: {error}</p>
        )}

        {!error && data && data.items.length === 0 && (
          <p className="text-sm text-slate-600">No hay matrículas en incumplimiento con los filtros actuales.</p>
        )}

        {hasRows && (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left">Alumno</th>
                  <th className="px-4 py-3 text-left">Curso</th>
                  <th className="px-4 py-3 text-left">Fecha límite</th>
                  <th className="px-4 py-3 text-left">Horas cursadas</th>
                  <th className="px-4 py-3 text-left">Horas requeridas</th>
                  <th className="px-4 py-3 text-left">Vencimiento certificado</th>
                  <th className="px-4 py-3 text-left">Reglas activas</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data?.items.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-slate-700">
                      <div className="font-semibold">{item.student.full_name}</div>
                      <div className="text-xs text-slate-500">{item.student.email}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{item.course?.name ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-700">{formatDate(item.deadline_date)}</td>
                    <td className="px-4 py-3 text-slate-700">{item.progress_hours.toFixed(1)}</td>
                    <td className="px-4 py-3 text-slate-700">{item.hours_required ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-700">{formatDate(item.student.certificate_expires_at)}</td>
                    <td className="px-4 py-3 text-slate-700">
                      <div className="flex flex-wrap gap-2">
                        {item.violations.map((violation) => (
                          <span
                            key={violation}
                            className="inline-flex rounded-full bg-rose-100 px-2 py-1 text-xs font-semibold text-rose-700"
                          >
                            {violation}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }
  try {
    return new Intl.DateTimeFormat("es-ES", { dateStyle: "medium" }).format(new Date(value));
  } catch (_error) {
    return value;
  }
}
