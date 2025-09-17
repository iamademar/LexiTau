import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import authConfig from "@/lib/auth.config";

export default async function AppLayout({ children }: { children: ReactNode }) {
  const session = await getServerSession(authConfig);
  if (!session) redirect("/auth/sign-in?next=" + encodeURIComponent("/dashboard"));
  return children; // do not wrap; pages manage their own sidebar layout already
}