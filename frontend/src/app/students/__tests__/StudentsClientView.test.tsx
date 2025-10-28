import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StudentsClientView } from "../StudentsClientView";
import type { NonComplianceResponse, StudentFilters } from "../types";

const sampleData: NonComplianceResponse = {
  total: 1,
  items: [
    {
      id: 1,
      status: "active",
      progress_hours: 4,
      last_notified_at: null,
      deadline_date: "2024-05-20",
      hours_required: 8,
      student: {
        id: 10,
        full_name: "Ana Pérez",
        email: "ana@example.com",
        certificate_expires_at: "2023-12-31",
      },
      course: {
        id: 20,
        name: "PRL Básico",
        deadline_date: "2024-05-20",
        hours_required: 8,
      },
      rule_results: {
        vencido: true,
        horas_insuficientes: true,
      },
      violations: ["vencido", "horas_insuficientes"],
    },
  ],
};

const sampleFilters: StudentFilters = {
  course: "PRL",
  status: "active",
  deadline_before: "2024-05-31",
  deadline_after: "2024-05-01",
  min_hours: "0",
  max_hours: null,
  rule: "vencido",
};

describe("StudentsClientView", () => {
  it("renders filters, summary and table rows", () => {
    render(
      <StudentsClientView
        data={sampleData}
        error={null}
        filters={sampleFilters}
        ruleOptions={["vencido", "horas_insuficientes"]}
        playbook="sample_prl_playbook"
      />,
    );

    expect(screen.getByLabelText("Curso")).toHaveValue("PRL");
    expect(screen.getByLabelText("Estado")).toHaveValue("active");
    expect(screen.getByLabelText("Fecha límite desde")).toHaveValue("2024-05-01");
    expect(screen.getByLabelText("Fecha límite hasta")).toHaveValue("2024-05-31");
    expect(screen.getByLabelText("Horas mínimas cursadas")).toHaveValue("0");

    expect(screen.getByRole("option", { name: "vencido" })).toBeInTheDocument();

    expect(screen.getByText("1 coincidencia")).toBeInTheDocument();
    expect(screen.getByText("Ana Pérez")).toBeInTheDocument();
    expect(screen.getByText("PRL Básico")).toBeInTheDocument();
    expect(screen.getByText("vencido")).toBeInTheDocument();
    expect(screen.getByText("horas_insuficientes")).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Dry-run" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Encolar" })).toBeInTheDocument();
  });
});
