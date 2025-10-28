import type { Metadata } from "next";

import { StudentsClientView } from "./StudentsClientView";
import type { NonComplianceResponse, StudentFilters } from "./types";

type SearchParams = Record<string, string | string[] | undefined>;

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DEFAULT_PLAYBOOK = process.env.NEXT_PUBLIC_DEFAULT_PLAYBOOK ?? "sample_prl_playbook";

export const metadata: Metadata = {
  title: "Alumnos en incumplimiento",
};

async function loadNonCompliance(
  searchParams: SearchParams,
): Promise<{ data: NonComplianceResponse | null; error: string | null }> {
  const params = new URLSearchParams();
  const allowedParams = [
    "course",
    "status",
    "deadline_before",
    "deadline_after",
    "min_hours",
    "max_hours",
    "rule",
  ];

  for (const key of allowedParams) {
    const raw = searchParams[key];
    const value = Array.isArray(raw) ? raw[0] : raw;
    if (value) {
      params.set(key, value);
    }
  }

  params.set("limit", "100");

  try {
    const response = await fetch(`${API_BASE_URL}/students/non-compliance?${params.toString()}`, {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`API respondió ${response.status}`);
    }
    const payload = (await response.json()) as NonComplianceResponse;
    return { data: payload, error: null };
  } catch (error) {
    return {
      data: null,
      error: error instanceof Error ? error.message : "No se pudo cargar el listado",
    };
  }
}

function extractFilters(searchParams: SearchParams): StudentFilters {
  return {
    course: pickFirst(searchParams.course),
    status: pickFirst(searchParams.status),
    deadline_before: pickFirst(searchParams.deadline_before),
    deadline_after: pickFirst(searchParams.deadline_after),
    min_hours: pickFirst(searchParams.min_hours),
    max_hours: pickFirst(searchParams.max_hours),
    rule: pickFirst(searchParams.rule),
  };
}

function pickFirst(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  return value ?? null;
}

export default async function StudentsPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const [{ data, error }] = await Promise.all([loadNonCompliance(searchParams)]);
  const filters = extractFilters(searchParams);
  const ruleOptions = data ? data.items.flatMap((item) => item.violations) : [];

  return (
    <StudentsClientView
      data={data}
      error={error}
      filters={filters}
      ruleOptions={ruleOptions}
      playbook={DEFAULT_PLAYBOOK}
    />
  );
}
