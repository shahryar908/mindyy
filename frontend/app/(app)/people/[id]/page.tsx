"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { FaceCluster, Photo } from "@/lib/types";

const PAGE_SIZE = 50;

export default function ClusterDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params?.id;

  const [cluster, setCluster] = useState<FaceCluster | null>(null);
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [labelDraft, setLabelDraft] = useState("");
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const load = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [people, photoPage] = await Promise.all([
        api.listPeople(),
        api.listPhotos({ cluster_id: id, limit: PAGE_SIZE }),
      ]);
      const found = people.find((p) => p.id === id);
      if (!found) {
        setError("This person doesn't exist or you don't have access.");
        return;
      }
      setCluster(found);
      setLabelDraft(found.label ?? "");
      setPhotos(photoPage.items);
      setCursor(photoPage.next_cursor);
      setHasMore(photoPage.next_cursor !== null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't load this person.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (!sentinelRef.current || loading || !hasMore || !id) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loadingMore && cursor) {
          void loadMore();
        }
      },
      { rootMargin: "400px" },
    );
    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cursor, hasMore, loadingMore, loading, id]);

  const loadMore = async () => {
    if (!cursor || !id || loadingMore) return;
    setLoadingMore(true);
    try {
      const res = await api.listPhotos({ cluster_id: id, limit: PAGE_SIZE, cursor });
      setPhotos((prev) => [...prev, ...res.items]);
      setCursor(res.next_cursor);
      setHasMore(res.next_cursor !== null);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "Couldn't load more");
    } finally {
      setLoadingMore(false);
    }
  };

  const onSaveLabel = async () => {
    if (!cluster) return;
    const trimmed = labelDraft.trim();
    if (!trimmed || trimmed === cluster.label) {
      setEditing(false);
      return;
    }
    const prev = cluster;
    setCluster({ ...cluster, label: trimmed });
    setEditing(false);
    try {
      await api.labelPerson(cluster.id, trimmed);
      toast.success("Renamed");
    } catch (err) {
      setCluster(prev);
      toast.error(err instanceof ApiError ? err.detail : "Couldn't rename");
    }
  };

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="font-label text-secondary">Loading…</p>
      </main>
    );
  }

  if (error || !cluster) {
    return (
      <main className="mx-auto max-w-md px-margin-mobile pt-12 md:px-margin-desktop">
        <div className="card-elevation rounded-[24px] bg-surface-container-lowest p-12 text-center">
          <h2 className="font-display mb-4 text-[28px] leading-[36px] text-primary">
            Person not found
          </h2>
          <p className="mb-8 text-secondary">{error ?? "Try again from the people page."}</p>
          <button
            type="button"
            onClick={() => router.push("/people")}
            className="font-label rounded-full bg-primary px-6 py-3 uppercase tracking-[0.2em] text-on-primary hover:bg-on-primary-fixed-variant"
          >
            Back to people
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-[1280px] px-margin-mobile pb-12 pt-2 md:px-margin-desktop">
      <Link
        href="/people"
        className="font-label mb-6 inline-block text-secondary hover:text-primary"
      >
        ← All people
      </Link>

      <header className="mb-10">
        <p className="font-label text-secondary">
          {cluster.face_count} {cluster.face_count === 1 ? "photo" : "photos"}
        </p>
        {editing ? (
          <input
            autoFocus
            value={labelDraft}
            onChange={(e) => setLabelDraft(e.target.value)}
            onBlur={onSaveLabel}
            onKeyDown={(e) => {
              if (e.key === "Enter") void onSaveLabel();
              if (e.key === "Escape") setEditing(false);
            }}
            maxLength={64}
            placeholder="Add a name"
            className="input-underlined font-display w-full text-[32px] leading-[40px] font-semibold tracking-tighter text-primary placeholder:text-outline-variant md:text-[48px] md:leading-[56px]"
          />
        ) : (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="font-display text-left text-[32px] leading-[40px] font-semibold tracking-tighter text-primary hover:opacity-80 md:text-[48px] md:leading-[56px]"
          >
            {cluster.label ?? <span className="italic text-secondary">Add a name</span>}
          </button>
        )}
      </header>

      {photos.length === 0 ? (
        <div className="card-elevation mx-auto mt-12 max-w-md rounded-[24px] bg-surface-container-lowest p-12 text-center">
          <p className="text-secondary">No photos to show yet.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {photos.map((p) => (
              <Link
                key={p.id}
                href={`/photos/${p.id}`}
                className="card-elevation group relative block aspect-square overflow-hidden rounded-[16px] bg-surface-container-low"
              >
                {p.thumbnail_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={p.thumbnail_url}
                    alt={p.caption ?? "Photo"}
                    className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                    loading="lazy"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center">
                    <p className="font-label text-secondary">{p.status}</p>
                  </div>
                )}
              </Link>
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
