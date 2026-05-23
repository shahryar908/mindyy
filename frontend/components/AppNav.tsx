"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useUploadQueue } from "@/lib/upload-queue";

const LINKS: { href: string; label: string }[] = [
  { href: "/timeline", label: "Timeline" },
  { href: "/upload", label: "Upload" },
  { href: "/people", label: "People" },
  { href: "/chat", label: "Chat" },
];

export function AppNav() {
  const pathname = usePathname();
  const { logout } = useAuth();
  const { inFlightCount } = useUploadQueue();

  const isActive = (href: string) => pathname === href || pathname?.startsWith(href + "/");

  return (
    <nav className="fixed top-0 z-50 w-full border-none bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-[1280px] items-center justify-between px-5 py-3 md:px-margin-desktop md:py-3">
        <Link
          href="/timeline"
          className="font-display text-[22px] font-medium leading-[28px] tracking-tighter text-primary"
        >
          MINDY
        </Link>
        <div className="flex items-center gap-6 md:gap-8">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`font-label transition-colors duration-300 hover:text-primary ${
                isActive(link.href)
                  ? "border-b border-primary pb-1 text-primary"
                  : "text-secondary"
              }`}
            >
              {link.label}
              {link.href === "/upload" && inFlightCount > 0 && (
                <span className="ml-2 rounded-full bg-primary px-2 py-0.5 text-[10px] leading-none text-on-primary">
                  {inFlightCount}
                </span>
              )}
            </Link>
          ))}
          <Link
            href="/profile"
            className={`font-label transition-colors duration-300 hover:text-primary ${
              isActive("/profile") ? "border-b border-primary pb-1 text-primary" : "text-secondary"
            }`}
          >
            Settings
          </Link>
          <button
            onClick={() => void logout()}
            className="font-label text-secondary transition-colors duration-300 hover:text-primary"
          >
            Sign Out
          </button>
        </div>
      </div>
    </nav>
  );
}
