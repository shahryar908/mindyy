export type ItemStatus = "uploading" | "processing" | "ready" | "failed";

export type ItemType = "photo";

export type Photo = {
  id: string;
  type: ItemType;
  status: ItemStatus;
  source_url: string | null;
  thumbnail_url: string | null;
  taken_at: string | null;
  location: string | null;
  caption: string | null;
  scenes: string[];
  objects: string[];
  ocr_text: string | null;
  item_metadata: Record<string, unknown>;
  created_at: string;
};

export type PhotoListResponse = {
  items: Photo[];
  next_cursor: string | null;
};

export type PhotoStatusResponse = {
  id: string;
  status: ItemStatus;
};

export type UploadResponse = {
  id: string;
  status: ItemStatus;
  message: string;
};

export type FaceCluster = {
  id: string;
  label: string | null;
  face_count: number;
  sample_thumbnail_url: string | null;
};

export type PhotoFilters = {
  cluster_id?: string;
  // future: start_date, end_date, status etc.
};

export type ChatCard = {
  id: string;
  thumbnail_url: string | null;
  caption: string;
  taken_at: string | null;
};
