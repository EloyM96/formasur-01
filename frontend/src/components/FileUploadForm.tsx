"use client";

import { useState } from "react";

type UploadResponse = {
  name: string;
  size: number;
  type: string;
};

export function FileUploadForm() {
  const [status, setStatus] = useState<"idle" | "uploading" | "error" | "success">("idle");
  const [message, setMessage] = useState<string>("");
  const [result, setResult] = useState<UploadResponse | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const file = formData.get("file");

    if (!(file instanceof File)) {
      setStatus("error");
      setMessage("Selecciona un fichero antes de subirlo.");
      setResult(null);
      return;
    }

    setStatus("uploading");
    setMessage("Subiendo fichero...");
    setResult(null);

    try {
      const response = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("La API respondió con un error");
      }

      const json = (await response.json()) as UploadResponse;
      setStatus("success");
      setResult(json);
      setMessage("Subida completada correctamente.");
      event.currentTarget.reset();
    } catch (error) {
      console.error(error);
      setStatus("error");
      setMessage("No se pudo subir el fichero. Inténtalo de nuevo.");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-2xl bg-white p-6 shadow-md">
      <div>
        <label className="block text-sm font-medium text-slate-700" htmlFor="file">
          Selecciona un fichero
        </label>
        <input
          className="mt-2 block w-full cursor-pointer rounded-md border border-slate-200 bg-slate-50 p-2 text-sm text-slate-600 focus:border-primary focus:outline-none"
          type="file"
          id="file"
          name="file"
          accept=".csv,.xlsx,.xls,.json"
          required
        />
      </div>
      <button
        type="submit"
        className="inline-flex w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm transition hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
        disabled={status === "uploading"}
      >
        {status === "uploading" ? "Subiendo..." : "Subir fichero"}
      </button>
      {message && (
        <p
          className={`text-sm ${
            status === "error" ? "text-red-600" : status === "success" ? "text-green-600" : "text-slate-600"
          }`}
        >
          {message}
        </p>
      )}
      {result && (
        <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
          <p className="font-semibold">Resumen de la subida</p>
          <ul className="mt-2 space-y-1">
            <li>
              <span className="font-medium">Nombre:</span> {result.name}
            </li>
            <li>
              <span className="font-medium">Tamaño:</span> {(result.size / 1024).toFixed(2)} KB
            </li>
            <li>
              <span className="font-medium">Tipo:</span> {result.type || "Desconocido"}
            </li>
          </ul>
        </div>
      )}
    </form>
  );
}
