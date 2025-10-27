import { NextResponse } from "next/server";

type UploadMetadata = {
  name: string;
  size: number;
  type: string;
};

export async function POST(request: Request) {
  const formData = await request.formData();
  const file = formData.get("file");

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "Fichero no proporcionado" }, { status: 400 });
  }

  const metadata: UploadMetadata = {
    name: file.name,
    size: file.size,
    type: file.type,
  };

  return NextResponse.json(metadata, { status: 201 });
}
