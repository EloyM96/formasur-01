import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as XLSX from "xlsx";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FileUploadForm } from "./FileUploadForm";

describe("FileUploadForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a success message when the upload API responds with 201", async () => {
    const mockResponse = {
      name: "prl.xlsx",
      size: 1024,
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    };

    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockResponse), {
        status: 201,
        headers: {
          "Content-Type": "application/json",
        },
      })
    );

    render(<FileUploadForm />);

    const fileInput = screen.getByLabelText(/selecciona un fichero/i);
    const submitButton = screen.getByRole("button", { name: /subir fichero/i });

    const file = new File(["contenido"], "prl.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    await userEvent.upload(fileInput, file);
    await userEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Subida completada correctamente./i)).toBeInTheDocument();
    });

    expect(fetch).toHaveBeenCalledWith(
      "/api/upload",
      expect.objectContaining({
        method: "POST",
      })
    );
    expect(await screen.findByText(/Nombre:/i)).toBeInTheDocument();
  });

  it("maps backend metadata nested under file", async () => {
    const backendResponse = {
      file: {
        id: "uuid",
        original_name: "curso.xlsx",
        stored_path: "uploads/uuid.xlsx",
        mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        size: 2048,
      },
      summary: {},
      ingest: {},
    };

    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(backendResponse), {
        status: 201,
        headers: {
          "Content-Type": "application/json",
        },
      })
    );

    render(<FileUploadForm />);

    const fileInput = screen.getByLabelText(/selecciona un fichero/i);
    const submitButton = screen.getByRole("button", { name: /subir fichero/i });

    const file = new File(["contenido"], "curso.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    await userEvent.upload(fileInput, file);
    await userEvent.click(submitButton);

    expect(await screen.findByText(/curso.xlsx/)).toBeInTheDocument();
  });

  it("renders the students list when uploading an XLSX file", async () => {
    const backendResponse = {
      name: "reporte.xlsx",
      size: 512,
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    };

    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(backendResponse), {
        status: 201,
        headers: {
          "Content-Type": "application/json",
        },
      })
    );

    const worksheet = XLSX.utils.json_to_sheet([
      {
        Nombre: "María",
        Apellidos: "Pérez",
        Correo: "maria@example.com",
        "Tiempo total": "01h 30m 00s",
      },
      {
        Nombre: "Carlos",
        Apellidos: "López",
        Correo: "carlos@example.com",
        "Tiempo total": "00h 45m 00s",
      },
    ]);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Reporte");
    const excelBuffer = XLSX.write(workbook, { bookType: "xlsx", type: "array" });

    render(<FileUploadForm />);

    const fileInput = screen.getByLabelText(/selecciona un fichero/i);
    const submitButton = screen.getByRole("button", { name: /subir fichero/i });

    const excelFile = new File([excelBuffer], "reporte.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    await userEvent.upload(fileInput, excelFile);
    await userEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText("Carlos López")).toBeInTheDocument();
    });

    const studentItems = screen.getAllByRole("listitem");
    expect(studentItems).toHaveLength(2);
    expect(studentItems[0]).toHaveTextContent("Carlos López");
    expect(studentItems[0]).toHaveTextContent("00h 45m 00s");
    expect(studentItems[1]).toHaveTextContent("María Pérez");

    expect(screen.getByRole("button", { name: "Contactar a Carlos López" })).toBeInTheDocument();
    expect(screen.getByText("Se han detectado 2 alumnos en el curso.")).toBeInTheDocument();
  });

  it("shows an error when the spreadsheet has no recognizable students", async () => {
    const backendResponse = {
      name: "reporte.xlsx",
      size: 512,
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    };

    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(backendResponse), {
        status: 201,
        headers: {
          "Content-Type": "application/json",
        },
      })
    );

    const worksheet = XLSX.utils.json_to_sheet([
      {
        Nombre: "Ana",
        Apellidos: "García",
        Correo: "ana@example.com",
      },
    ]);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Reporte");
    const excelBuffer = XLSX.write(workbook, { bookType: "xlsx", type: "array" });
    const excelFile = new File([excelBuffer], "reporte.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    render(<FileUploadForm />);

    const fileInput = screen.getByLabelText(/selecciona un fichero/i);
    const submitButton = screen.getByRole("button", { name: /subir fichero/i });

    await userEvent.upload(fileInput, excelFile);
    await userEvent.click(submitButton);

    await waitFor(() => {
      expect(
        screen.getByText("No se encontraron alumnos en el fichero XLSX proporcionado.")
      ).toBeInTheDocument();
    });
  });
});
