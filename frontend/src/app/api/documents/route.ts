// frontend/src/app/api/documents/route.ts
import { NextRequest, NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(req: NextRequest) {
  const qs = req.nextUrl.searchParams.toString();
  const upstreamPath = qs ? `/documents?${qs}` : "/documents";
  const upstream = await apiFetch(upstreamPath, { method: "GET" });
  const body = await upstream.text();

  return new NextResponse(body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") || "application/json",
    },
  });
}