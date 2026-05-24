# MINDY

A personal photo memory assistant. Upload your photos and ask questions about them in natural language: *"highlights of last month"*, *"photos with Ahmed"*, *"that day at the beach"*. The system runs each photo through a vision LLM (caption + scene tags + OCR + safety), a face detector (clustering same people across photos), and a text embedder (so semantic search just works). Then a streaming chat endpoint turns your question into a grounded narrative with the relevant moment cards underneath.

> **Status: in active development.** Auth + upload + processing pipeline + retrieval + chat all work end-to-end on a single developer machine. Deployment story not yet built.

---

## Table of contents

1. [What it does](#what-it-does)
2. [Tech stack](#tech-stack)
3. [System architecture](#system-architecture)
4. [Database schema](#database-schema)
5. [Three core flows](#three-core-flows)
6. [Repository layout](#repository-layout)
7. [API surface](#api-surface)
8. [Getting it running locally](#getting-it-running-locally)
9. [Environment variables](#environment-variables)
10. [Running tests](#running-tests)
11. [What's deliberately out of scope](#whats-deliberately-out-of-scope)

---

## What it does

1. **Sign up + verify by email OTP.** Email/password or Google OAuth. JWT access + refresh tokens. Password reset by token.
2. **Drag-and-drop photo upload.** Multi-file, 3-concurrent, survives navigation via a global upload queue. Files stream directly into S3 — no buffering in the backend.
3. **Background processing pipeline** runs per upload:
   - EXIF extraction (date taken, GPS, camera).
   - WebP thumbnail generation, written back to S3.
   - Vision: caption, scene tags, objects, OCR text, safety flag (Groq Llama 4 Scout).
   - Face detection + clustering (InsightFace `buffalo_l`, cosine similarity against the user's existing clusters).
   - Text embedding (sentence-transformers `all-MiniLM-L6-v2`, 384-dim).
4. **Timeline view** with infinite scroll. Photos visible immediately as `processing`, then flip to `ready` with caption + thumbnail.
5. **People page**: every detected face cluster, sortable, renamable inline.
6. **Chat**: a single natural-language box. Backend parses intent → embeds query → hybrid SQL+vector retrieval → Cohere rerank → Groq streams the narrative answer back over Server-Sent Events while the moment cards render immediately.

---

## Tech stack

### Backend (`backend/`)

- **FastAPI** + **uvicorn** — HTTP layer.
- **SQLModel** (SQLAlchemy 2.x) — ORM + Pydantic models in one class.
- **PostgreSQL 16 + pgvector** in production; **SQLite** transparent fallback for tests and local dev. Tables auto-switch column types based on `DATABASE_URL` prefix.
- **Redis** — OTP storage with TTL, rate-limit counters.
- **AWS S3** — image storage (originals + thumbnails). Private bucket, presigned GET URLs for browser access.
- **slowapi** — IP-based rate limiting on abuse-prone endpoints.
- **Groq** — vision (Llama 4 Scout multimodal) and chat (Llama 3.3 70B Versatile).
- **sentence-transformers** — local embedding model (no API cost, ~280 MB model on first use).
- **InsightFace** + **onnxruntime** — face detection and embedding.
- **Cohere** — reranking (`rerank-english-v3.0`).
- **sse-starlette** — Server-Sent Events for streaming chat.
- **FastAPI BackgroundTasks** — in-process job runner for the photo pipeline. (Designed to swap to Arq + Redis worker later without changing the orchestrator function.)
- **pytest** + **fakeredis** + **moto** — fully mocked test suite, no live API calls.

### Frontend (`frontend/`)

- **Next.js 16** App Router (Turbopack).
- **React 19**.
- **TailwindCSS v4** with a custom "Soft Noir" design system (Playfair Display + Plus Jakarta Sans).
- **sonner** — toasts.
- Manual SSE consumer using `fetch` + `ReadableStream` (since `EventSource` doesn't support POST).
- Tokens in `localStorage` for v1 (httpOnly cookies are a planned upgrade).

---

## System architecture

A two-process stack today: Next.js dev server on `:3000`, FastAPI on `:8000`. Postgres and Redis run via `docker compose`. AWS S3 is the only external infrastructure dependency for storage.

```
                       BROWSER (Next.js 16, localhost:3000)
                       ────────────────────────────────────
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           │                         │                         │
      public pages              (app) group              auth pages
      /                       (auth guard +              /sign-in
                              UploadQueueProvider        /sign-up
                              + Toaster + AppNav)        /verify-otp
                                     │                   /forgot-password
           ┌──────────┬──────────────┼──────────────┬──────────┐
      /timeline   /upload     /photos/[id]   /people, /[id]   /chat   /profile
           │          │             │              │           │         │
           ▼          ▼             ▼              ▼           ▼         ▼
                             ┌──────────────────────────────┐
                             │   lib/api.ts (single client) │
                             │  - bearer token attach       │
                             │  - 401 → /auth/refresh once  │
                             │  - hard-fail → /sign-in      │
                             └──────────────┬───────────────┘
                                            │
       ┌────────────────────────────────────┼────────────────────────────────┐
       │              lib/upload-queue.tsx (global state)                    │
       │  - 3-concurrent upload cap                                          │
       │  - 2s polling of /photos/{id}/status while uploading/processing     │
       │  - sonner toasts on ready / failed                                  │
       └────────────────────────────────────┬────────────────────────────────┘
                                            │
                                            │  HTTP + multipart + SSE
                                            ▼
                       FASTAPI BACKEND (uvicorn, :8000)
                       ────────────────────────────────
                                     │
      ┌──────────────────┬───────────┼─────────────────┬─────────────────┐
      │                  │           │                 │                 │
      /auth              /photos     /photos/upload    /photos/people    /chat
      ├ signup           ├ list      ├ POST multipart  ├ GET clusters    SSE stream:
      ├ verify-otp       ├ {id}      └ rate 30/min     └ PATCH {id}       1) cards event
      ├ signin           ├ {id}/status                                    2) token tokens
      ├ refresh-token    ├ DELETE                                         3) done
      ├ forgot-password  └ cluster_id filter
      ├ reset-password
      └ google/{login,callback}
           │                  │                       │                  │
           │       ┌──────────┴──────────┐            │                  │
           ▼       ▼                     ▼            ▼                  │
      ┌────────────────┐   FastAPI BackgroundTasks                       │
      │ rate-limit     │              │                                  │
      │ (slowapi)      │              ▼                                  │
      └────────────────┘   ┌─────────────────────────────────────┐       │
           │               │ pipeline.run_photo_pipeline()       │       │
           │               │   1. download from S3               │       │
           │               │   2. extract_exif (Pillow + HEIC)   │       │
           │               │   3. make_thumbnail (WebP)→S3       │       │
           │               │   4. describe_image (Groq vision)   │       │
           │               │   5. detect_and_cluster_faces       │       │
           │               │   6. embed_text (MiniLM)            │       │
           │               │   7. upsert photo_metadata + status │       │
           │               │      → READY                        │       │
           │               └─────────────────────────────────────┘       │
           │                                                             │
           │  /chat orchestration ←───────────────────────────────────────┘
           │       1. parse_intent          → Groq llama-3.3-70b
           │       2. embed_query           → sentence-transformers
           │       3. retrieve_candidates   → SQL filter + pgvector cosine
           │       4. rerank_candidates     → Cohere rerank-v3
           │       5. stream_narrative      → Groq streaming → SSE frames
           │
           ▼
      ┌──────────────────┐   ┌─────────────────┐   ┌─────────────────────┐
      │ Postgres 16 +    │   │ Redis           │   │ AWS S3 (private)    │
      │ pgvector         │   │ (docker or      │   │                     │
      │                  │   │  memurai)       │   │ photos/<uid>/<uuid> │
      │ users            │   │                 │   │ thumbs/<uid>/<uuid> │
      │ memory_items     │   │ otp:<uid>       │   │                     │
      │ photo_metadata   │   │ otp_cooldown    │   │ presigned reads     │
      │ face_clusters    │   │ rate-limit keys │   │ direct PUTs from    │
      │ faces            │   │                 │   │ backend             │
      │  ├ vec(384) text │   │                 │   │                     │
      │  ├ vec(512) face │   │                 │   │                     │
      │  └ ivfflat idx   │   │                 │   │                     │
      └──────────────────┘   └─────────────────┘   └─────────────────────┘
```

### State boundaries (where data lives)

| Layer                  | What's in it                              |
|------------------------|-------------------------------------------|
| URL                    | route, current photo id, cluster id       |
| Component-local state  | form inputs, chat turn history, edit mode |
| React Context (global) | auth + tokens, upload queue + polling     |
| `localStorage`         | `mindyy_access`, `mindyy_refresh`         |
| Postgres / SQLite      | persistent truth (users, photos, faces)   |
| Redis                  | OTPs, rate-limit counters, cooldowns      |
| S3                     | image bytes (originals + WebP thumbs)     |

---

## Database schema

```
                ┌───────────────────────┐
                │        users          │
                ├───────────────────────┤
                │ id              UUID  │── PK
                │ email           text  │── unique
                │ hashed_password text? │
                │ is_verified     bool  │
                │ provider        enum  │── local | google
                │ google_sub      text? │── unique
                │ created_at      ts    │
                └─────────┬─────────────┘
                          │ 1
                          │
                 ┌────────┴────────┐
                 │ N               │ N
   ┌─────────────▼────────┐   ┌────▼──────────────────┐
   │     memory_items     │   │     face_clusters     │
   ├──────────────────────┤   ├───────────────────────┤
   │ id              UUID │── PK
   │ user_id         UUID │── FK→users
   │ type            enum │── photo (future: pdf/text)
   │ status          enum │── uploading|processing|ready|failed
   │ source_key      text │── S3 key, not URL
   │ thumbnail_key   text?│── S3 key
   │ taken_at        ts?  │── from EXIF
   │ location        text?│── "lat,lng" if GPS in EXIF
   │ item_metadata   JSON │── filename, content_type, ...
   │ created_at      ts   │
   └─────────┬────────────┘
             │ 1
             │
   ┌─────────┴───────────────┐
   │ 1                       │ N            ┌───────────────────────┐
   ▼                         ▼              │     face_clusters     │
┌─────────────────────┐    ┌────────────┐   ├───────────────────────┤
│   photo_metadata    │    │   faces    │   │ id            UUID    │── PK
├─────────────────────┤    ├────────────┤   │ user_id       UUID    │── FK→users
│ memory_item_id PK,FK│    │ id     PK  │   │ label         text?   │── rename target
│ caption        text?│    │ memory_item│   │ rep_embedding vec(512)│── running centroid
│ ocr_text       text?│    │   id   FK  │── │ face_count    int     │
│ scenes         JSON │    │ cluster_id │── │ created_at    ts      │
│ objects        JSON │    │   FK   ────┼──▶└───────────────────────┘
│ safe           bool │    │ bbox JSON  │
│ width          int? │    │ embedding  │
│ height         int? │    │   vec(512) │
│ camera_make    text?│    └────────────┘
│ camera_model   text?│
│ text_embedding      │    Indexes (Postgres only):
│   vec(384)          │      ivfflat(text_embedding, vector_cosine_ops)
└─────────────────────┘      ivfflat(faces.embedding, vector_cosine_ops)
                             ivfflat(face_clusters.rep_embedding, vector_cosine_ops)
                             btree(memory_items.user_id, taken_at)
                             btree(faces.cluster_id)
```

### Polymorphic design

`memory_items` is the polymorphic root — only photos today, but PDFs, text notes, or voice memos can join later via their own `*_metadata` side-table without touching the queries that operate on the timeline.

### Vector storage

- **Postgres**: real `vector(N)` columns via `pgvector`. IVFFlat indexes for cosine distance.
- **SQLite** (tests and zero-setup dev): the same columns are stored as `LargeBinary`. The switch happens in `photos/tables.py` based on `DATABASE_URL`. Retrieval falls back to in-Python cosine sort with a 500-row cap when not on Postgres.

---

## Three core flows

### 1. Upload → ready → visible in timeline

```
Browser (/upload)
  → fetch POST /photos/upload (multipart)
       → backend: put_object → S3
       → backend: insert memory_items (status=uploading)
       → backend: BackgroundTasks.add_task(run_photo_pipeline)
       → return 202 {id}
  ← UploadQueueProvider stores photoId, status=uploading

[Background pipeline runs in the uvicorn process]
  download → EXIF → thumbnail (→S3) → vision → faces → embedding
  → status=ready, photo_metadata upserted

[Meanwhile in browser]
  Queue poller every 2s → GET /photos/{id}/status
  → status flips uploading → processing → ready
  → sonner toast "<filename> is ready"
  → /timeline detects readyCount change → re-fetch /photos
  → new tile appears with caption + thumbnail
```

### 2. Chat (the SSE flow)

```
Browser /chat:
  fetch POST /chat (Accept: text/event-stream)
    body: {query: "highlights of last month"}
    │
    ▼  manual SSE parser (lib/sse.ts)
  backend:
    parse_intent (Groq)
    → embed_query (local model)
    → retrieve_candidates (SQL + pgvector cosine)
    → rerank (Cohere)
    → build signed URLs for top 5 thumbnails
    yields:
      event: cards
      data: [{id, thumbnail_url, caption, taken_at}, ...]
                                                ──► grid renders ~300 ms in
      event: token
      data: "Across June..."                     ──► text streams char by char
      event: token
      data: " you visited the beach..."
      ...
      event: done                                ──► input re-enabled
```

The cards arrive in the first frame, the narrative streams underneath in subsequent frames. From the user's perspective, the answer feels instant.

### 3. 401 silent refresh

```
Any (app) page → fetch some endpoint
  ← 401 (access expired)
  client.ts:
    POST /auth/refresh-token with stored refresh_token
    ─ success: store new pair, retry original request once
                user sees nothing happen
    ─ fail:    tokenStore.clear()
               window.location = /sign-in?reason=expired&next=<here>
```

---

## Repository layout

```
mindyy/
├── README.md                       ← this file
├── .gitignore                      ← root: blocks .env everywhere
├── backend/
│   ├── main.py                     FastAPI app + lifespan + CORS + slowapi
│   ├── db.py                       engine + init_db (auto-pgvector on Postgres)
│   ├── redis_client.py             single Redis connection
│   ├── rate_limit.py               slowapi Limiter
│   ├── docker-compose.yml          Postgres + Redis
│   ├── pyproject.toml              dependencies (uv)
│   ├── .env.example                template
│   ├── auth/
│   │   ├── routes.py               signup, signin, OTP, password reset, Google OAuth
│   │   ├── schemas.py              Pydantic request/response shapes
│   │   ├── security.py             bcrypt + JWT
│   │   ├── otp.py                  Redis-backed OTP gen/verify
│   │   ├── email.py                SMTP sender
│   │   ├── google.py               OAuth code-exchange + id_token verify
│   │   ├── deps.py                 get_current_user dependency
│   │   └── tables.py               re-exports User from models
│   ├── models/
│   │   └── tables.py               User + Auth_provider
│   ├── photos/
│   │   ├── routes.py               upload, list, get, delete, status, people
│   │   ├── schemas.py
│   │   ├── tables.py               MemoryItem, PhotoMetadata, FaceCluster, Face
│   │   ├── storage.py              S3 wrapper (boto3, lazy client)
│   │   └── processing/
│   │       ├── pipeline.py         run_photo_pipeline orchestrator
│   │       ├── exif.py             EXIF extraction (HEIC via pillow-heif)
│   │       ├── thumbnails.py       WebP thumbnail generator
│   │       ├── vision.py           Groq vision call
│   │       ├── faces.py            InsightFace detection + clustering
│   │       └── embeddings.py       sentence-transformers wrapper
│   ├── chat/
│   │   ├── routes.py               POST /chat (SSE endpoint)
│   │   ├── schemas.py
│   │   ├── intent.py               Groq intent router
│   │   ├── retrieval.py            hybrid SQL + pgvector
│   │   ├── rerank.py               Cohere rerank with graceful fallback
│   │   └── synthesis.py            Groq streaming narrative
│   ├── scripts/
│   │   └── backfill_embeddings.py  one-off re-embedding script
│   └── tests/
│       ├── conftest.py             in-memory SQLite + fakeredis + S3 mock
│       ├── test_signup.py
│       ├── test_signin.py
│       ├── test_password_reset.py
│       ├── test_tokens.py
│       ├── test_google_oauth.py
│       ├── test_photos.py
│       ├── test_processing.py
│       └── test_chat.py
│
└── frontend/
    ├── package.json                Next 16, React 19, sonner
    ├── tsconfig.json               @/* path alias
    ├── next.config.ts
    ├── postcss.config.mjs          Tailwind v4
    ├── app/
    │   ├── layout.tsx              fonts + AuthProvider
    │   ├── page.tsx                landing or redirect to /timeline
    │   ├── globals.css             Noir palette + custom CSS
    │   ├── sign-in/page.tsx
    │   ├── sign-up/page.tsx
    │   ├── verify-otp/page.tsx
    │   ├── forgot-password/page.tsx
    │   ├── reset-password/page.tsx
    │   ├── auth/callback/page.tsx  Google return handler
    │   └── (app)/
    │       ├── layout.tsx          auth guard + AppNav + UploadQueueProvider
    │       ├── timeline/page.tsx
    │       ├── upload/page.tsx
    │       ├── photos/[id]/page.tsx
    │       ├── people/page.tsx
    │       ├── people/[id]/page.tsx
    │       ├── chat/page.tsx
    │       └── profile/page.tsx
    ├── components/
    │   ├── TopNav.tsx              public-page nav
    │   ├── AppNav.tsx              protected-page nav (Timeline | Upload | People | Chat | Settings)
    │   ├── AuthCard.tsx
    │   ├── FormField.tsx
    │   └── PrimaryButton.tsx
    └── lib/
        ├── api.ts                  single HTTP client, 401 silent refresh
        ├── auth-context.tsx        useAuth hook
        ├── upload-queue.tsx        UploadQueueProvider + polling worker
        ├── sse.ts                  manual SSE parser
        └── types.ts                TS mirrors of backend Pydantic models
```

---

## API surface

### Auth (`/auth/*`)

| Method | Path                     | Body                          | Returns                      |
|--------|--------------------------|-------------------------------|------------------------------|
| POST   | `/auth/signup`           | `{email, password}`           | `201 {user_id, email}`       |
| POST   | `/auth/verify-otp`       | `{user_id, code}`             | `{access, refresh}`          |
| POST   | `/auth/resend-otp`       | `{email}`                     | `{message}` (no enumeration) |
| POST   | `/auth/signin`           | `{email, password}`           | `{access, refresh}`          |
| POST   | `/auth/forgot-password`  | `{email}`                     | `200` always (no enumeration)|
| POST   | `/auth/reset-password`   | `{token, new_password}`       | `{message}`                  |
| POST   | `/auth/refresh-token`    | `{refresh_token}`             | `{access, refresh}`          |
| POST   | `/auth/logout`           | bearer                        | `{message}` (best-effort)    |
| GET    | `/auth/me`               | bearer                        | `{id, email, is_verified}`   |
| GET    | `/auth/google/login`     | -                             | 307 → Google + state cookie  |
| GET    | `/auth/google/callback`  | `?code&state`                 | 307 → frontend with tokens   |

Rate limits per IP: signup 5/min · signin 10/min · verify-otp 10/min · resend-otp 3/min · forgot-password 3/min.

### Photos (`/photos/*`)

| Method | Path                          | Body / Query                   | Returns                  |
|--------|-------------------------------|--------------------------------|--------------------------|
| POST   | `/photos/upload`              | multipart `file`               | `202 {id, status}`       |
| GET    | `/photos`                     | `?limit&cursor&cluster_id`     | `{items, next_cursor}`   |
| GET    | `/photos/{id}`                | bearer                         | full `PhotoRead`         |
| GET    | `/photos/{id}/status`         | bearer                         | `{id, status}`           |
| DELETE | `/photos/{id}`                | bearer                         | `204`                    |
| GET    | `/photos/people`              | bearer                         | `[{id, label, face_count, sample_thumbnail_url}]` |
| PATCH  | `/photos/people/{cluster_id}` | `{label}`                      | updated cluster          |

Upload rate-limit: 30/min per IP.

### Chat (`/chat`)

| Method | Path     | Body          | Returns                       |
|--------|----------|---------------|-------------------------------|
| POST   | `/chat`  | `{query}`     | `text/event-stream`           |

Rate limit: 30/hour per IP. SSE frames: `cards` (one), `token` (many), `done` (one).

---

## Getting it running locally

### Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/) for the backend.
- Node 20+ and npm for the frontend.
- Docker Desktop (for Postgres + Redis), or Memurai for Redis-on-Windows + a local Postgres install.
- An AWS S3 bucket (private) + IAM user with `PutObject`/`GetObject`/`DeleteObject` on it.
- A [Groq API key](https://console.groq.com/keys) (free tier covers dev).
- A [Cohere API key](https://dashboard.cohere.com/api-keys) (free trial covers dev).
- An SMTP account for OTP email — [Mailtrap](https://mailtrap.io) for dev, or Gmail app-password.

### 1. Backend

```powershell
cd backend
docker compose up -d                 # Postgres + Redis
cp .env.example .env                 # fill values — see "Environment variables"
uv sync                              # ~5 min first time (PyTorch is heavy)
uv run python -c "from db import init_db; init_db()"
uv run uvicorn main:app --reload
```

### 2. Create IVFFlat indexes (Postgres only, once you have ~50+ photos)

```sql
CREATE INDEX IF NOT EXISTS ix_photo_metadata_text_embedding
  ON photo_metadata USING ivfflat (text_embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS ix_faces_embedding
  ON faces USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS ix_face_clusters_rep_embedding
  ON face_clusters USING ivfflat (rep_embedding vector_cosine_ops) WITH (lists = 50);
```

### 3. Frontend

```powershell
cd frontend
cp .env.local.example .env.local     # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

Open `http://localhost:3000`. Sign up, check Mailtrap for the OTP, verify, upload a photo, watch the timeline.

### First-photo gotcha

On the first photo, sentence-transformers downloads `all-MiniLM-L6-v2` (~280 MB) and InsightFace downloads `buffalo_l` (~280 MB). Both download into `~/.cache/huggingface/` and `~/.insightface/` respectively. Subsequent photos skip the download. On a slow connection this can take 10-30 minutes — that's a one-time cost.

To pre-warm without uploading a photo:

```powershell
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
uv run python -c "import insightface; a=insightface.app.FaceAnalysis(name='buffalo_l'); a.prepare(ctx_id=-1)"
```

---

## Environment variables

### Backend (`backend/.env`)

```env
# --- Database ---
DATABASE_URL=postgresql+psycopg://mindyy:mindyy@localhost:5432/mindyy
# Or for zero-setup dev: sqlite:///./mindyy.db

# --- Auth ---
JWT_SECRET=<at least 32 random bytes>

# --- Infra ---
REDIS_URL=redis://localhost:6379/0
CORS_ORIGINS=http://localhost:3000

# --- Email (OTP) ---
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=<mailtrap user>
SMTP_PASSWORD=<mailtrap pass>
SMTP_FROM=no-reply@mindyy.local
SMTP_USE_TLS=true

# --- Google OAuth ---
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
FRONTEND_REDIRECT_URL=http://localhost:3000/auth/callback

# --- S3 ---
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=ap-south-1
S3_BUCKET=mindyy-uploads-dev

# --- LLMs ---
GROQ_API_KEY=
VISION_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
CHAT_LLM_MODEL=llama-3.3-70b-versatile

# --- Reranker ---
COHERE_API_KEY=
RERANK_MODEL=rerank-english-v3.0

# --- Embeddings (local — no API key) ---
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384

# --- Faces ---
INSIGHTFACE_MODEL=buffalo_l
FACE_SIMILARITY_THRESHOLD=0.6
```

### Frontend (`frontend/.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Never commit `.env` or `.env.local`. The root `.gitignore` already blocks both.

---

## Running tests

```powershell
cd backend
uv run pytest
```

The test suite runs against in-memory SQLite + fakeredis + a dict-based S3 mock. No live API calls — `embed_text`, `describe_image`, `detect_and_cluster_faces`, Cohere rerank, and Groq chat are all mocked via fixtures in `conftest.py`. A full run completes in under 30 seconds. Test isolation is the most important guarantee — cross-user access tests live in every router's test file.

---

## What's deliberately out of scope

- **Job queue persistence.** Background processing uses FastAPI's `BackgroundTasks` (in-process). On uvicorn restart, in-flight jobs are lost. Designed to swap to Arq (Redis-backed worker) by changing one function in `photos/routes.py`.
- **httpOnly cookies for auth.** Tokens currently live in `localStorage`. Vulnerable to XSS if the app ever has a script-injection bug. Planned upgrade.
- **Token revocation on logout.** Pure JWT — `/auth/logout` is best-effort. A `jti` blocklist table is the path forward.
- **Cluster merge/split.** Backend endpoints not built. Frontend `/people` only supports rename today.
- **Date/people filter UI on `/timeline`.** Cluster filter works via the `cluster_id` query param; date-range and status filters need backend params + UI.
- **Multi-turn chat memory.** Each chat call is independent — no conversation history is persisted server-side.
- **Production deployment story.** No Dockerfile, no CI, no migration tool. Schema is created via `SQLModel.metadata.create_all` which is fine for dev but you'll want Alembic before production.

---

## Recruiter line

A two-process stack (Next.js + FastAPI) with five LLM-touching layers:

1. **Vision** — Groq Llama 4 Scout, single multimodal call returns caption + scenes + objects + OCR + safety in one JSON response.
2. **Face clustering** — InsightFace embeddings with an online running-mean centroid algorithm; cosine similarity 0.6 threshold; new faces either join existing clusters or seed new ones in the same transaction.
3. **Text embeddings** — local sentence-transformers, no API cost; same model at index-time and query-time so distances stay comparable.
4. **Hybrid retrieval** — pgvector cosine search inside a SQL query that first applies user-scoped structured filters (date range, person), then orders the remainder by semantic distance.
5. **Two-stage reranking + grounded synthesis** — Cohere narrows 20 candidates to 5; Groq streams a constrained narrative ("never invent details not in captions/dates/tags"); SSE delivers cards in the first frame and tokens in subsequent frames.

The full request-to-response path for a chat query touches three external APIs, one Postgres hybrid query, and one streaming response — and runs in under three seconds. Every external dependency is mocked at the test boundary so the suite runs offline in under 30 seconds.
