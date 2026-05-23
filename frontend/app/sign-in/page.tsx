"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { TopNav } from "@/components/TopNav";
import { AuthCard } from "@/components/AuthCard";
import { FormField } from "@/components/FormField";
import { PrimaryButton } from "@/components/PrimaryButton";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function SignInPage() {
  const router = useRouter();
  const { setTokensAndLoad } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const pair = await api.signin(email, password);
      await setTokensAndLoad(pair);
      router.push("/profile");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <TopNav />
      <AuthCard>
        <header className="mb-12 text-center md:text-left">
          <h1 className="font-display mb-4 text-[32px] leading-[40px] md:text-[48px] md:leading-[56px] font-semibold text-primary">
            Welcome Back
          </h1>
          <p className="text-base text-secondary opacity-70">
            Enter your credentials to access your digital workspace.
          </p>
        </header>

        <form onSubmit={onSubmit} className="space-y-10">
          <FormField
            id="email"
            label="Email Address"
            type="email"
            value={email}
            onChange={setEmail}
            placeholder="name@example.com"
            autoComplete="email"
            required
          />
          <FormField
            id="password"
            label="Password"
            type="password"
            value={password}
            onChange={setPassword}
            placeholder="••••••••"
            autoComplete="current-password"
            required
            rightSlot={
              <Link
                href="/forgot-password"
                className="font-label text-primary underline-offset-4 hover:underline"
              >
                Forgot Password?
              </Link>
            }
          />

          {error && (
            <p className="text-sm text-error" role="alert">
              {error}
            </p>
          )}

          <div className="pt-4">
            <PrimaryButton type="submit" disabled={loading}>
              {loading ? "Signing in…" : "Sign In"}
            </PrimaryButton>
          </div>
        </form>

        <div className="mt-8">
          <a
            href={api.googleLoginUrl()}
            className="font-label flex w-full items-center justify-center rounded-full border border-outline-variant py-5 uppercase tracking-[0.2em] text-primary transition-colors hover:bg-surface-container-low"
          >
            Continue with Google
          </a>
        </div>

        <footer className="mt-12 border-t border-surface-container pt-8 text-center">
          <p className="text-base text-secondary">
            New to MINDY?
            <Link href="/sign-up" className="ml-2 font-bold text-primary underline-offset-8 hover:underline">
              Sign Up
            </Link>
          </p>
        </footer>
      </AuthCard>
    </>
  );
}
