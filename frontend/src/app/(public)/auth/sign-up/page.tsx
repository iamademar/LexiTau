"use client";
import { useState } from "react";
import { signIn } from "next-auth/react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8001";

export default function SignUpPage() {
  const [email, setEmail] = useState("");
  const [business, setBusiness] = useState("");
  const [password, setPassword] = useState("");
  const [ok, setOk] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null); setOk(null);
    const resp = await fetch(`${BACKEND_URL}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, business_name: business }),
    });
    if (!resp.ok) {
      const j = await resp.json().catch(() => ({}));
      setErr(j?.detail ?? "Sign up failed");
      return;
    }
    setOk("Account created. Signing you in…");
    await signIn("credentials", { email, password, redirect: true, callbackUrl: "/dashboard" });
  }

  return (
    <main className="mx-auto max-w-sm px-6 py-16">
      <h1 className="text-2xl font-semibold">Create your account</h1>
      <form onSubmit={onSubmit} className="mt-6 grid gap-4">
        <input
          className="h-9 rounded-md border px-3"
          placeholder="Business name"
          value={business}
          onChange={e=>setBusiness(e.target.value)}
          required
        />
        <input
          className="h-9 rounded-md border px-3"
          placeholder="Email"
          type="email"
          value={email}
          onChange={e=>setEmail(e.target.value)}
          required
        />
        <input
          className="h-9 rounded-md border px-3"
          placeholder="Password"
          type="password"
          value={password}
          onChange={e=>setPassword(e.target.value)}
          required
        />
        {ok && <p className="text-sm text-green-700">{ok}</p>}
        {err && <p className="text-sm text-red-600">{err}</p>}
        <button className="h-9 rounded-md bg-primary px-4 text-primary-foreground text-sm">Create account</button>
      </form>
    </main>
  );
}