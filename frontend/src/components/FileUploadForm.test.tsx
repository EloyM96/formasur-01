import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FileUploadForm } from "./FileUploadForm";

describe("FileUploadForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a success message when the upload API responds with 201", async () => {
    const mockResponse = {
      file: {
        original_name: "prl.xlsx",
        size: 1024,
        mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      },
      summary: {
        total_rows: 0,
        missing_columns: [],
        preview: [],
        errors: [],
      },
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

  it("renders the students list when the backend preview contains rows", async () => {
    const backendResponse = {
      file: {
        original_name: "reporte.xlsx",
        size: 512,
        mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      },
      summary: {
        total_rows: 2,
        missing_columns: [],
        preview: [
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
        ],
        errors: [],
      },
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

    const excelFile = new File(["contenido"], "reporte.xlsx", {
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

  it("shows an error when the backend preview lacks recognizable students", async () => {
    const backendResponse = {
      file: {
        original_name: "reporte.xlsx",
        size: 512,
        mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      },
      summary: {
        total_rows: 1,
        missing_columns: [],
        preview: [
          {
            Nombre: "Ana",
            Apellidos: "García",
            Correo: "ana@example.com",
          },
        ],
        errors: [],
      },
    };

    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(backendResponse), {
        status: 201,
        headers: {
          "Content-Type": "application/json",
        },
      })
    );

    const excelFile = new File(["contenido"], "reporte.xlsx", {
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
