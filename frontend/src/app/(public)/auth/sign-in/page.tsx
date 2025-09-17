"use client";
import { useState } from "react";
import { signIn } from "next-auth/react";
import { useSearchParams, useRouter } from "next/navigation";

export default function SignInPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const search = useSearchParams();
  const router = useRouter();
  const next = search.get("next") || "/dashboard";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    const res = await signIn("credentials", { email, password, redirect: false });
    if (res?.error) setErr("Invalid email or password");
    else router.push(next);
  }

  return (
    <main className="mx-auto max-w-sm px-6 py-16">
      <h1 className="text-2xl font-semibold">Sign in</h1>
      <form onSubmit={onSubmit} className="mt-6 grid gap-4">
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
        {err && <p className="text-sm text-red-600">{err}</p>}
        <button className="h-9 rounded-md bg-primary px-4 text-primary-foreground text-sm">Continue</button>
      </form>
    </main>
  );
}