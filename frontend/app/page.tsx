"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import Link from "next/link";
import { TopNav } from "@/components/TopNav";
import { useAuth } from "@/lib/auth-context";

export default function HomePage() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && user) {
      router.replace("/timeline");
    }
  }, [loading, user, router]);

  // While we figure out where to send them, show a minimal landing.
  if (loading) {
    return (
      <main className="soft-glow-background flex min-h-screen items-center justify-center">
        <p className="font-label text-secondary">Loading…</p>
      </main>
    );
  }

  if (user) {
    return null; // about to redirect
  }

  return (
    <>
      <TopNav />
      <main className="soft-glow-background relative flex min-h-screen w-full items-center justify-center overflow-hidden px-margin-mobile pt-24 pb-12 md:px-margin-desktop">
        <div className="mx-auto w-full max-w-[1280px] text-center">
          <p className="font-label mb-8 text-secondary">A digital workspace</p>
          <h1 className="font-display mb-12 text-[48px] leading-[56px] md:text-[80px] md:leading-[88px] font-semibold tracking-tighter text-primary">
            Think clearly.
            <br />
            Build quietly.
          </h1>
          <p className="mx-auto mb-16 max-w-xl text-lg leading-[30px] text-secondary opacity-70">
            MINDY is the calm, focused space for your most important work.
          </p>
          <div className="flex flex-col items-center justify-center gap-6 md:flex-row">
            <Link
              href="/sign-up"
              className="font-label rounded-full bg-primary px-12 py-5 uppercase tracking-[0.2em] text-on-primary transition-all hover:bg-on-primary-fixed-variant active:scale-[0.98]"
            >
              Get Started
            </Link>
            <Link
              href="/sign-in"
              className="font-label text-secondary underline-offset-8 hover:text-primary hover:underline"
            >
              Already a member? Sign In
            </Link>
          </div>
        </div>
      </main>
    </>
  );
}
