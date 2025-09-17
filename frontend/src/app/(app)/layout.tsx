import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import authConfig from "@/lib/auth.config";
import { SidebarProvider, Sidebar, SidebarInset } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";

export default async function AppLayout({ children }: { children: ReactNode }) {
  const session = await getServerSession(authConfig);
  if (!session) redirect("/auth/sign-in?next=" + encodeURIComponent("/dashboard"));

  return (
    <SidebarProvider defaultOpen>
      <Sidebar variant="inset">
        <AppSidebar />
      </Sidebar>
      <SidebarInset>
        {children}
      </SidebarInset>
    </SidebarProvider>
  );
}