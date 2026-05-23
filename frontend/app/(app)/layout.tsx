"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Toaster } from "sonner";
import { AppNav } from "@/components/AppNav";
import { useAuth } from "@/lib/auth-context";
import { UploadQueueProvider } from "@/lib/upload-queue";

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      router.replace(`/sign-in?next=${next}`);
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <main className="soft-glow-background flex min-h-screen items-center justify-center">
        <p className="font-label text-secondary">Loading…</p>
      </main>
    );
  }

  return (
    <UploadQueueProvider>
      <AppNav />
      <div className="pt-16">{children}</div>
      <Toaster position="bottom-right" />
    </UploadQueueProvider>
  );
}
