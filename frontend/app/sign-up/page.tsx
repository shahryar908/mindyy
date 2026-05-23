"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { TopNav } from "@/components/TopNav";
import { AuthCard } from "@/components/AuthCard";
import { FormField } from "@/components/FormField";
import { PrimaryButton } from "@/components/PrimaryButton";
import { api, ApiError } from "@/lib/api";

export default function SignUpPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.signup(email, password);
      const params = new URLSearchParams({ user_id: res.user_id, email: res.email });
      router.push(`/verify-otp?${params.toString()}`);
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
        <header className="mb-5 text-center md:text-left">
          <h1 className="font-display mb-1 text-[26px] leading-[32px] md:text-[32px] md:leading-[38px] font-semibold text-primary">
            Create your account
          </h1>
          <p className="text-sm text-secondary opacity-70">
            Sign up to get started.
          </p>
        </header>

        <form onSubmit={onSubmit} className="space-y-4">
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
            autoComplete="new-password"
            required
          />

          {error && (
            <p className="text-sm text-error" role="alert">
              {error}
            </p>
          )}

          <div className="pt-1">
            <PrimaryButton type="submit" disabled={loading}>
              {loading ? "Creating…" : "Sign Up"}
            </PrimaryButton>
          </div>
        </form>

        <div className="mt-3">
          <a
            href={api.googleLoginUrl()}
            className="font-label flex w-full items-center justify-center rounded-full border border-outline-variant py-3 uppercase tracking-[0.2em] text-primary transition-colors hover:bg-surface-container-low"
          >
            Continue with Google
          </a>
        </div>

        <footer className="mt-4 border-t border-surface-container pt-4 text-center">
          <p className="text-sm text-secondary">
            Already have an account?
            <Link href="/sign-in" className="ml-2 font-bold text-primary underline-offset-8 hover:underline">
              Sign In
            </Link>
          </p>
        </footer>
      </AuthCard>
    </>
  );
}
