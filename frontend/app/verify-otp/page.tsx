"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { TopNav } from "@/components/TopNav";
import { AuthCard } from "@/components/AuthCard";
import { PrimaryButton } from "@/components/PrimaryButton";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

function VerifyOtpInner() {
  const router = useRouter();
  const params = useSearchParams();
  const userId = params.get("user_id") ?? "";
  const email = params.get("email") ?? "";
  const { setTokensAndLoad } = useAuth();

  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resent, setResent] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!userId) {
      setError("Missing user_id. Start from sign-up.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const pair = await api.verifyOtp(userId, code);
      await setTokensAndLoad(pair);
      router.push("/profile");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function onResend() {
    if (!email) return;
    setResending(true);
    setError(null);
    try {
      await api.resendOtp(email);
      setResent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not resend");
    } finally {
      setResending(false);
    }
  }

  return (
    <>
      <TopNav />
      <AuthCard>
        <header className="mb-5 text-center md:text-left">
          <h1 className="font-display mb-1 text-[26px] leading-[32px] md:text-[32px] md:leading-[38px] font-semibold text-primary">
            Verify your email
          </h1>
          <p className="text-sm text-secondary opacity-70">
            We sent a 6-digit code to <span className="text-primary">{email || "your inbox"}</span>.
          </p>
        </header>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="flex flex-col gap-2">
            <label htmlFor="code" className="font-label text-secondary">
              Verification Code
            </label>
            <input
              id="code"
              name="code"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              placeholder="000000"
              required
              className="input-underlined py-3 text-center text-2xl tracking-[0.6em] text-primary placeholder:text-outline-variant"
            />
          </div>

          {error && (
            <p className="text-sm text-error" role="alert">
              {error}
            </p>
          )}
          {resent && !error && (
            <p className="text-sm text-secondary">If eligible, a new code has been sent.</p>
          )}

          <div className="pt-1">
            <PrimaryButton type="submit" disabled={loading || code.length !== 6}>
              {loading ? "Verifying…" : "Verify"}
            </PrimaryButton>
          </div>
        </form>

        <footer className="mt-4 border-t border-surface-container pt-4 text-center">
          <button
            type="button"
            onClick={onResend}
            disabled={resending || !email}
            className="font-label text-secondary underline-offset-8 hover:text-primary hover:underline disabled:opacity-50"
          >
            {resending ? "Sending…" : "Resend code"}
          </button>
        </footer>
      </AuthCard>
    </>
  );
}

export default function VerifyOtpPage() {
  return (
    <Suspense fallback={null}>
      <VerifyOtpInner />
    </Suspense>
  );
}
