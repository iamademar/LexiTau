# High-level blueprint

## Goals

* Ship a minimal but production-grade **Assistant UI** wired to your backend.
* Include a **typed form pipeline** (RHF + Zod) as a second feature.
* Bake in **tests, linting, CI, and error handling** from day one.
* No orphaned code: every artifact is rendered, linked, and covered by tests.

## Architecture (thin UI, typed edges)

* **Next.js 15 (App Router)** serving:

  * `/` — Assistant panel (streams or single JSON) + Sample form.
  * `/api/chat` — proxy to `BACKEND_URL/vanna/analysis` (Option A), preserving streaming or JSON.
* **Styling**: Tailwind v4 (postcss zero-config) + tiny Radix wrappers.
* **Validation**: Zod schema → RHF resolver on client; server validates payloads again in proxy.
* **Tests**: Vitest + Testing Library (unit/component) + Playwright (e2e).
* **DX/CI**: Biome or ESLint+Prettier, type-check, test, build on PR; preview env variables.

---

# Iteration plan (coarse → fine)

## Milestone A — Foundations (scaffold + styles)

1. Create `/frontend` Next app; add Tailwind v4 pipeline; global theme tokens.
2. Add helpers (`cn`) and base UI atoms (Button, Input, Label, Dialog, Form helpers).
3. Commit + smoke test that the page renders.

**Exit criteria**: `pnpm dev` renders a page with two cards and no console errors.

## Milestone B — Assistant UI + proxy

1. Add `Assistant.tsx` with `@assistant-ui/*`; wire to `/api/chat`.
2. Implement `/api/chat` (Option A): forward JSON to `/vanna/analysis` with `BACKEND_URL`.
3. Add error guards (timeouts, non-200 mapping to UI).

**Exit criteria**: Typing a message yields a response (stream or single), or a friendly error.

## Milestone C — Form demo (RHF + Zod)

1. Add `SampleForm` with a Zod schema + inline validation.
2. Add submit handler (local log now), success/failure UI states.
3. Unit tests: schema constraints and UI errors show/hide correctly.

**Exit criteria**: Form rejects invalid email, accepts valid, test suite passes.

## Milestone D — Testing & quality gates

1. Add **Vitest** + Testing Library; write unit & component tests.
2. Add **Playwright** e2e: render Assistant + round-trip via mocked backend.
3. Add lint/type/format scripts and pre-commit hooks (optional).

**Exit criteria**: `pnpm test`, `pnpm test:e2e`, `pnpm typecheck` pass locally and in CI.

## Milestone E — Hardening & docs

1. Add `AbortController` timeout and user-facing errors for `/api/chat`.
2. Add minimal README (how to run, envs, commands) and `.env.local.example`.
3. (Optional) Dockerfile + docker-compose override for full-stack dev.

**Exit criteria**: README accurate; errors surface gracefully; build is reproducible.

---

# Work breakdown (right-sized steps)

### A. Foundations

* A1. Scaffold Next.js app in `/frontend`.
* A2. Tailwind v4 postcss config + `globals.css` theme.
* A3. Add `tsconfig` baseUrl/paths.
* A4. Add `lib/utils.ts (cn)`.
* A5. Create UI atoms: `button.tsx`, `input.tsx`, `label.tsx`, `dialog.tsx`, `form.tsx`.
* A6. Home layout with two sections (Assistant + Form).

### B. Assistant + proxy

* B1. `Assistant.tsx` with `AssistantRuntimeProvider`, `Thread`, markdown.
* B2. `/api/chat/route.ts` forwarding to `${BACKEND_URL}/vanna/analysis`.
* B3. Env: `.env.local BACKEND_URL=http://localhost:8001`.
* B4. Error states: network fail, non-200, invalid JSON.
* B5. Streaming: passthrough body if backend streams; fallback to JSON.

### C. Form demo

* C1. Install RHF + Zod; define `Schema`.
* C2. `SampleForm` with RHF resolver and inline error text.
* C3. Unit tests for schema + UI error rendering.

### D. Tests & CI

* D1. Add Vitest + RTL config; sample Button test.
* D2. Component test for Assistant renders and calls API (mock fetch).
* D3. Playwright: visit `/`, send message, assert UI update with mock.
* D4. CI workflow: install, typecheck, unit, e2e (headed=false).

### E. Hardening & docs

* E1. `AbortController` with 25s default; map to 504 UI state.
* E2. Telemetry hooks (console for now) when errors occur.
* E3. README + `.env.local.example`.

---

# Double-refined micro-steps (safe, incremental)

1. Init project & deps (`create-next-app`, packages).
2. Add Tailwind v4 `postcss.config.mjs` + `globals.css` theme tokens.
3. Wire `layout.tsx` and basic `page.tsx` two-column layout.
4. Add `cn`, Button, Input, Label, Dialog, Form helpers; render Button/Inputs on home.
5. Create `Assistant.tsx` with runtime + markdown; stub `/api/chat`.
6. Implement `/api/chat` Option A (JSON to `/vanna/analysis`); add `.env.local`.
7. Add error handling (try/catch, status mapping), show alert text in Assistant card.
8. Add `SampleForm` with Zod schema and inline errors; show success toast (console log ok).
9. Add Vitest/RTL; write tests for `cn`, Button, Input, Form errors.
10. Mock `fetch` in test for `/api/chat`; test happy/error paths.
11. Add Playwright e2e; mock network; verify user flow.
12. Add `AbortController` + timeout; surface to UI; tests for timeout path.
13. Add CI workflow (Node 20, pnpm, cache); run typecheck, unit, e2e.
14. README and env example; strip dead code.

---

# Test strategy (short)

* **Unit**: utils (`cn`), form schema, proxy handler edge cases.
* **Component**: Assistant render, markdown, error banners; form field errors.
* **E2E**: Happy path Assistant (mocked network), form submit UX.

---

# TDD prompts for a code-gen LLM

> Each prompt is **self-contained**, asks for **tests first**, then implementation, and ends with **wiring + verification**. Copy a prompt, run it, commit, repeat.

## Prompt 1 — Initialize frontend skeleton

```text
You are a senior Next.js engineer. Implement the following in /frontend.

GOAL
- Scaffold a Next.js 15 app with TypeScript in /frontend.
- Add scripts: dev, build, start, typecheck, test (placeholder).
- Use pnpm.

TASKS
1) Run: npx create-next-app@latest . --ts --eslint --app --src-dir
2) Add packages:
   pnpm add react react-dom next typescript
   pnpm add clsx tailwind-merge class-variance-authority
   pnpm add -D @tailwindcss/postcss postcss autoprefixer
3) Ensure package.json has:
   "scripts": { "dev": "next dev", "build": "next build", "start": "next start", "typecheck": "tsc --noEmit", "test": "vitest" }

TESTS (write first; commit with a failing placeholder)
- Create tests/setup placeholder that just asserts true (to verify runner).

DELIVERABLES
- Commit: "feat(frontend): scaffold Next.js app and baseline scripts"
- Verify: pnpm dev runs and renders default page.
```

## Prompt 2 — Tailwind v4 + theme

```text
GOAL
- Add Tailwind v4 via postcss; light/dark theme tokens.

TASKS
1) Create postcss.config.mjs with:
   export default { plugins: { '@tailwindcss/postcss': {}, autoprefixer: {} } }
2) Create src/app/globals.css with:
   @import "tailwindcss";
   @theme inline { --color-bg: oklch(99% 0.01 250); --color-fg: oklch(20% 0.03 260); --radius: 16px; }
   :root { color-scheme: light dark; }
   html, body, #__next { height: 100%; }
   body { background: var(--color-bg); color: var(--color-fg); }
3) Ensure layout.tsx imports "./globals.css".

TESTS
- Component smoke test to render a div with Tailwind class 'rounded-2xl' and assert it exists (Testing Library).

DELIVERABLES
- Commit: "feat(tailwind): configure v4 postcss and global theme"
- Verify UI loads with no style errors.
```

## Prompt 3 — TS paths + utils

```text
GOAL
- Add tsconfig paths and a cn() utility.

TASKS
1) Update tsconfig.json compilerOptions: baseUrl=src and paths for "@/*", "@/components/*", "@/lib/*", "@/app/*".
2) Create src/lib/utils.ts:
   import { clsx } from "clsx";
   import { twMerge } from "tailwind-merge";
   export function cn(...inputs: any[]) { return twMerge(clsx(inputs)); }

TESTS
- Unit tests for cn(): merging duplicates, conditional classes.

DELIVERABLES
- Commit: "feat(paths): tsconfig paths and cn() helper"
```

## Prompt 4 — UI atoms and layout

```text
GOAL
- Implement Button, Input, Label, Dialog, Form helpers.
- Render a two-card layout on the home page.

TASKS
1) Create components/ui/{button.tsx,input.tsx,label.tsx,dialog.tsx,form.tsx} as described in the spec.
2) Update src/app/page.tsx to show two sections ("Assistant", "Sample Form (coming soon)").
3) Keep layout clean and responsive.

TESTS
- Component tests: Button renders with default and ghost variant.
- Input accepts value and onChange.
- FormField shows error text when provided an error.

DELIVERABLES
- Commit: "feat(ui): atoms (button/input/label/dialog/form) and two-card home"
```

## Prompt 5 — Assistant UI (client)

```text
GOAL
- Add Assistant panel using @assistant-ui (runtime + Thread + Markdown).

TASKS
1) Install: pnpm add @assistant-ui/react @assistant-ui/react-ai-sdk @assistant-ui/react-markdown ai remark-gfm
2) Create components/assistant/Assistant.tsx with AssistantRuntimeProvider, useChatRuntime({ api: "/api/chat" }), Thread, ReactMarkdown(remarkGfm).
3) Dynamically import Assistant in page.tsx (ssr:false) and render inside left card.

TESTS
- Component test: Assistant renders heading "Assistant" and Thread placeholder.
- No network calls during render (mock useChatRuntime).

DELIVERABLES
- Commit: "feat(assistant): wire Assistant UI with runtime stub"
```

## Prompt 6 — `/api/chat` proxy (Option A to `/vanna/analysis`)

```text
GOAL
- Implement API route that forwards JSON to BACKEND_URL/vanna/analysis.

TASKS
1) Create src/app/api/chat/route.ts:
   - Read JSON body from request.
   - POST to `${process.env.BACKEND_URL}/vanna/analysis` with Content-Type: application/json.
   - Return Response with passthrough body and content-type; set Cache-Control: no-store.
   - Add try/catch; map network errors to 502 JSON { error }.
2) Add .env.local with BACKEND_URL=http://localhost:8001.
3) Add a tiny server-side Zod schema for request shape to defensively validate (optional but preferred).

TESTS
- Unit test route handler with mocked fetch:
  a) 200 returns body passthrough.
  b) 500 maps to same status with body.
  c) Network error -> 502 JSON { error: "…" }.
- Ensure headers include no-store.

DELIVERABLES
- Commit: "feat(api): chat proxy to /vanna/analysis with error mapping"
```

## Prompt 7 — Assistant error states + streaming tolerance

```text
GOAL
- Show user-friendly messages when backend errors or times out.
- Tolerate streaming or single JSON.

TASKS
1) In Assistant.tsx, add minimal UI for "Connecting…", "Error", "Try again".
2) In /api/chat, add AbortController with 25s timeout; if aborted, return 504 JSON { error }.
3) Ensure Response streams are forwarded unmodified when available; otherwise return JSON.

TESTS
- Mock timeout path -> 504; Assistant shows "Request timed out".
- Mock non-200 -> Assistant shows "Something went wrong".

DELIVERABLES
- Commit: "feat(assistant): error & timeout states; streaming tolerant proxy"
```

## Prompt 8 — RHF + Zod form

```text
GOAL
- Implement SampleForm with Zod email schema and inline errors.

TASKS
1) Install: pnpm add react-hook-form @hookform/resolvers zod
2) Create components/forms/SampleForm.tsx using Schema.email -> zodResolver.
3) Render form in right card; console.log on submit.

TESTS
- Component test: invalid email shows error; valid email hides error and calls onSubmit.
- Schema unit tests: rejects "foo", accepts "a@b.com".

DELIVERABLES
- Commit: "feat(form): RHF + Zod sample with validation"
```

## Prompt 9 — Vitest + RTL setup

```text
GOAL
- Add Vitest + @testing-library/react setup with jsdom and happy-dom fallback.

TASKS
1) Install: pnpm add -D vitest @testing-library/react @testing-library/jest-dom @types/testing-library__jest-dom jsdom
2) Create vitest.config.ts for ts/tsx + jsdom.
3) Create tests/setup.ts to extend expect with jest-dom; configure testURL.
4) Update package.json "test": "vitest --run", "test:watch": "vitest".

TESTS
- Ensure existing tests run green.

DELIVERABLES
- Commit: "chore(test): vitest + RTL config and setup"
```

## Prompt 10 — Playwright e2e (mock backend)

```text
GOAL
- Add Playwright e2e to validate Assistant and Form UX with mocked network.

TASKS
1) Install: pnpm dlx playwright install --with-deps
2) Add a test that:
   - Mocks POST /api/chat to return a small JSON chunk.
   - Visits "/", types a message, asserts response node appears.
   - Submits form with invalid email (sees error), then valid email (no error).
3) Add scripts: "test:e2e": "playwright test".

DELIVERABLES
- Commit: "test(e2e): Playwright coverage for assistant and form"
```

## Prompt 11 — CI workflow

```text
GOAL
- GitHub Actions: node 20 + pnpm cache + typecheck + unit + e2e (headed=false).

TASKS
1) .github/workflows/frontend.yml:
   - checkout
   - setup node 20
   - setup pnpm
   - install
   - run typecheck, test, test:e2e, build
2) Cache pnpm store.

DELIVERABLES
- Commit: "ci(frontend): add GH Actions for typecheck/tests/build"
```

## Prompt 12 — Hardening + docs

```text
GOAL
- Timeouts and docs.

TASKS
1) Confirm /api/chat uses AbortController(25_000ms).
2) Map common errors to meaningful UI strings.
3) Add README in /frontend: setup, envs, scripts, testing.
4) Add .env.local.example with BACKEND_URL placeholder.

DELIVERABLES
- Commit: "docs(frontend): README and env example; finalize proxy timeout handling"
- Verify: fresh clone -> follow README -> green build/tests.
```

---

## Final wiring checklist

* `/frontend` runs with `pnpm dev`.
* `/api/chat` forwards to `http://localhost:8001/vanna/analysis`.
* Assistant renders; errors handled; form validates.
* Unit + e2e tests pass locally and in CI.
* README and env example are accurate.

If you want, I can also add a follow-up set of prompts to introduce a **SQL Runner** page (POST `{ sql, trace }` through the same proxy) so you can exercise the Vanna endpoint interactively.
