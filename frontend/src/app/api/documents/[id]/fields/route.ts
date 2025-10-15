import { NextRequest, NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

type Params = Promise<{ id: string }>;

export async function GET(_: NextRequest, ctx: { params: Params }) {
  const { id } = await ctx.params;
  const upstream = await apiFetch(`/documents/${id}/fields`, { method: "GET" });
  const body = await upstream.text();
  const contentType = upstream.headers.get("content-type") || "application/json";

  return new NextResponse(body, {
    status: upstream.status,
    headers: { "content-type": contentType },
  });
}