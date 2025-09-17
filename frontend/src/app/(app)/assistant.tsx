"use client";

import { AssistantRuntimeProvider, useLocalRuntime } from "@assistant-ui/react";
import { Thread } from "@/components/assistant-ui/thread";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { Separator } from "@/components/ui/separator";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

function extractUserText(last: any): string {
  if (!last) return "";
  if (typeof last.content === "string") return last.content.trim();
  if (Array.isArray(last.content))
    return last.content.filter((p: any) => p?.type === "text").map((p: any) => p.text).join(" ").trim();
  if (Array.isArray(last.parts))
    return last.parts.filter((p: any) => p?.type === "text").map((p: any) => p.text).join(" ").trim();
  return "";
}

export const Assistant = () => {
  const runtime = useLocalRuntime({
    // No streaming — just return JSON content for the last user message
    run: async ({ messages }) => {
      const last = messages[messages.length - 1];
      const question = extractUserText(last);
      const res = await fetch("/api/chat-json", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      // Handle auth / error
      if (!res.ok) {
        const errText = await res.text().catch(() => "Unknown error");
        return { content: [{ type: "text", text: `Error ${res.status}: ${errText}` }] };
      }

      const data = await res.json().catch(() => ({}));
      const answerText = data?.answer ?? data?.response ?? data?.text ?? "No answer provided";
      return { content: [{ type: "text", text: answerText }] };
    },
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset>
          <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
            <SidebarTrigger />
            <Separator orientation="vertical" className="mr-2 h-4" />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem className="hidden md:block">
                  <BreadcrumbLink href="#">
                    LexExtract
                  </BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden md:block" />
                <BreadcrumbItem>
                  <BreadcrumbPage>
                    Chat Interface
                  </BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </header>
          <Thread />
        </SidebarInset>
      </SidebarProvider>
    </AssistantRuntimeProvider>
  );
};
