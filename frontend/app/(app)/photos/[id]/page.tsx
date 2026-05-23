"use client";

import { useRouter, useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { Photo } from "@/lib/types";

export default function PhotoDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params?.id;

  const [photo, setPhoto] = useState<Photo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  useEffect(() => {
    if (!id) return;
    const load = async () => {
      setLoading(true);
      try {
        const p = await api.getPhoto(id);
        setPhoto(p);
      } catch (err) {
        if (err instanceof ApiError) {
          setError({ status: err.status, message: err.detail });
        } else {
          setError({ status: 0, message: "Couldn't load this photo." });
        }
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [id]);

  // Escape closes
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") goBack();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const goBack = () => {
    if (window.history.length > 1) {
      router.back();
    } else {
      router.push("/timeline");
    }
  };

  const onDelete = async () => {
    if (!photo) return;
    setDeleting(true);
    try {
      await api.deletePhoto(photo.id);
      toast.success("Photo deleted");
      router.push("/timeline");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "Couldn't delete photo");
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="font-label text-secondary">Loading…</p>
      </main>
    );
  }

  if (error) {
    const is404 = error.status === 404;
    return (
      <main className="mx-auto max-w-md px-margin-mobile pt-12 md:px-margin-desktop">
        <div className="card-elevation rounded-[24px] bg-surface-container-lowest p-12 text-center">
          <h2 className="font-display mb-4 text-[28px] leading-[36px] text-primary">
            {is404 ? "Photo not found" : "Couldn't load photo"}
          </h2>
          <p className="mb-8 text-secondary">
            {is404 ? "It may have been deleted, or you don't have access." : error.message}
          </p>
          <button
            type="button"
            onClick={() => router.push("/timeline")}
            className="font-label rounded-full bg-primary px-6 py-3 uppercase tracking-[0.2em] text-on-primary hover:bg-on-primary-fixed-variant"
          >
            Back to timeline
          </button>
        </div>
      </main>
    );
  }

  if (!photo) return null;

  const isReady = photo.status === "ready";
  const isFailed = photo.status === "failed";

  return (
    <main className="mx-auto w-full max-w-[1280px] px-margin-mobile pb-12 pt-2 md:px-margin-desktop">
      <button
        type="button"
        onClick={goBack}
        className="font-label mb-6 text-secondary hover:text-primary"
      >
        ← Back
      </button>

      <div className="grid gap-8 md:grid-cols-[1fr,360px]">
        <div className="card-elevation overflow-hidden rounded-[24px] bg-surface-container-lowest">
          {photo.source_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={photo.source_url}
              alt={photo.caption ?? "Photo"}
              className="h-auto w-full"
            />
          ) : (
            <div className="flex aspect-square items-center justify-center bg-surface-container">
              <p className="font-label text-secondary">Still processing…</p>
            </div>
          )}
        </div>

        <aside className="card-elevation rounded-[24px] bg-surface-container-lowest p-8">
          {!isReady && (
            <div className="mb-6 rounded-[12px] bg-surface-container-low p-4">
              <p className="font-label mb-1 text-secondary">Status</p>
              <p className="text-base text-primary capitalize">{photo.status}</p>
              {isFailed && (
                <p className="mt-2 text-sm text-secondary">
                  We couldn&apos;t extract details for this photo.
                </p>
              )}
            </div>
          )}

          {isReady && photo.caption && (
            <Field label="Caption" value={photo.caption} />
          )}

          {photo.taken_at && (
            <Field label="Taken" value={formatDate(photo.taken_at)} />
          )}

          {photo.location && <Field label="Location" value={photo.location} />}

          {isReady && photo.scenes.length > 0 && (
            <Chips label="Scenes" values={photo.scenes} />
          )}

          {isReady && photo.objects.length > 0 && (
            <Chips label="Objects" values={photo.objects} />
          )}

          {isReady && photo.ocr_text && (
            <Field label="Text in image" value={photo.ocr_text} />
          )}

          <div className="mt-8 border-t border-surface-container pt-6">
            {confirmingDelete ? (
              <div className="space-y-3">
                <p className="text-sm text-secondary">Delete this photo permanently?</p>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={onDelete}
                    disabled={deleting}
                    className="font-label flex-1 rounded-full bg-error py-3 uppercase tracking-[0.2em] text-on-error hover:opacity-90 disabled:opacity-50"
                  >
                    {deleting ? "Deleting…" : "Confirm"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmingDelete(false)}
                    disabled={deleting}
                    className="font-label flex-1 rounded-full border border-outline-variant py-3 uppercase tracking-[0.2em] text-primary hover:bg-surface-container-low"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmingDelete(true)}
                className="font-label text-error hover:underline"
              >
                Delete photo
              </button>
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="mb-5">
      <p className="font-label mb-1 text-secondary">{label}</p>
      <p className="text-base text-primary">{value}</p>
    </div>
  );
}

function Chips({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="mb-5">
      <p className="font-label mb-2 text-secondary">{label}</p>
      <div className="flex flex-wrap gap-2">
        {values.map((v) => (
          <span
            key={v}
            className="font-label rounded-full bg-surface-container px-3 py-1 text-primary"
          >
            {v}
          </span>
        ))}
      </div>
    </div>
  );
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}
