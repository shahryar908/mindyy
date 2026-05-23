"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";
import { TopNav } from "@/components/TopNav";
import { useAuth } from "@/lib/auth-context";

function CallbackInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { setTokensAndLoad } = useAuth();

  useEffect(() => {
    const access = params.get("access_token");
    const refresh = params.get("refresh_token");
    if (!access || !refresh) {
      router.replace("/sign-in?error=google_failed");
      return;
    }
    void setTokensAndLoad({ access_token: access, refresh_token: refresh }).then(() => {
      router.replace("/profile");
    });
  }, [params, router, setTokensAndLoad]);

  return (
    <>
      <TopNav />
      <main className="soft-glow-background flex min-h-screen items-center justify-center pt-24">
        <p className="font-label text-secondary">Finishing sign in…</p>
      </main>
    </>
  );
}

export default function GoogleCallbackPage() {
  return (
    <Suspense fallback={null}>
      <CallbackInner />
    </Suspense>
  );
}
