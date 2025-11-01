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
});
