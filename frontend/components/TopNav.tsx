"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export function TopNav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const isActive = (href: string) => pathname?.startsWith(href);

  return (
    <nav className="fixed top-0 z-50 w-full border-none bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-[1280px] items-center justify-between px-5 py-8 md:px-margin-desktop md:py-10">
        <Link
          href="/"
          className="font-display text-[32px] font-medium leading-[40px] tracking-tighter text-primary"
        >
          MINDY
        </Link>
        <div className="flex items-center gap-8">
          <Link
            href="/support"
            className="font-label text-secondary transition-colors duration-300 hover:text-primary"
          >
            Support
          </Link>
          {user ? (
            <>
              <Link
                href="/profile"
                className={`font-label transition-colors duration-300 hover:text-primary ${
                  isActive("/profile") ? "border-b border-primary pb-1 text-primary" : "text-secondary"
                }`}
              >
                Profile
              </Link>
              <button
                onClick={() => void logout()}
                className="font-label text-secondary transition-colors duration-300 hover:text-primary"
              >
                Sign Out
              </button>
            </>
          ) : (
            <Link
              href="/sign-in"
              className={`font-label transition-colors duration-300 hover:text-primary ${
                isActive("/sign-in") ? "border-b border-primary pb-1 text-primary" : "text-secondary"
              }`}
            >
              Sign In
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
}
