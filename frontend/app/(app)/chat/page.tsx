"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, tokenStore } from "@/lib/api";
import { parseSseStream } from "@/lib/sse";
import type { ChatCard } from "@/lib/types";

type ChatTurn = {
  id: string;
  query: string;
  cards: ChatCard[];
  narrative: string;
  streaming: boolean;
  error?: string;
};

const SUGGESTIONS = [
  "highlights of last month",
  "photos at the beach",
  "show me photos with food",
];

export default function ChatPage() {
  const [query, setQuery] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auto-scroll to bottom as content arrives.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  // Clean up on unmount.
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const submit = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || streaming) return;

    const turnId = Math.random().toString(36).slice(2);
    const newTurn: ChatTurn = {
      id: turnId,
      query: trimmed,
      cards: [],
      narrative: "",
      streaming: true,
    };
    setTurns((prev) => [...prev, newTurn]);
    setQuery("");
    setStreaming(true);

    const updateTurn = (patch: Partial<ChatTurn>) => {
      setTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, ...patch } : t)));
    };

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const token = tokenStore.getAccess();
      const res = await fetch(api.chatStreamUrl(), {
        method: "POST",
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ query: trimmed }),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      if (!res.body) {
        throw new Error("Empty response body");
      }

      const reader = res.body.getReader();
      let narrative = "";
      let cards: ChatCard[] = [];

      for await (const frame of parseSseStream(reader)) {
        if (frame.event === "cards") {
          try {
            cards = JSON.parse(frame.data) as ChatCard[];
            updateTurn({ cards });
          } catch {
            // ignore malformed frame
          }
        } else if (frame.event === "token") {
          narrative += frame.data;
          updateTurn({ narrative });
        } else if (frame.event === "done") {
          break;
        }
      }

      updateTurn({ streaming: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Connection failed";
      updateTurn({ streaming: false, error: message });
      toast.error(message);
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void submit(query);
  };

  return (
    <main className="mx-auto flex h-[calc(100vh-64px)] w-full max-w-[900px] flex-col px-margin-mobile pb-6 pt-2 md:px-margin-desktop">
      <header className="mb-4 shrink-0">
        <p className="font-label text-secondary">Ask your library</p>
        <h1 className="font-display text-[28px] leading-[36px] font-semibold tracking-tighter text-primary md:text-[36px] md:leading-[44px]">
          Chat
        </h1>
      </header>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto pr-2"
      >
        {turns.length === 0 ? (
          <EmptyState onPick={(q) => void submit(q)} />
        ) : (
          <ul className="space-y-12">
            {turns.map((t) => (
              <li key={t.id}>
                <p className="font-label mb-3 text-secondary">You asked</p>
                <p className="mb-6 text-lg text-primary">{t.query}</p>

                {t.cards.length > 0 && (
                  <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
                    {t.cards.map((c) => (
                      <Link
                        key={c.id}
                        href={`/photos/${c.id}`}
                        className="card-elevation group relative block aspect-square overflow-hidden rounded-[16px] bg-surface-container-low"
                      >
                        {c.thumbnail_url ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={c.thumbnail_url}
                            alt={c.caption}
                            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                            loading="lazy"
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center">
                            <p className="font-label text-secondary">No preview</p>
                          </div>
                        )}
                      </Link>
                    ))}
                  </div>
                )}

                <div className="card-elevation rounded-[16px] bg-surface-container-lowest p-5">
                  <p className="whitespace-pre-wrap text-base text-primary">
                    {t.narrative || (t.streaming ? "…" : "")}
                    {t.streaming && <span className="ml-1 animate-pulse">▍</span>}
                  </p>
                  {t.error && (
                    <p className="mt-2 text-sm text-error">{t.error}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <form onSubmit={onSubmit} className="mt-6 shrink-0">
        <div className="card-elevation flex items-center gap-3 rounded-full bg-surface-container-lowest px-5 py-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={streaming}
            placeholder="Ask about your photos…"
            maxLength={500}
            className="flex-1 bg-transparent text-base text-primary outline-none placeholder:text-outline-variant disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={streaming || !query.trim()}
            className="font-label rounded-full bg-primary px-5 py-2 uppercase tracking-[0.2em] text-on-primary transition-colors hover:bg-on-primary-fixed-variant disabled:cursor-not-allowed disabled:opacity-50"
          >
            {streaming ? "…" : "Ask"}
          </button>
        </div>
      </form>
    </main>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="card-elevation mx-auto mt-12 max-w-lg rounded-[24px] bg-surface-container-lowest p-10 text-center">
      <h2 className="font-display mb-3 text-[24px] leading-[32px] text-primary">
        Ask your library
      </h2>
      <p className="mb-8 text-secondary">
        Get a narrative answer with moment cards from your photos. Try one of these:
      </p>
      <div className="flex flex-col gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onPick(s)}
            className="font-label rounded-full border border-outline-variant px-4 py-3 text-left text-secondary transition-colors hover:bg-surface-container-low hover:text-primary"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
