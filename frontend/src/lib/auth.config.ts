import type { NextAuthOptions } from "next-auth";
import Credentials from "next-auth/providers/credentials";

type BackendUser = {
  id: number;
  email: string;
  business_id: number;
  created_at?: string;
};

type LoginResponse = {
  user: BackendUser;
  access_token: string;
  token_type: "bearer";
};

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8001";

export default {
  session: { strategy: "jwt" },
  providers: [
    Credentials({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;

        const resp = await fetch(`${BACKEND_URL}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: credentials.email, password: credentials.password }),
        });

        if (!resp.ok) return null;

        const data = (await resp.json()) as LoginResponse;
        return {
          ...data.user,
          accessToken: data.access_token,
          tokenType: data.token_type,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.user = {
          id: (user as any).id,
          email: (user as any).email,
          business_id: (user as any).business_id,
        };
        token.accessToken = (user as any).accessToken;
        token.tokenType = (user as any).tokenType;
      }
      return token;
    },
    async session({ session, token }) {
      if (token?.user) {
        (session as any).user = token.user;
        (session as any).accessToken = token.accessToken;
        (session as any).tokenType = token.tokenType;
      }
      return session;
    },
  },
  pages: { signIn: "/auth/sign-in" },
} satisfies NextAuthOptions;