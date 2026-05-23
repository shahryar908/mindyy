"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { TopNav } from "@/components/TopNav";
import { AuthCard } from "@/components/AuthCard";
import { FormField } from "@/components/FormField";
import { PrimaryButton } from "@/components/PrimaryButton";
import { api, ApiError } from "@/lib/api";

function ResetInner() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) {
      setError("Reset token missing from URL.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await api.resetPassword(token, password);
      setDone(true);
      setTimeout(() => router.push("/sign-in"), 1500);
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
            Choose a new password
          </h1>
          <p className="text-base text-secondary opacity-70">
            Pick something memorable but strong.
          </p>
        </header>

        {done ? (
          <p className="text-base text-secondary">
            Password updated. Redirecting you to sign in…
          </p>
        ) : (
          <form onSubmit={onSubmit} className="space-y-10">
            <FormField
              id="new-password"
              label="New Password"
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
            <div className="pt-4">
              <PrimaryButton type="submit" disabled={loading}>
                {loading ? "Updating…" : "Update Password"}
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

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetInner />
    </Suspense>
  );
}
