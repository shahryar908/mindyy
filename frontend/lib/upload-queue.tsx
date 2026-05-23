"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "./api";
import type { ItemStatus } from "./types";

export type UploadEntry = {
  // localId is generated client-side so we can track the entry before the server returns the photo id.
  localId: string;
  filename: string;
  // Server-side photo id (memory_item_id). Null until upload returns 202.
  photoId: string | null;
  status: "queued" | ItemStatus | "error";
  error?: string;
};

type QueueState = {
  entries: UploadEntry[];
  inFlightCount: number;
  enqueue: (files: File[]) => void;
  clearFinished: () => void;
  retry: (localId: string) => void;
};

const QueueContext = createContext<QueueState | null>(null);

const MAX_CONCURRENT = 3;
const POLL_INTERVAL_MS = 2000;
const ACTIVE_STATUSES: UploadEntry["status"][] = ["queued", "uploading", "processing"];

function randomId() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function UploadQueueProvider({
  children,
  onPhotoReady,
}: {
  children: React.ReactNode;
  onPhotoReady?: (photoId: string) => void;
}) {
  const [entries, setEntries] = useState<UploadEntry[]>([]);
  // Mirror in a ref so the polling worker reads fresh state without re-subscribing.
  const entriesRef = useRef<UploadEntry[]>([]);
  entriesRef.current = entries;

  // Track files awaiting upload start (because we cap concurrency).
  const pendingFiles = useRef<Map<string, File>>(new Map());

  const updateEntry = useCallback((localId: string, patch: Partial<UploadEntry>) => {
    setEntries((curr) => curr.map((e) => (e.localId === localId ? { ...e, ...patch } : e)));
  }, []);

  const startUpload = useCallback(
    async (localId: string, file: File) => {
      updateEntry(localId, { status: "uploading" });
      try {
        const res = await api.uploadPhoto(file);
        updateEntry(localId, {
          photoId: res.id,
          status: res.status,
        });
      } catch (err) {
        const message = err instanceof ApiError ? err.detail : "Upload failed";
        updateEntry(localId, { status: "error", error: message });
        toast.error(`${file.name}: ${message}`);
      } finally {
        pendingFiles.current.delete(localId);
      }
    },
    [updateEntry],
  );

  // Drain pending uploads up to MAX_CONCURRENT
  useEffect(() => {
    const uploadingCount = entries.filter((e) => e.status === "uploading").length;
    if (uploadingCount >= MAX_CONCURRENT) return;
    const slots = MAX_CONCURRENT - uploadingCount;
    const queued = entries.filter((e) => e.status === "queued").slice(0, slots);
    for (const e of queued) {
      const file = pendingFiles.current.get(e.localId);
      if (file) {
        void startUpload(e.localId, file);
      }
    }
  }, [entries, startUpload]);

  // Polling worker for in-flight items
  useEffect(() => {
    const interval = setInterval(async () => {
      const current = entriesRef.current;
      const toPoll = current.filter(
        (e) =>
          e.photoId !== null &&
          (e.status === "uploading" || e.status === "processing"),
      );
      if (toPoll.length === 0) return;

      await Promise.all(
        toPoll.map(async (entry) => {
          if (!entry.photoId) return;
          try {
            const status = await api.getPhotoStatus(entry.photoId);
            if (status.status === entry.status) return;
            updateEntry(entry.localId, { status: status.status });
            if (status.status === "ready") {
              toast.success(`${entry.filename} is ready`);
              onPhotoReady?.(entry.photoId);
            } else if (status.status === "failed") {
              toast.error(`${entry.filename} failed to process`);
            }
          } catch {
            // Network blip — try again next tick.
          }
        }),
      );
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [updateEntry, onPhotoReady]);

  const enqueue = useCallback((files: File[]) => {
    const newEntries: UploadEntry[] = files.map((f) => {
      const localId = randomId();
      pendingFiles.current.set(localId, f);
      return { localId, filename: f.name, photoId: null, status: "queued" };
    });
    setEntries((curr) => [...curr, ...newEntries]);
  }, []);

  const clearFinished = useCallback(() => {
    setEntries((curr) =>
      curr.filter(
        (e) =>
          e.status === "queued" ||
          e.status === "uploading" ||
          e.status === "processing",
      ),
    );
  }, []);

  const retry = useCallback(
    (localId: string) => {
      const entry = entriesRef.current.find((e) => e.localId === localId);
      if (!entry || entry.status !== "error") return;
      updateEntry(localId, { status: "queued", error: undefined });
    },
    [updateEntry],
  );

  const inFlightCount = entries.filter((e) =>
    ACTIVE_STATUSES.includes(e.status),
  ).length;

  return (
    <QueueContext.Provider value={{ entries, inFlightCount, enqueue, clearFinished, retry }}>
      {children}
    </QueueContext.Provider>
  );
}

export function useUploadQueue() {
  const ctx = useContext(QueueContext);
  if (!ctx) throw new Error("useUploadQueue must be used inside UploadQueueProvider");
  return ctx;
}
