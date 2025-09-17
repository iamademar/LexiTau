import { getServerSession } from "next-auth";
import authConfig from "@/lib/auth.config";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8001";

export async function apiFetch(path: string, init?: RequestInit) {
  const session = await getServerSession(authConfig);
  const headers = new Headers(init?.headers);

  if ((session as any)?.accessToken) {
    headers.set("Authorization", `Bearer ${(session as any).accessToken}`);
    console.log("apiFetch: attaching Authorization header");
  } else {
    console.warn("apiFetch: NO accessToken found on session");
  }

  const resp = await fetch(`${BACKEND_URL}${path}`, { ...init, headers });
  return resp;
}