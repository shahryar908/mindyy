"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { TopNav } from "@/components/TopNav";
import { useAuth } from "@/lib/auth-context";

export default function ProfilePage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();

  useEffect(() => {
    if (!loading && !user) router.replace("/sign-in");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <>
        <TopNav />
        <main className="soft-glow-background flex min-h-screen items-center justify-center pt-24">
          <p className="font-label text-secondary">Loading…</p>
        </main>
      </>
    );
  }

  return (
    <>
      <TopNav />
      <main className="soft-glow-background relative min-h-screen w-full pt-24 pb-12">
        <div className="mx-auto w-full max-w-[1280px] px-margin-mobile md:px-margin-desktop">
          <header className="mb-12 mt-12">
            <p className="font-label mb-4 text-secondary">Your account</p>
            <h1 className="font-display text-[48px] leading-[56px] md:text-[80px] md:leading-[88px] font-semibold tracking-tighter text-primary">
              {user.email.split("@")[0]}
            </h1>
          </header>

          <section className="card-elevation rounded-[24px] bg-surface-container-lowest p-8 md:p-12">
            <div className="grid gap-8 md:grid-cols-2">
              <Field label="Email" value={user.email} />
              <Field label="Status" value={user.is_verified ? "Verified" : "Unverified"} />
              <Field label="User ID" value={user.id} mono />
            </div>

            <div className="mt-12 border-t border-surface-container pt-8">
              <button
                type="button"
                onClick={() => void logout().then(() => router.push("/sign-in"))}
                className="font-label text-secondary underline-offset-8 hover:text-primary hover:underline"
              >
                Sign Out
              </button>
            </div>
          </section>
        </div>
      </main>
    </>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="font-label mb-2 text-secondary">{label}</p>
      <p className={`text-base text-primary ${mono ? "font-mono break-all" : ""}`}>{value}</p>
    </div>
  );
}
