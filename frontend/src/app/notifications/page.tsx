import Link from "next/link";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Notification = {
  id: number;
  playbook: string | null;
  channel: string;
  adapter: string;
  recipient: string | null;
  subject: string | null;
  status: string;
  created_at: string;
};

type NotificationResponse = {
  total: number;
  items: Notification[];
};

type MetadataResponse = {
  channels: string[];
  statuses: string[];
  adapters: string[];
  playbooks: string[];
};

type SearchParams = Record<string, string | string[] | undefined>;

async function loadNotifications(searchParams: SearchParams): Promise<{
  data: NotificationResponse | null;
  error: string | null;
}> {
  const params = new URLSearchParams();
  const allowedParams = [
    "status",
    "channel",
    "playbook",
    "adapter",
    "recipient",
    "search",
    "date_from",
    "date_to",
  ];

  for (const key of allowedParams) {
    const raw = searchParams[key];
    const value = Array.isArray(raw) ? raw[0] : raw;
    if (value) {
      params.set(key, value);
    }
  }

  params.set("limit", "25");

  try {
    const response = await fetch(`${API_BASE_URL}/notifications?${params.toString()}`, {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`API respondió ${response.status}`);
    }
    const data = (await response.json()) as NotificationResponse;
    return { data, error: null };
  } catch (error) {
    return {
      data: null,
      error: error instanceof Error ? error.message : "No se pudo cargar el listado",
    };
  }
}

async function loadMetadata(): Promise<MetadataResponse | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/notifications/metadata`, {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error("metadata request failed");
    }
    return (await response.json()) as MetadataResponse;
  } catch (error) {
    console.warn("No se pudo cargar metadata de notificaciones", error);
    return null;
  }
}

function formatDate(value: string): string {
  try {
    return new Intl.DateTimeFormat("es-ES", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(value));
  } catch (_error) {
    return value;
  }
}

function renderOptions(values: string[], placeholder: string) {
  return [
    <option key="placeholder" value="">
      {placeholder}
    </option>,
    ...values.map((value) => (
      <option key={value} value={value}>
        {value}
      </option>
    )),
  ];
}

export default async function NotificationsPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const [{ data, error }, metadata] = await Promise.all([
    loadNotifications(searchParams),
    loadMetadata(),
  ]);

  const activeFilters = {
    status: Array.isArray(searchParams.status) ? searchParams.status[0] : searchParams.status,
    channel: Array.isArray(searchParams.channel) ? searchParams.channel[0] : searchParams.channel,
    playbook: Array.isArray(searchParams.playbook) ? searchParams.playbook[0] : searchParams.playbook,
    adapter: Array.isArray(searchParams.adapter) ? searchParams.adapter[0] : searchParams.adapter,
    recipient: Array.isArray(searchParams.recipient) ? searchParams.recipient[0] : searchParams.recipient,
    search: Array.isArray(searchParams.search) ? searchParams.search[0] : searchParams.search,
    date_from: Array.isArray(searchParams.date_from) ? searchParams.date_from[0] : searchParams.date_from,
    date_to: Array.isArray(searchParams.date_to) ? searchParams.date_to[0] : searchParams.date_to,
  };

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-8 px-6 py-10">
      <header className="space-y-2">
        <p className="text-sm font-semibold uppercase tracking-wide text-primary">Auditoría</p>
        <h1 className="text-3xl font-bold text-slate-900">Histórico de notificaciones</h1>
        <p className="text-base text-slate-600">
          Consulta los envíos recientes, revisa el estado de cada canal y filtra por playbook, adaptador o destinatario.
        </p>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <form className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <select
            className="rounded-lg border border-slate-300 bg-white p-2 text-sm text-slate-700"
            name="status"
            defaultValue={activeFilters.status ?? ""}
          >
            {renderOptions(metadata?.statuses ?? [], "Estado")}
          </select>
          <select
            className="rounded-lg border border-slate-300 bg-white p-2 text-sm text-slate-700"
            name="channel"
            defaultValue={activeFilters.channel ?? ""}
          >
            {renderOptions(metadata?.channels ?? [], "Canal")}
          </select>
          <select
            className="rounded-lg border border-slate-300 bg-white p-2 text-sm text-slate-700"
            name="adapter"
            defaultValue={activeFilters.adapter ?? ""}
          >
            {renderOptions(metadata?.adapters ?? [], "Adaptador")}
          </select>
          <select
            className="rounded-lg border border-slate-300 bg-white p-2 text-sm text-slate-700"
            name="playbook"
            defaultValue={activeFilters.playbook ?? ""}
          >
            {renderOptions(metadata?.playbooks ?? [], "Playbook")}
          </select>
          <input
            className="rounded-lg border border-slate-300 p-2 text-sm text-slate-700"
            name="recipient"
            placeholder="Destinatario exacto"
            defaultValue={activeFilters.recipient ?? ""}
          />
          <input
            className="rounded-lg border border-slate-300 p-2 text-sm text-slate-700"
            name="search"
            placeholder="Buscar en asunto o destinatario"
            defaultValue={activeFilters.search ?? ""}
          />
          <input
            className="rounded-lg border border-slate-300 p-2 text-sm text-slate-700"
            type="datetime-local"
            name="date_from"
            defaultValue={activeFilters.date_from ?? ""}
          />
          <input
            className="rounded-lg border border-slate-300 p-2 text-sm text-slate-700"
            type="datetime-local"
            name="date_to"
            defaultValue={activeFilters.date_to ?? ""}
          />
          <div className="flex items-center gap-3">
            <button
              type="submit"
              className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary/90"
            >
              Aplicar filtros
            </button>
            <Link className="text-sm font-semibold text-primary hover:text-primary/80" href="/notifications" prefetch={false}>
              Limpiar
            </Link>
          </div>
        </form>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        {error && <p className="text-sm text-red-600">No se pudieron cargar las notificaciones: {error}</p>}
        {!error && data && data.items.length === 0 && (
          <p className="text-sm text-slate-600">No se encontraron notificaciones con los filtros actuales.</p>
        )}
        {!error && data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left">Fecha</th>
                  <th className="px-4 py-3 text-left">Playbook</th>
                  <th className="px-4 py-3 text-left">Canal</th>
                  <th className="px-4 py-3 text-left">Adaptador</th>
                  <th className="px-4 py-3 text-left">Destinatario</th>
                  <th className="px-4 py-3 text-left">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((notification) => (
                  <tr key={notification.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-slate-700">{formatDate(notification.created_at)}</td>
                    <td className="px-4 py-3 text-slate-700">{notification.playbook ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-700">{notification.channel}</td>
                    <td className="px-4 py-3 text-slate-700">{notification.adapter}</td>
                    <td className="px-4 py-3 text-slate-700">{notification.recipient ?? "—"}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                        {notification.status}
                      </span>
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
