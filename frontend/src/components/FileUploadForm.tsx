"use client";

import { useState } from "react";
import * as XLSX from "xlsx";

type UploadResponse = {
  name: string;
  size: number;
  type: string;
};

type ParsedStudent = {
  fullName: string;
  email: string | null;
  displayTime: string;
  totalSeconds: number;
};

export function FileUploadForm() {
  const [status, setStatus] = useState<"idle" | "uploading" | "error" | "success">("idle");
  const [message, setMessage] = useState<string>("");
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [students, setStudents] = useState<ParsedStudent[]>([]);

  const extractUploadMetadata = (payload: unknown): UploadResponse | null => {
    if (!payload || typeof payload !== "object") {
      return null;
    }

    const maybeDirect = payload as Partial<UploadResponse>;
    if (typeof maybeDirect.name === "string" && typeof maybeDirect.size === "number") {
      return {
        name: maybeDirect.name,
        size: maybeDirect.size,
        type: maybeDirect.type ?? "",
      } satisfies UploadResponse;
    }

    if ("file" in payload && payload.file && typeof payload.file === "object") {
      const fileInfo = payload.file as Record<string, unknown>;
      const name = typeof fileInfo.original_name === "string" ? fileInfo.original_name : "";
      const size = typeof fileInfo.size === "number" ? fileInfo.size : 0;
      const type =
        typeof fileInfo.mime === "string"
          ? fileInfo.mime
          : typeof fileInfo.type === "string"
            ? fileInfo.type
            : "";

      if (!name && !size && !type) {
        return null;
      }

      return {
        name,
        size,
        type,
      } satisfies UploadResponse;
    }

    return null;
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const formData = new FormData(formElement);
    const file = formData.get("file");

    if (!(file instanceof File)) {
      setStatus("error");
      setMessage("Selecciona un fichero antes de subirlo.");
      setResult(null);
      setStudents([]);
      return;
    }

    setStatus("uploading");
    setMessage("Subiendo fichero...");
    setResult(null);
    setStudents([]);

    try {
      const response = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("La API respondió con un error");
      }

      const contentType = response.headers.get("content-type") ?? "";
      let parsed: UploadResponse | null = null;

      if (contentType.includes("application/json")) {
        const payload = (await response.json()) as unknown;
        parsed = extractUploadMetadata(payload);
      }

      const shouldParseSpreadsheet = shouldParseAsSpreadsheet(file);

      if (shouldParseSpreadsheet) {
        try {
          const parsedStudents = await parseStudentsFromSpreadsheet(file);

          if (parsedStudents.length === 0) {
            setStatus("error");
            setMessage("No se encontraron alumnos en el fichero XLSX proporcionado.");
            setStudents([]);
            return;
          }

          setStatus("success");
          setStudents(parsedStudents);
          setMessage(
            `Se han detectado ${parsedStudents.length} alumno${
              parsedStudents.length === 1 ? "" : "s"
            } en el curso.`
          );
          setResult(null);
          formElement.reset();
          return;
        } catch (parseError) {
          console.error(parseError);
          setStatus("error");
          setMessage("No se pudo leer el fichero XLSX. Verifica el formato e inténtalo de nuevo.");
          setStudents([]);
          return;
        }
      }

      setStatus("success");
      setResult(parsed);
      setStudents([]);
      setMessage("Subida completada correctamente.");
      formElement.reset();
    } catch (error) {
      console.error(error);
      setStatus("error");
      setMessage("No se pudo subir el fichero. Inténtalo de nuevo.");
      setStudents([]);
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
          accept=".xlsx,.xls"
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
      {students.length > 0 && (
        <div className="space-y-3 rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
          <div>
            <p className="font-semibold text-slate-900">Alumnado detectado</p>
            <p className="text-xs text-slate-500">
              Ordenado de menor a mayor tiempo acumulado en el curso.
            </p>
          </div>
          <ul className="divide-y divide-slate-200">
            {students.map((student, index) => (
              <li key={`${student.fullName}-${student.email ?? index}`} className="flex flex-wrap items-center justify-between gap-4 py-3">
                <div>
                  <p className="font-medium text-slate-800">{student.fullName}</p>
                  {student.email && <p className="text-xs text-slate-500">{student.email}</p>}
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-sm font-semibold text-slate-700">{student.displayTime}</span>
                  <button
                    type="button"
                    className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-300 text-slate-500 transition hover:border-primary hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-1"
                    aria-label={`Contactar a ${student.fullName}`}
                  >
                    <MailIcon className="h-4 w-4" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </form>
  );
}

async function parseStudentsFromSpreadsheet(file: File): Promise<ParsedStudent[]> {
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: "array" });
  if (!workbook.SheetNames.length) {
    return [];
  }

  const sheet = workbook.Sheets[workbook.SheetNames[0]];
  if (!sheet) {
    return [];
  }

  const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, {
    defval: "",
    raw: false,
  });

  const parsed = rows
    .map((row) => {
      const firstName = getCellValue(row, [
        "Nombre",
        "Nombre(s)",
        "Nombre alumno",
        "First name",
        "Nombre estudiante",
      ]);
      const lastName = getCellValue(row, [
        "Apellidos",
        "Apellido",
        "Last name",
        "Apellidos alumno",
      ]);
      let fullName = `${firstName} ${lastName}`.trim();
      if (!fullName) {
        fullName = getCellValue(row, [
          "Nombre completo",
          "Nombre y apellidos",
          "Full name",
          "Alumno",
        ]);
      }

      const email = getCellValue(row, [
        "Correo",
        "Correo electrónico",
        "Correo electronico",
        "Email",
        "Email address",
      ]);

      const timeValue = getCellValue(row, [
        "Tiempo total",
        "Tiempo Total",
        "Tiempo total en el curso",
        "Tiempo total (curso)",
        "Total time",
        "Duración",
      ]);

      if (!fullName || !timeValue) {
        return null;
      }

      const totalSeconds = parseDurationToSeconds(timeValue);
      const displayTime = totalSeconds > 0 ? formatDuration(totalSeconds) : timeValue.trim();

      return {
        fullName,
        email: email || null,
        displayTime,
        totalSeconds,
      } satisfies ParsedStudent;
    })
    .filter((student): student is ParsedStudent => Boolean(student));

  return parsed.sort((a, b) => a.totalSeconds - b.totalSeconds);
}

function getCellValue(row: Record<string, unknown>, candidateNames: string[]): string {
  const entries = Object.entries(row).map(([key, value]) => [key.trim().toLowerCase(), value] as const);

  for (const candidate of candidateNames) {
    const normalizedCandidate = candidate.trim().toLowerCase();

    for (const [key, value] of entries) {
      if (key !== normalizedCandidate) {
        continue;
      }

      if (value === null || value === undefined) {
        continue;
      }

      if (typeof value === "number") {
        return value.toString();
      }

      if (typeof value === "string") {
        const trimmed = value.trim();
        if (trimmed) {
          return trimmed;
        }
      }
    }
  }

  return "";
}

function shouldParseAsSpreadsheet(file: File): boolean {
  const normalizedType = file.type.toLowerCase();
  const normalizedName = file.name.toLowerCase();

  return (
    normalizedType.includes("spreadsheet") ||
    normalizedType.includes("excel") ||
    normalizedName.endsWith(".xlsx") ||
    normalizedName.endsWith(".xls")
  );
}

function parseDurationToSeconds(input: string): number {
  const value = input.trim();
  if (!value) {
    return 0;
  }

  const colonMatch = value.match(/^([0-9]+):(\d{2})(?::(\d{2}))?$/);
  if (colonMatch) {
    const hours = Number.parseInt(colonMatch[1], 10);
    const minutes = Number.parseInt(colonMatch[2], 10);
    const seconds = colonMatch[3] ? Number.parseInt(colonMatch[3], 10) : 0;
    return hours * 3600 + minutes * 60 + seconds;
  }

  const normalized = value.toLowerCase();
  const hoursMatch = normalized.match(/(\d+(?:[.,]\d+)?)\s*(?:h|horas?)/);
  const minutesMatch = normalized.match(/(\d+(?:[.,]\d+)?)\s*(?:m|min|minutos?)/);
  const secondsMatch = normalized.match(/(\d+(?:[.,]\d+)?)\s*(?:s|seg|segundos?)/);

  let totalSeconds = 0;

  if (hoursMatch) {
    totalSeconds += Number.parseFloat(hoursMatch[1].replace(",", ".")) * 3600;
  }
  if (minutesMatch) {
    totalSeconds += Number.parseFloat(minutesMatch[1].replace(",", ".")) * 60;
  }
  if (secondsMatch) {
    totalSeconds += Number.parseFloat(secondsMatch[1].replace(",", "."));
  }

  if (totalSeconds > 0) {
    return Math.round(totalSeconds);
  }

  const numericParts = normalized.match(/\d+(?:[.,]\d+)?/g);
  if (numericParts) {
    if (numericParts.length === 3) {
      const [hours, minutes, seconds] = numericParts;
      return (
        Number.parseFloat(hours.replace(",", ".")) * 3600 +
        Number.parseFloat(minutes.replace(",", ".")) * 60 +
        Number.parseFloat(seconds.replace(",", "."))
      );
    }
    if (numericParts.length === 2) {
      const [hours, minutes] = numericParts;
      return (
        Number.parseFloat(hours.replace(",", ".")) * 3600 +
        Number.parseFloat(minutes.replace(",", ".")) * 60
      );
    }
    if (numericParts.length === 1) {
      return Number.parseFloat(numericParts[0].replace(",", ".")) * 3600;
    }
  }

  return 0;
}

function formatDuration(totalSeconds: number): string {
  if (!Number.isFinite(totalSeconds) || totalSeconds <= 0) {
    return "00h 00m 00s";
  }

  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);

  const pad = (value: number) => value.toString().padStart(2, "0");

  return `${pad(hours)}h ${pad(minutes)}m ${pad(seconds)}s`;
}

function MailIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <rect x="3" y="5" width="18" height="14" rx="2" ry="2" />
      <polyline points="3 7 12 13 21 7" />
    </svg>
  );
}
