"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { FaceCluster } from "@/lib/types";

export default function PeoplePage() {
  const [clusters, setClusters] = useState<FaceCluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listPeople();
      setClusters(sortClusters(res));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't load people.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const onRename = async (id: string, label: string) => {
    const trimmed = label.trim();
    if (!trimmed) {
      setEditingId(null);
      return;
    }
    const prev = clusters;
    setClusters((curr) =>
      sortClusters(curr.map((c) => (c.id === id ? { ...c, label: trimmed } : c))),
    );
    setEditingId(null);
    try {
      await api.labelPerson(id, trimmed);
      toast.success("Renamed");
    } catch (err) {
      setClusters(prev);
      toast.error(err instanceof ApiError ? err.detail : "Couldn't rename");
    }
  };

  return (
    <main className="mx-auto w-full max-w-[1280px] px-margin-mobile pb-12 pt-6 md:px-margin-desktop">
      <header className="mb-8">
        <p className="font-label text-secondary">Faces detected in your photos</p>
        <h1 className="font-display text-[32px] leading-[40px] font-semibold tracking-tighter text-primary md:text-[48px] md:leading-[56px]">
          People
        </h1>
      </header>

      {loading ? (
        <SkeletonGrid />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : clusters.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {clusters.map((c) => (
            <ClusterTile
              key={c.id}
              cluster={c}
              editing={editingId === c.id}
              onStartEdit={() => setEditingId(c.id)}
              onCancelEdit={() => setEditingId(null)}
              onRename={(label) => onRename(c.id, label)}
            />
          ))}
        </div>
      )}
    </main>
  );
}

function ClusterTile({
  cluster,
  editing,
  onStartEdit,
  onCancelEdit,
  onRename,
}: {
  cluster: FaceCluster;
  editing: boolean;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onRename: (label: string) => void;
}) {
  const [value, setValue] = useState(cluster.label ?? "");

  useEffect(() => {
    setValue(cluster.label ?? "");
  }, [cluster.label, editing]);

  return (
    <div className="card-elevation overflow-hidden rounded-[16px] bg-surface-container-lowest">
      <Link
        href={`/people/${cluster.id}`}
        className="group relative block aspect-square overflow-hidden bg-surface-container-low"
      >
        {cluster.sample_thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={cluster.sample_thumbnail_url}
            alt={cluster.label ?? "Person"}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <p className="font-label text-secondary">No preview</p>
          </div>
        )}
      </Link>

      <div className="p-4">
        {editing ? (
          <input
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onBlur={() => onRename(value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onRename(value);
              if (e.key === "Escape") onCancelEdit();
            }}
            maxLength={64}
            placeholder="Add a name"
            className="input-underlined w-full py-1 text-base text-primary placeholder:text-outline-variant"
          />
        ) : (
          <button
            type="button"
            onClick={onStartEdit}
            className="w-full text-left"
          >
            <p className="truncate text-base text-primary">
              {cluster.label ?? <span className="italic text-secondary">Add a name</span>}
            </p>
          </button>
        )}
        <p className="font-label mt-1 text-secondary">
          {cluster.face_count} {cluster.face_count === 1 ? "photo" : "photos"}
        </p>
      </div>
    </div>
  );
}

function sortClusters(list: FaceCluster[]): FaceCluster[] {
  return [...list].sort((a, b) => {
    // Unnamed first by face_count desc, then named alphabetically.
    if (!a.label && b.label) return -1;
    if (a.label && !b.label) return 1;
    if (!a.label && !b.label) return b.face_count - a.face_count;
    return (a.label ?? "").localeCompare(b.label ?? "");
  });
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
      {Array.from({ length: 10 }).map((_, i) => (
        <div
          key={i}
          className="aspect-[3/4] animate-pulse rounded-[16px] bg-surface-container-low"
        />
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="card-elevation mx-auto mt-12 max-w-md rounded-[24px] bg-surface-container-lowest p-12 text-center">
      <h2 className="font-display mb-2 text-[24px] leading-[32px] text-primary">
        No people yet
      </h2>
      <p className="text-secondary">
        Upload more photos with faces and check back. People appear here once we&apos;ve
        recognised them.
      </p>
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
