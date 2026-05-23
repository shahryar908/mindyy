"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";

export default function ProfilePage() {
  const router = useRouter();
  const { user, logout } = useAuth();

  if (!user) {
    // (app)/layout.tsx already redirects unauthenticated users; this is a render-safety guard.
    return null;
  }

  const onSignOut = async () => {
    try {
      await logout();
      toast.success("Signed out");
    } catch {
      /* logout endpoint is best-effort */
    }
    router.push("/sign-in");
  };

  return (
    <main className="mx-auto w-full max-w-[1000px] px-margin-mobile pb-12 pt-6 md:px-margin-desktop">
      <header className="mb-10">
        <p className="font-label text-secondary">Your account</p>
        <h1 className="font-display text-[32px] leading-[40px] font-semibold tracking-tighter text-primary md:text-[48px] md:leading-[56px]">
          Settings
        </h1>
      </header>

      <section className="card-elevation rounded-[24px] bg-surface-container-lowest p-8 md:p-10">
        <div className="grid gap-8 md:grid-cols-2">
          <Field label="Email" value={user.email} />
          <Field label="Status" value={user.is_verified ? "Verified" : "Unverified"} />
          <div className="md:col-span-2">
            <Field label="User ID" value={user.id} mono />
          </div>
        </div>

        <div className="mt-10 border-t border-surface-container pt-6">
          <button
            type="button"
            onClick={() => void onSignOut()}
            className="font-label text-error underline-offset-8 hover:underline"
          >
            Sign out
          </button>
        </div>
      </section>
    </main>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="font-label mb-2 text-secondary">{label}</p>
      <p className={`text-base text-primary ${mono ? "break-all font-mono text-sm" : ""}`}>
        {value}
      </p>
    </div>
  );
}
