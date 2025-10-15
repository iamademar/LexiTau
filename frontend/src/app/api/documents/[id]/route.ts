// frontend/src/app/api/documents/[id]/route.ts
import { NextRequest, NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

type Params = Promise<{ id: string }>;

export async function GET(_: NextRequest, ctx: { params: Params }) {
  const { id } = await ctx.params; // ✅ await the params
  console.debug("GET /api/documents/%s", id);

  const upstream = await apiFetch(`/documents/${id}`, { method: "GET" });
  const body = await upstream.text();

  console.debug("GET /api/documents/%s -> upstream %d", id, upstream.status);

  return new NextResponse(body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") || "application/json",
    },
  });
}