import Link from "next/link";
export const revalidate = 60;

export default function PublicHome() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-semibold">Welcome to LexiTau</h1>
      <p className="mt-3 text-muted-foreground">
        Advanced document extraction and analysis platform for financial statements.
      </p>
      <div className="mt-8 flex gap-3">
        <Link href="/auth/sign-in?next=/dashboard" className="inline-flex rounded-md bg-primary px-4 py-2 text-primary-foreground text-sm hover:bg-primary/90">
          Sign in
        </Link>
        <Link href="/auth/sign-up" className="inline-flex rounded-md border px-4 py-2 text-sm hover:bg-accent">
          Create account
        </Link>
      </div>
    </main>
  );
}