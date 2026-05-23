"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { useUploadQueue, type UploadEntry } from "@/lib/upload-queue";

const ACCEPTED = ["image/jpeg", "image/png", "image/heic", "image/webp"];
const MAX_BYTES = 50 * 1024 * 1024;

export default function UploadPage() {
  const { entries, enqueue, clearFinished, retry } = useUploadQueue();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const onFiles = (files: FileList | null) => {
    if (!files) return;
    const accepted: File[] = [];
    const rejected: { name: string; reason: string }[] = [];

    for (const f of Array.from(files)) {
      if (!ACCEPTED.includes(f.type)) {
        rejected.push({ name: f.name, reason: "Unsupported format" });
        continue;
      }
      if (f.size > MAX_BYTES) {
        rejected.push({ name: f.name, reason: "Larger than 50 MB" });
        continue;
      }
      accepted.push(f);
    }

    if (accepted.length > 0) enqueue(accepted);
    rejected.forEach((r) => toast.error(`${r.name}: ${r.reason}`));
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    onFiles(e.dataTransfer.files);
  };

  return (
    <main className="mx-auto w-full max-w-[1000px] px-margin-mobile pb-12 pt-6 md:px-margin-desktop">
      <header className="mb-8">
        <p className="font-label text-secondary">Add to your library</p>
        <h1 className="font-display text-[32px] leading-[40px] font-semibold tracking-tighter text-primary md:text-[48px] md:leading-[56px]">
          Upload
        </h1>
      </header>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`card-elevation flex min-h-[260px] cursor-pointer flex-col items-center justify-center rounded-[24px] border-2 border-dashed transition-colors ${
          dragOver
            ? "border-primary bg-surface-container-low"
            : "border-outline-variant bg-surface-container-lowest"
        } p-12 text-center`}
      >
        <p className="font-display mb-2 text-[24px] leading-[32px] text-primary">
          Drop photos here
        </p>
        <p className="mb-6 text-secondary">or click to choose files</p>
        <p className="font-label text-[10px] text-secondary">
          JPEG · PNG · HEIC · WEBP — up to 50 MB each
        </p>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED.join(",")}
          onChange={(e) => onFiles(e.target.files)}
          className="hidden"
        />
      </div>

      {entries.length > 0 && (
        <section className="mt-12">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-display text-[20px] leading-[28px] text-primary">
              Queue ({entries.length})
            </h2>
            <button
              type="button"
              onClick={clearFinished}
              className="font-label text-secondary hover:text-primary"
            >
              Clear finished
            </button>
          </div>
          <ul className="space-y-2">
            {entries.map((e) => (
              <QueueRow key={e.localId} entry={e} onRetry={retry} />
            ))}
          </ul>
        </section>
      )}

      {entries.length > 0 && entries.every((e) => e.status === "ready") && (
        <div className="mt-8 text-center">
          <Link
            href="/timeline"
            className="font-label inline-block rounded-full bg-primary px-8 py-4 uppercase tracking-[0.2em] text-on-primary hover:bg-on-primary-fixed-variant"
          >
            View in timeline
          </Link>
        </div>
      )}
    </main>
  );
}

function QueueRow({
  entry,
  onRetry,
}: {
  entry: UploadEntry;
  onRetry: (localId: string) => void;
}) {
  const labelMap: Record<UploadEntry["status"], string> = {
    queued: "Queued",
    uploading: "Uploading",
    processing: "Processing",
    ready: "Ready",
    failed: "Failed",
    error: "Error",
  };

  const colorMap: Record<UploadEntry["status"], string> = {
    queued: "text-secondary",
    uploading: "text-primary",
    processing: "text-primary",
    ready: "text-primary",
    failed: "text-error",
    error: "text-error",
  };

  return (
    <li className="card-elevation flex items-center justify-between rounded-[16px] bg-surface-container-lowest p-4">
      <div className="min-w-0 flex-1">
        <p className="truncate text-base text-primary">{entry.filename}</p>
        {entry.error && <p className="mt-1 text-xs text-error">{entry.error}</p>}
      </div>
      <div className="ml-4 flex items-center gap-3">
        <p className={`font-label ${colorMap[entry.status]}`}>{labelMap[entry.status]}</p>
        {entry.status === "error" && (
          <button
            type="button"
            onClick={() => onRetry(entry.localId)}
            className="font-label text-secondary hover:text-primary"
          >
            Retry
          </button>
        )}
        {entry.status === "ready" && entry.photoId && (
          <Link
            href={`/photos/${entry.photoId}`}
            className="font-label text-secondary hover:text-primary"
          >
            View
          </Link>
        )}
      </div>
    </li>
  );
}
