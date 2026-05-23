"use client";

import Link from "next/link";
import { useState } from "react";
import { TopNav } from "@/components/TopNav";
import { AuthCard } from "@/components/AuthCard";
import { FormField } from "@/components/FormField";
import { PrimaryButton } from "@/components/PrimaryButton";
import { api, ApiError } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.forgotPassword(email);
      setSent(true);
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
            Reset your password
          </h1>
          <p className="text-base text-secondary opacity-70">
            Enter your email and we&apos;ll send a reset link.
          </p>
        </header>

        {sent ? (
          <p className="text-base text-secondary">
            If an account exists for <span className="text-primary">{email}</span>, a reset link is on
            its way.
          </p>
        ) : (
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
            {error && (
              <p className="text-sm text-error" role="alert">
                {error}
              </p>
            )}
            <div className="pt-4">
              <PrimaryButton type="submit" disabled={loading}>
                {loading ? "Sending…" : "Send Reset Link"}
              </PrimaryButton>
            </div>
          </form>
        )}

        <footer className="mt-12 border-t border-surface-container pt-8 text-center">
          <Link href="/sign-in" className="font-label text-secondary underline-offset-8 hover:text-primary hover:underline">
            Back to Sign In
          </Link>
        </footer>
      </AuthCard>
    </>
  );
}
