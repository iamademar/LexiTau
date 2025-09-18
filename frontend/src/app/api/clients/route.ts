import { NextRequest, NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

// NextAuth + headers() are Node-compatible; keep this on the Node runtime.
export const runtime = "nodejs";
// Avoid caching; always reflect latest server data
export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(req: NextRequest) {
  // Forward any query params ?q=&page=&limit= etc. to your backend
  const qs = req.nextUrl.searchParams.toString();
  const upstreamPath = qs ? `/clients?${qs}` : "/clients";

  const upstream = await apiFetch(upstreamPath, { method: "GET" });
  const contentType = upstream.headers.get("content-type") || "application/json";
  const body = await upstream.text();

  return new NextResponse(body, {
    status: upstream.status,
    headers: { "content-type": contentType },
  });
}

export async function POST(req: NextRequest) {
  const payload = await req.json();

  const upstream = await apiFetch("/clients", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });

  const contentType = upstream.headers.get("content-type") || "application/json";
  const body = await upstream.text();

  return new NextResponse(body, {
    status: upstream.status,
    headers: { "content-type": contentType },
  });
}