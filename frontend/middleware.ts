import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

const PROTECTED = ["/clients", "/statements", "/dashboard"];

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (!PROTECTED.some(p => pathname === p || pathname.startsWith(p + "/"))) {
    return NextResponse.next();
  }
  const token = await getToken({ req });
  if (!token) {
    const url = new URL("/auth/sign-in", req.url);
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/dashboard/:path*", "/clients/:path*", "/statements/:path*"] };