"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Photo } from "@/lib/types";
import { useUploadQueue } from "@/lib/upload-queue";

const PAGE_SIZE = 50;

export default function TimelinePage() {
  const { entries } = useUploadQueue();
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const loadInitial = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listPhotos({ limit: PAGE_SIZE });
      setPhotos(res.items);
      setCursor(res.next_cursor);
      setHasMore(res.next_cursor !== null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't load your photos.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadInitial();
  }, []);

  // Re-fetch when an upload completes (so newly READY photos appear without manual refresh).
  const readyCount = entries.filter((e) => e.status === "ready").length;
  useEffect(() => {
    if (readyCount > 0) {
      void loadInitial();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readyCount]);

  // Infinite scroll
  useEffect(() => {
    if (!sentinelRef.current || loading || !hasMore) return;

    const observer = new IntersectionObserver(
      (intersections) => {
        if (intersections[0].isIntersecting && !loadingMore && cursor) {
          void loadMore();
        }
      },
      { rootMargin: "400px" },
    );
    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cursor, hasMore, loadingMore, loading]);

  const loadMore = async () => {
    if (!cursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const res = await api.listPhotos({ limit: PAGE_SIZE, cursor });
      setPhotos((prev) => [...prev, ...res.items]);
      setCursor(res.next_cursor);
      setHasMore(res.next_cursor !== null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't load more photos.");
    } finally {
      setLoadingMore(false);
    }
  };

  return (
    <main className="mx-auto w-full max-w-[1280px] px-margin-mobile pb-12 pt-6 md:px-margin-desktop">
      <header className="mb-8 flex items-end justify-between">
        <div>
          <p className="font-label text-secondary">Your library</p>
          <h1 className="font-display text-[32px] leading-[40px] font-semibold tracking-tighter text-primary md:text-[48px] md:leading-[56px]">
            Timeline
          </h1>
        </div>
        <Link
          href="/upload"
          className="font-label rounded-full bg-primary px-6 py-3 uppercase tracking-[0.2em] text-on-primary transition-all hover:bg-on-primary-fixed-variant active:scale-[0.98]"
        >
          Upload
        </Link>
      </header>

      {loading ? (
        <SkeletonGrid />
      ) : error ? (
        <ErrorState message={error} onRetry={loadInitial} />
      ) : photos.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {photos.map((p) => (
              <PhotoTile key={p.id} photo={p} />
            ))}
          </div>
          {hasMore && (
            <div ref={sentinelRef} className="mt-8 text-center">
              <p className="font-label text-secondary">{loadingMore ? "Loading…" : ""}</p>
            </div>
          )}
        </>
      )}
    </main>
  );
}

function PhotoTile({ photo }: { photo: Photo }) {
  const isReady = photo.status === "ready";
  return (
    <Link
      href={`/photos/${photo.id}`}
      className="card-elevation group relative block aspect-square overflow-hidden rounded-[16px] bg-surface-container-low"
    >
      {photo.thumbnail_url ? (
        // Signed URLs change per request — disable Next.js Image optimisation here.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={photo.thumbnail_url}
          alt={photo.caption ?? "Photo"}
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
          loading="lazy"
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center bg-surface-container">
          <p className="font-label text-secondary">{photo.status}</p>
        </div>
      )}
      {!isReady && (
        <div className="absolute right-2 top-2 rounded-full bg-background/80 px-2 py-1 backdrop-blur">
          <p className="font-label text-[10px] text-primary">{photo.status}</p>
        </div>
      )}
    </Link>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
      {Array.from({ length: 15 }).map((_, i) => (
        <div
          key={i}
          className="aspect-square animate-pulse rounded-[16px] bg-surface-container-low"
        />
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="card-elevation mx-auto mt-12 max-w-md rounded-[24px] bg-surface-container-lowest p-12 text-center">
      <h2 className="font-display mb-2 text-[24px] leading-[32px] text-primary">
        Nothing here yet
      </h2>
      <p className="mb-8 text-secondary">You haven&apos;t uploaded any photos yet.</p>
      <Link
        href="/upload"
        className="font-label inline-block rounded-full bg-primary px-8 py-4 uppercase tracking-[0.2em] text-on-primary hover:bg-on-primary-fixed-variant"
      >
        Upload your first
      </Link>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="card-elevation mx-auto mt-12 max-w-md rounded-[24px] bg-surface-container-lowest p-12 text-center">
      <p className="mb-6 text-error">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="font-label rounded-full border border-outline-variant px-6 py-3 uppercase tracking-[0.2em] text-primary hover:bg-surface-container-low"
      >
        Retry
      </button>
    </div>
  );
}
