import { NextRequest, NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(_: NextRequest, { params }: { params: { id: string } }) {
  const upstream = await apiFetch(`/clients/${params.id}`, { method: "GET" });
  const body = await upstream.text();
  return new NextResponse(body, {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") || "application/json" },
  });
}

// If your backend supports it:
export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const payload = await req.json();
  const upstream = await apiFetch(`/clients/${params.id}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await upstream.text();
  return new NextResponse(body, {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") || "application/json" },
  });
}

// If delete isn't implemented yet, you can stub a 501 here and keep your UI's delete button:
export async function DELETE(_: NextRequest, { params }: { params: { id: string } }) {
  // Forward if backend supports it:
  // const upstream = await apiFetch(`/clients/${params.id}`, { method: "DELETE" });
  // return new NextResponse(null, { status: upstream.status });

  return new NextResponse(JSON.stringify({ error: "Not implemented" }), {
    status: 501,
    headers: { "content-type": "application/json" },
  });
}