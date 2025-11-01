import { NextResponse } from "next/server";

const BACKEND_BASE_URL =
  process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function POST(request: Request) {
  const formData = await request.formData();
  const file = formData.get("file");

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "Fichero no proporcionado" }, { status: 400 });
  }

  const backendFormData = new FormData();
  backendFormData.append("file", file, file.name);

  try {
    const backendResponse = await fetch(`${BACKEND_BASE_URL}/uploads`, {
      method: "POST",
      body: backendFormData,
    });

    const responseHeaders = new Headers();
    const contentType = backendResponse.headers.get("content-type");
    if (contentType) {
      responseHeaders.set("content-type", contentType);
    }

    const payload = await backendResponse.text();

    return new NextResponse(payload, {
      status: backendResponse.status,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error("Upload proxy failed", error);
    return NextResponse.json(
      { error: "No se pudo contactar con el servicio de ingesta." },
      { status: 502 }
    );
  }
}
