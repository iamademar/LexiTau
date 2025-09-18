// frontend/src/app/api/documents/upload/route.ts
import { NextRequest, NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function POST(req: NextRequest) {
  const incoming = await req.formData();
  const form = new FormData();
  for (const [key, value] of incoming.entries()) {
    form.append(key, value as Blob);
  }

  const upstream = await apiFetch("/documents/upload", { method: "POST", body: form });
  const body = await upstream.text();
  return new NextResponse(body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") || "application/json",
    },
  });
}