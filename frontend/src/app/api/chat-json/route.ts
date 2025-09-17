import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import authConfig from "@/lib/auth.config";
import { apiFetch } from "@/lib/api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const session = await getServerSession(authConfig);
  const token = (session as any)?.accessToken as string | undefined;

  if (!token) {
    return NextResponse.json({ error: "Please sign in to use analysis." }, { status: 401 });
  }

  const { question } = await req.json().catch(() => ({ question: "" }));
  if (!question || String(question).trim().length < 3) {
    return NextResponse.json({ error: "Please ask a longer question (3+ characters)." }, { status: 400 });
  }

  const resp = await apiFetch("/analysis/run", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      // Forward auth to your FastAPI
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ question }),
  });

  let answerText = "I couldn't process your request.";
  if (resp.ok) {
    try {
      const data = await resp.json();
      answerText = data?.answer ?? "No answer provided";
    } catch {
      answerText = await resp.text();
    }
  } else {
    try {
      const err = await resp.json();
      answerText = `Error ${resp.status}: ${err?.detail ?? JSON.stringify(err)}`;
    } catch {
      answerText = `Error ${resp.status}: ${await resp.text()}`;
    }
  }

  // LocalRuntime expects you to return text — you can return the shape you want,
  // since you map it in LocalRuntime.run above.
  return NextResponse.json({ answer: answerText });
}