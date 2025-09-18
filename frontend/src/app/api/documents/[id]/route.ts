// frontend/src/app/api/documents/[id]/route.ts
import { NextRequest, NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(_: NextRequest, { params }: { params: { id: string } }) {
  const upstream = await apiFetch(`/documents/${params.id}`, { method: "GET" });
  const body = await upstream.text();

  return new NextResponse(body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") || "application/json",
    },
  });
}