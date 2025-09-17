import { getServerSession } from "next-auth";
import authConfig from "@/lib/auth.config";
import { apiFetch } from "@/lib/api";
import { streamText } from "ai";

export async function POST(req: Request) {
  console.log("🚀 Chat API POST request received");

  const session = await getServerSession(authConfig);
  console.log("🔐 Session check:", {
    sessionExists: !!session,
    hasAccessToken: !!(session as any)?.accessToken,
    user: (session as any)?.user ? {
      id: (session as any).user.id,
      email: (session as any).user.email,
      business_id: (session as any).user.business_id
    } : null
  });

  const { messages } = await req.json();
  console.log("📨 Received messages:", JSON.stringify(messages, null, 2));

  // Extract the question from the last user message
  const lastUserMessage = messages?.slice().reverse().find((m: any) => m.role === "user");
  console.log("👤 Last user message:", lastUserMessage);

  const question = lastUserMessage?.parts
    ? lastUserMessage.parts
        .filter((p: any) => p?.type === "text")
        .map((p: any) => p.text)
        .join(" ")
        .trim()
    : (typeof lastUserMessage?.content === "string"
        ? lastUserMessage.content.trim()
        : (Array.isArray(lastUserMessage?.content)
            ? lastUserMessage.content
                .filter((p: any) => p?.type === "text")
                .map((p: any) => p.text)
                .join(" ")
                .trim()
            : ""));

  console.log("❓ Extracted question:", `"${question}"`, `(length: ${question.length})`);

  // Authentication check
  if (!(session as any)?.accessToken) {
    console.log("❌ No access token - returning auth error");
    return new Response("Please sign in to use analysis.", {
      status: 401,
      headers: { "Content-Type": "text/plain" }
    });
  }

  // Validation check
  if (!question || question.length < 3) {
    console.log("❌ Question too short - returning error");
    return new Response("Please ask a longer question (3+ characters).", {
      status: 400,
      headers: { "Content-Type": "text/plain" }
    });
  }

  console.log("🔄 Calling backend analysis endpoint...");
  console.log("📤 Request payload:", JSON.stringify({ question }));

  try {
    const resp = await apiFetch("/analysis/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    console.log("📥 Backend response:", {
      status: resp.status,
      statusText: resp.statusText,
      ok: resp.ok
    });

    let answerText = "I couldn't process your request.";

    if (resp.ok) {
      console.log("✅ Backend success response");
      try {
        const data = await resp.json();
        console.log("🔍 Success data:", data);
        // Use the answer field from AnalysisResponse
        answerText = data?.answer ?? "No answer provided";
      } catch {
        try {
          const responseText = await resp.text();
          console.log("🔍 Response text:", responseText);
          answerText = responseText;
        } catch {
          console.log("🔍 Could not parse success response");
        }
      }
    } else {
      console.log("❌ Backend error response");
      try {
        const errorData = await resp.json();
        console.log("🔍 Error data:", errorData);
        answerText = `Error ${resp.status}: ${errorData.detail || JSON.stringify(errorData)}`;
      } catch {
        try {
          const errorText = await resp.text();
          console.log("🔍 Error text:", errorText);
          answerText = `Error ${resp.status}: ${errorText}`;
        } catch {
          console.log("🔍 Could not parse error response");
          answerText = `Error ${resp.status}: Failed to get response`;
        }
      }
    }

    console.log("📝 Final answer text:", answerText);

    // Create a streaming response that Assistant-UI can understand
    // Based on the AI SDK data stream format
    console.log("🌊 Creating compatible streaming response");

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        try {
          // Split the answer into chunks for streaming effect
          const words = answerText.split(" ");
          const chunkSize = Math.max(1, Math.floor(words.length / 15)); // ~15 chunks

          // Send the stream in AI SDK format that Assistant-UI expects
          for (let i = 0; i < words.length; i += chunkSize) {
            const chunk = words.slice(i, i + chunkSize).join(" ");
            const textDelta = i + chunkSize < words.length ? chunk + " " : chunk;

            // Send text delta in the format: "0:{json}\n"
            const delta = JSON.stringify({ type: "text-delta", textDelta });
            controller.enqueue(encoder.encode(`0:${delta}\n`));

            // Small delay for visual streaming effect
            await new Promise(resolve => setTimeout(resolve, 80));
          }

          // Send finish message
          const finishMessage = JSON.stringify({ type: "finish", finishReason: "stop" });
          controller.enqueue(encoder.encode(`0:${finishMessage}\n`));

          // Send final data message
          const dataMessage = JSON.stringify({ finishReason: "stop", usage: { promptTokens: 0, completionTokens: 0 } });
          controller.enqueue(encoder.encode(`d:${dataMessage}\n`));

          controller.close();
        } catch (error) {
          console.error("❌ Stream error:", error);
          controller.error(error);
        }
      },
    });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Vercel-AI-Data-Stream": "v1",
      },
    });

  } catch (error) {
    console.error("❌ Error in chat endpoint:", error);
    return new Response("Internal server error", {
      status: 500,
      headers: { "Content-Type": "text/plain" }
    });
  }
}