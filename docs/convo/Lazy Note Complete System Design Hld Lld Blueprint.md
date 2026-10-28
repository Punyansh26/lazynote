# Lazy Note — Complete Production Software Architecture, System Design (HLD & LLD), OOP Class Blueprint & SaaS Engineering Bible

**Role:** Principal Systems Architect & Senior Staff Mentor  
**Target Builder:** Python-First Developer Building Their First Production Multi-Tenant SaaS  
**System Scope:** End-to-End Hinglish/Multimodal Lecture & Meeting Engine (Phase 1 Audio/DSP/ASR + Phase 2 Multi-Lens Workspace, Contextual Hybrid RAG & Android Omnichannel Clipper)

---

## 1. The Architectural Mindset & Language Decision: Can We Build Everything in Python?

Since this is your first production SaaS project and **Python is your strongest language**, the very first decision we must make as architects is: **Where should we use Python, and where are we forced by browser/OS physics to use TypeScript?**

### 1.1 The Honest Engineering Rule: "Python for the Brain & Heavy Lifting, TypeScript Thin-Client for the Edge"
A common beginner mistake is trying to either (a) build the entire web/mobile UI in pure Python (using tools like Streamlit, Gradio, or Anvil), OR (b) rewrite the entire AI/audio backend in Node.js just to use one language. **Both approaches fail in production for Lazy Note:**
* **Why Pure Python UI Frameworks (Streamlit/Gradio/NiceGUI) Fail Here:** Streamlit runs on a server and re-runs your Python script on every button click. It **cannot** access the mobile browser's `IndexedDB` when classroom Wi-Fi drops for 90 minutes, cannot run an offline `MediaRecorder` 30-second chunk queue, cannot invoke the Android native Share Sheet (`Intent.ACTION_SEND`), and cannot render an instant offline-capable Notion-style block editor ([BlockNote](https://www.blocknotejs.org/) / [Tiptap](https://tiptap.dev/)).
* **Why Node.js Fails for the Backend Worker:** Audio Digital Signal Processing (`ffmpeg`, `soundfile`, `numpy`), neural speech enhancement ([DeepFilterNet3](https://github.com/rikorose/deepfilternet)), Voice Activity Detection (`torch` + **Silero VAD v6**), academic PDF layout parsing ([IBM Docling](https://github.com/docling-project/docling)), and AI orchestration (`google-genai`, `pydantic`) are **first-class citizens in Python**. Running PyTorch and Docling inside Node.js is painful and brittle.

### 1.2 The Production Architecture Split (80% Python Backend + 20% TypeScript Edge UI)
We design Lazy Note as a **Strict API-Driven Modular Monolith + Async Worker** where **80% of your business logic, OOP classes, database models, AI prompts, audio DSP, and billing rules live in Python (FastAPI)**, and the frontend (Next.js PWA + Expo Android) acts as a **Thin Reactive State & Capture Layer**.

| Architectural Layer | Technology Selected | Alternatives Considered | Why We Chose This & Tradeoff Analysis |
| :--- | :--- | :--- | :--- |
| **Backend API & Domain Logic** | **Python 3.12 + [FastAPI](https://fastapi.tiangolo.com/) + [Pydantic v2](https://www.google.com/search?q=https://docs.pydantic.dev/)** | Django Ninja, Flask, Node.js (NestJS), Go | **Why:** You already know Python. FastAPI gives you asynchronous I/O (`async def`) for high concurrency, automatic Swagger/OpenAPI docs (`/docs`), and Pydantic v2 (written in Rust) for strict type validation and Gemini Structured Outputs. **Tradeoff:** Python is slower than Go for raw CPU loops, which doesn't matter because heavy work is offloaded to C++/Rust-backed libraries (`ffmpeg`, `pytorch`, `pydantic-core`). |
| **Database ORM & Migrations** | **[SQLAlchemy 2.0 (Async)](https://docs.sqlalchemy.org/) + `asyncpg` + `Alembic`** | SQLModel, Tortoise ORM, Prisma, Raw SQL | **Why:** SQLAlchemy 2.0 with `Mapped[]` type annotations gives you clean Object-Oriented Python classes with full IDE autocomplete, non-blocking async Postgres queries via `asyncpg`, and battle-tested schema migrations via `Alembic`. **Tradeoff:** Slightly steeper learning curve than raw SQL, but prevents SQL injection and keeps complex relationships (`WorkspaceItem -> TranscriptRevision -> NoteArtifact`) maintainable. |
| **Primary Database, Vector Store & Search** | **[Supabase (Managed PostgreSQL 16)](https://supabase.com/docs/guides/ai/hybrid-search)** with `pgvector`, `ltree`, `tsvector` | MongoDB + Pinecone + Elasticsearch | **Why:** Using 3 separate databases (MongoDB for JSON + Pinecone for vectors + Elastic for keyword search) on your first project creates distributed sync nightmares and triples your cloud bill. PostgreSQL 16 handles relational tables, JSONB blocks, hierarchical folders (`ltree`), keyword search (`tsvector`), and HNSW vector embeddings (`pgvector`) inside **one ACID transaction**. |
| **Async Background Job Queue** | **[Celery 5.4](https://docs.celeryq.dev/) + Redis (Upstash)** *(or [Inngest](https://www.inngest.com/docs/patterns/jobs/keeping-your-api-fast) Python SDK)* | FastAPI `BackgroundTasks`, RabbitMQ, AWS SQS | **Why:** FastAPI's built-in `BackgroundTasks` runs inside the web server process—if your server restarts or scales down while transcribing a 90-minute lecture, the job dies silently! Celery + Redis (or Inngest) persists jobs to disk, supports automatic exponential-backoff retries, step checkpoints, and separates CPU-heavy FFmpeg/DeepFilterNet workers from fast web API workers. |
| **Blob & Media Object Storage** | **Cloudflare R2** (via `boto3` S3-compatible Python client) | AWS S3, Supabase Storage, Google Cloud Storage | **Why:** AWS S3 charges $0.09/GB every time a student streams or replays their lecture audio (egress fees). **Cloudflare R2 charges $0.00 egress fees** and uses the exact same `boto3` S3 Python SDK as AWS. |
| **Web & Mobile Capture Frontend** | **[Next.js 15 (App Router)](https://nextjs.org/) + Tailwind CSS + [BlockNote](https://www.blocknotejs.org/) + `Dexie.js`** | Streamlit (Python), React SPA (Vite), Flutter | **Why:** Next.js + PWA lets you deploy a single web app that works on laptops, Android, and iOS immediately, with `Dexie.js` wrapping `IndexedDB` for offline 30-second audio chunk queuing and BlockNote giving you a pre-built Notion-style editor in 20 lines of code. |
| **Android Share-Sheet Clipper (Phase 2/3)** | **React Native (Expo) + [`expo-share-intent`](https://github.com/0xkaz/agentclip-mobile)** | Native Kotlin, Flutter | **Why:** Shares TypeScript API types with your Next.js web app and provides a ready-made Android `SEND` intent receiver for <300ms link/Reel/YouTube clipping. |

---

## 2. Complete Python & Frontend Library Inventory (What to Install & Why)

Because this is your first production build, you should never guess which Python library to install. Here is the exact, curated `pyproject.toml` dependency map for your backend and why every single package exists:

| Category | Python Package (`pip` / `uv`) | Exact Role in Lazy Note |
| :--- | :--- | :--- |
| **Web Framework & Server** | `fastapi`, `uvicorn[standard]`, `uvloop`, `httptools` | High-performance ASGI web server handling REST endpoints, Webhooks, and Server-Sent Events (SSE). |
| **Data Validation & Settings** | `pydantic>=2.9`, `pydantic-settings` | Validates every API request/response, parses `.env` secrets safely, and enforces strict JSON schemas on Gemini LLM outputs. |
| **Database & Vector ORM** | `sqlalchemy[asyncio]>=2.0`, `asyncpg`, `alembic`, `pgvector` | Async PostgreSQL connection pooling, OOP table mapping, vector column support (`VECTOR(768)`), and schema version control. |
| **Task Queue & Caching** | `celery[redis]` (or `inngest`), `redis>=5.0` | Dispatches long-running audio stitching, DSP, STT, and RAG indexing jobs to background worker containers; powers rate-limiting and progress pub/sub. |
| **Cloud Storage & HTTP** | `boto3`, `httpx`, `tenacity` | `boto3` generates presigned Cloudflare R2 URLs; `httpx` makes async calls to Sarvam AI, Deepgram, and Jina Reader; `tenacity` provides automatic `@retry` decorators for flaky external APIs. |
| **Audio DSP, VAD & Media** | `ffmpeg-python`, `soundfile`, `numpy`, `torch`, `torchaudio`, `silero-vad`, `deepfilternet` | Concatenates WebM chunks, runs classical FFmpeg highpass/declick filters, runs **Silero VAD v6** silence stripping, and executes **DeepFilterNet3** neural noise suppression. |
| **AI, STT & Document Parsing** | `google-genai` (official Gemini SDK), `sarvamai`, `deepgram-sdk`, `docling`, `yt-dlp`, `trafilatura` | Interfaces with [Gemini 2.5 Flash](https://ai.google.dev/gemini-api/docs/models) (1M context + Vision + Embeddings), [Sarvam AI Saaras v4](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/batch-api), [Deepgram Nova-3](https://developers.deepgram.com/docs/models-languages-overview), [IBM Docling](https://github.com/docling-project/docling) for PDFs/slides, and [`yt-dlp`](https://www.socialkit.dev/blog/how-to-build-youtube-transcript-scraper-python) for YouTube/Reel extraction. |
| **Security, Billing & Observability** | `PyJWT[crypto]`, `razorpay` (or `stripe`), `structlog`, `sentry-sdk[fastapi]` | Verifies Supabase JWT auth tokens locally in `<1ms`, verifies Razorpay/Stripe payment webhooks, outputs structured JSON logs, and captures production stack traces. |
| **Testing & Code Quality** | `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy` | Runs automated unit/integration tests, formats/lints Python code in milliseconds (`ruff`), and checks static types (`mypy`). |

---

## 3. Production Repository & Folder Structure (Clean Architecture)

When beginners start a project, they often put all their code in two files: `main.py` and `utils.py`. Within three weeks, `main.py` grows to 4,000 lines of spaghetti code where SQL queries, FFmpeg shell commands, and LLM prompts are tangled together.

To prevent this, we use **Layered Clean Architecture (Domain-Driven Design Lite)**:
1. **`api/` (Presentation Layer):** Only handles HTTP requests, checks auth headers, validates Pydantic schemas, and calls a **Service**. It *never* writes raw SQL or calls FFmpeg directly.
2. **`services/` (Application Use-Case Layer):** Orchestrates business logic (e.g., `RecordingService`, `NoteGenerationService`, `RagChatService`). It coordinates repositories and external providers.
3. **`domain/` & `providers/` (Core Logic & Strategy Interfaces):** Pure Python OOP classes and Abstract Base Classes (`STTProvider`, `AudioEnhancer`, `NoteLensGenerator`, `ClipExtractor`).
4. **`repositories/` & `models/` (Data Access Layer):** Encapsulates all SQLAlchemy database queries (`SessionRepository`, `NoteRepository`, `VectorSearchRepository`).
5. **`workers/` (Async Pipeline Layer):** Background job entrypoints that run outside the HTTP request/response cycle.

```text
lazy-note/                                      # Root Monorepo
├── docker-compose.yml                          # Local Postgres (pgvector+ltree), Redis, API & Worker
├── .env.example                                # Template for all API keys & config variables
├── Makefile                                    # Shortcuts: `make dev`, `make migrate`, `make test`
│
├── backend/                                    # 🐍 PYTHON BACKEND & AI PIPELINE (80% of System)
│   ├── pyproject.toml                          # Dependencies managed via `uv` or `poetry`
│   ├── Dockerfile.api                          # Lightweight image for FastAPI HTTP server
│   ├── Dockerfile.worker                       # Heavy image with FFmpeg, PyTorch, DeepFilterNet, Docling
│   ├── alembic.ini                             # Database migration config
│   ├── migrations/                             # Versioned SQL schema migrations
│   │
│   ├── app/
│   │   ├── main.py                             # FastAPI app factory, CORS, exception handlers
│   │   ├── core/                               # Cross-cutting infrastructure
│   │   │   ├── config.py                       # Pydantic BaseSettings (.env loader)
│   │   │   ├── database.py                     # Async SQLAlchemy engine & get_db() dependency
│   │   │   ├── security.py                     # Supabase JWT verification & current_user injector
│   │   │   ├── storage.py                      # S3/Cloudflare R2 Presigned URL & stream manager
│   │   │   ├── exceptions.py                   # Custom domain exceptions (QuotaExceededError, etc.)
│   │   │   └── logging.py                      # Structlog JSON logger configuration
│   │   │
│   │   ├── models/                             # SQLAlchemy 2.0 ORM Database Tables
│   │   │   ├── base.py                         # TimestampMixin, UUID PrimaryKey base class
│   │   │   ├── user.py                         # UserProfile, SubscriptionPlan, UsageLedger
│   │   │   ├── workspace.py                    # Folder (ltree), WorkspaceItem (Session/Note/Clip)
│   │   │   ├── recording.py                    # RecordingSession, AudioChunkLog, TimelineAnnotation
│   │   │   ├── transcript.py                   # TranscriptRevision, TranscriptSegment (3 scripts)
│   │   │   ├── note.py                         # NoteArtifact, NoteKnowledgeChunk (pgvector+tsvector)
│   │   │   ├── clip.py                         # SharedWebClip (Reels, YT, Blogs, WhatsApp)
│   │   │   └── chat.py                         # ChatThread, ChatMessage, AgentPendingAction
│   │   │
│   │   ├── schemas/                            # Pydantic v2 Request/Response DTOs & LLM Contracts
│   │   │   ├── workspace_schemas.py
│   │   │   ├── recording_schemas.py
│   │   │   ├── transcript_schemas.py
│   │   │   ├── note_lens_schemas.py            # Strict Gemini Structured Output schemas (Quiz, Flashcards)
│   │   │   ├── rag_chat_schemas.py
│   │   │   └── clip_schemas.py
│   │   │
│   │   ├── repositories/                       # Data Access Layer (One Repository per Aggregate)
│   │   │   ├── base_repo.py                    # Generic CRUD Repository[ModelType]
│   │   │   ├── workspace_repo.py               # ltree subtree queries & loose-file queries
│   │   │   ├── recording_repo.py               # Chunk verification & timeline annotation queries
│   │   │   ├── transcript_repo.py              # Multi-revision queries & FTS transcript fallback
│   │   │   ├── note_repo.py                    # Block-level merge & SHA-256 chunk diffing
│   │   │   └── vector_search_repo.py           # Hybrid RRF (pgvector + tsvector) SQL execution
│   │   │
│   │   ├── providers/                          # Pluggable OOP Strategy Implementations
│   │   │   ├── stt/                            # Speech-to-Text Strategy Pattern
│   │   │   │   ├── base.py                     # Abstract class `BaseSTTProvider`
│   │   │   │   ├── sarvam_provider.py          # Sarvam Saaras v4 Batch & Keyterms implementation
│   │   │   │   ├── deepgram_provider.py        # Deepgram Nova-3 implementation
│   │   │   │   ├── whisper_provider.py         # Fallback / Ensemble Whisper implementation
│   │   │   │   └── router.py                   # `STTProviderRouter` factory
│   │   │   ├── dsp/                            # Audio Conditioning Pipeline
│   │   │   │   ├── stitcher.py                 # WebM cluster verifier & FFmpeg Cues remuxer
│   │   │   │   ├── classical_dsp.py            # 85Hz highpass, 50Hz notch, adeclick, speechnorm
│   │   │   │   ├── neural_denoiser.py          # SNR-gated DeepFilterNet3 dual-track processor
│   │   │   │   └── vad_chunker.py              # Silero VAD v6 dynamic window packer & OffsetMap
│   │   │   ├── llm/                            # Gemini 2.5 Multimodal & Prompt Engine
│   │   │   │   ├── gemini_client.py            # Context caching, structured JSON & vision wrapper
│   │   │   │   ├── keyterm_distiller.py        # Pre-ASR 50-keyterm extractor from slides/audio
│   │   │   │   ├── phonetic_repair.py          # Post-ASR timestamp-locked homophone repair
│   │   │   │   └── lens_generators.py          # Strategy classes for Summary, Detailed, Quiz, Deck, MoM
│   │   │   └── extractors/                     # Omnichannel Clipper Extractors
│   │   │       ├── base.py                     # Abstract class `BaseClipExtractor`
│   │   │       ├── youtube_extractor.py        # yt-dlp captions/audio + playlist stub generator
│   │   │       ├── short_video_extractor.py    # IG Reel / YT Short audio + FFmpeg keyframe Vision OCR
│   │   │       └── article_extractor.py        # Jina Reader (r.jina.ai) + Trafilatura fallback
│   │   │
│   │   ├── services/                           # Business Logic Orchestration
│   │   │   ├── workspace_service.py
│   │   │   ├── recording_service.py
│   │   │   ├── transcription_service.py
│   │   │   ├── note_studio_service.py
│   │   │   ├── rag_agent_service.py
│   │   │   ├── clipper_service.py
│   │   │   └── billing_quota_service.py
│   │   │
│   │   ├── workers/                            # Celery / Inngest Durable Background Tasks
│   │   │   ├── celery_app.py
│   │   │   ├── audio_pipeline_tasks.py         # Stitch -> DSP -> VAD -> STT -> Repair -> Default Note
│   │   │   ├── note_indexing_tasks.py          # Contextual chunking -> Embedding -> pgvector upsert
│   │   │   └── clip_ingestion_tasks.py         # URL routing -> Media extraction -> Smart Clip note
│   │   │
│   │   └── api/                                # FastAPI REST & SSE Routers
│   │       └── v1/
│   │           ├── router.py                   # Aggregates all v1 endpoints
│   │           ├── folders.py
│   │           ├── items.py                    # Unified Workspace Items & Loose Files
│   │           ├── recordings.py               # Presigned chunk URLs, pins, photos, finalize
│   │           ├── transcripts.py              # View/switch revisions, trigger heavy re-transcribe
│   │           ├── notes.py                    # Generate lens, block edit sync, export PDF/MD
│   │           ├── search_and_rag.py           # Cmd+K Hybrid Search & SSE Streaming RAG Bot
│   │           ├── clips.py                    # Android Share-Sheet ingestion endpoint
│   │           └── billing.py                  # Quota check & Razorpay/Stripe webhooks
│   │
│   └── tests/                                  # Automated Pytest Suite
│       ├── conftest.py
│       ├── unit/                               # Tests VAD chunker, OffsetMap, prompt builders
│       └── integration/                        # Tests API endpoints & database repositories
│
├── web/                                        # 🌐 NEXT.JS 15 PWA FRONTEND (Laptop + Mobile Browser)
│   ├── src/
│   │   ├── lib/db/dexie-recorder-db.ts         # IndexedDB local chunk queue (`LocalAudioChunk`)
│   │   ├── services/recorder-engine.ts         # MediaRecorder + WakeLock + Serial R2 Uploader
│   │   ├── components/editor/NoteStudio.tsx    # BlockNote / Tiptap editor + [▶ mm:ss] audio pills
│   │   ├── components/drawer/TranscriptVault.tsx # Hidden `⋯` slide-over drawer & script toggle
│   │   └── app/                                # Next.js App Router pages
│
└── mobile-clipper/                             # 📱 EXPO ANDROID SHARE-SHEET APP (Phase 2/3)
    └── src/ShareOverlaySheet.tsx               # <300ms Share Receiver Bottom Sheet (`expo-share-intent`)
```

---

## 4. High-Level System Design (HLD) & End-to-End Component Lifecycles

To see how the frontend, FastAPI server, Cloudflare R2, PostgreSQL, and background workers interact without blocking each other, let's trace the **4 Core System Lifecycles**:

```
====================================================================================================
                  LAZY NOTE PRODUCTION MULTI-TENANT SAAS ARCHITECTURE (HLD)
====================================================================================================

 [Next.js Web/PWA Client]                     [Expo Android Share Overlay]
  • IndexedDB Chunk Queue                      • <300ms `SEND` Intent Receiver
  • WakeLock + Mic Health                      • Captures URL + "Why I Saved This"
  • BlockNote Rich Editor                      • Queues offline -> Syncs to API
         │                                                    │
         ├────────────── 1. Direct Presigned PUT ─────────────┼───────► [Cloudflare R2 Storage]
         │               (30s Opus Chunks, Photos, PDFs)      │          • /raw_chunks/*.webm
         │                                                    │          • /master/*.webm & *.m4a
         ▼                                                    ▼          • /assets/*.webp & *.pdf
  ================ HTTPS / REST / Server-Sent Events (SSE) ================
         │
         ▼
 +-------------------------------------------------------------------------------------------------+
 |                         FASTAPI APPLICATION SERVER (Stateless API Tier)                         |
 |  • Auth Guard (Verifies Supabase JWT)        • Quota Guard (Checks `usage_ledger` minutes)      |
 |  • Workspace & Folder Service (`ltree`)      • Note Studio Service (Block Sync & Lens CRUD)     |
 |  • Hybrid Search & Agentic RAG Streamer      • Presigned URL Generator (`boto3`)                |
 +--------------------------------------+----------------------------------------------------------+
                                        │
            ┌───────────────────────────┴────────────────────────────┐
            │ 2. SQL / Vector Queries (`asyncpg`)                    │ 3. Enqueue Durable Job
            ▼                                                        ▼
 +------------------------------------------+           +------------------------------------------+
 |   SUPABASE POSTGRESQL 16 (Single Truth)  |           |      REDIS BROKER + CELERY / INNGEST     |
 |  • Relational: users, folders, items     |           |  • Queue: `q_audio_pipeline` (High CPU)  |
 |  • Multi-Version: transcript_revisions   |           |  • Queue: `q_llm_synthesis` (High I/O)   |
 |  • Multi-Lens: note_artifacts (JSONB)    |           |  • Queue: `q_rag_indexing` (Fast)        |
 |  • Search: `pgvector` HNSW + `tsvector`  |           |  • Queue: `q_clip_ingestor` (Network)    |
 +------------------------------------------+           +--------------------+---------------------+
                                                                             │
                                                                             ▼
 +-------------------------------------------------------------------------------------------------+
 |                     PYTHON BACKGROUND WORKER FLEET (Heavy Processing Tier)                      |
 |                                                                                                 |
 |  [Worker A: Audio & DSP Engine]              [Worker B: Multimodal AI & RAG Indexer]            |
 |   1. Verify chunks & FFmpeg Stitch            1. Pre-ASR Keyterm Distiller (Gemini Flash-Lite)  |
 |   2. Classical DSP (85Hz HPF, 50Hz Notch)     2. STT Router -> Sarvam Saaras v4 / Deepgram      |
 |   3. SNR Gate -> DeepFilterNet3 (Dual Track)  3. Post-ASR Phonetic Repair & 3-Script Generator  |
 |   4. Silero VAD v6 + `TimestampOffsetMap`     4. Multi-Lens Synthesis (Gemini 2.5 Flash)        |
 |   5. IBM Docling PDF/Slide Layout Parser      5. Contextual Chunker + `pgvector` Embedding Sync |
 +-------------------------------------------------------------------------------------------------+
```

### 4.1 Lifecycle 1: Recording a 90-Minute Lecture to First Generated Note
1. **Session Start (`POST /api/v1/recordings/sessions`):** Client creates a session (either inside a Folder `folder_id` or as a Loose File `folder_id=null`). Backend verifies the user has remaining monthly recording quota, creates a `workspace_items` row (`type='recording_session'`) and a `recording_sessions` row (`status='recording'`), and returns `session_id` + a batch of 20 presigned R2 upload URLs (`chunk_0000` to `chunk_0019`).
2. **Edge Capture & Serial Upload Loop:** Browser `MediaRecorder` slices 30-second Opus chunks (`~120 KB` each), saves each immediately to `IndexedDB`, and uploads them serially to R2. Every time the client uploads a chunk (or batches of 5), it calls `POST /api/v1/recordings/sessions/{id}/chunks/ack`. When URLs run low, the endpoint returns the next batch of 20 presigned URLs.
3. **In-Session Multimodal Capture:** When the student snaps a whiteboard photo at `42:15` (`recording_offset_ms = 2535000`) or taps `📌 Exam Alert`, the client uploads the WebP image to R2 and posts a `TimelineAnnotation` record anchored to `start_ms = 2535000`.
4. **Finalize & Async Handoff (`POST /api/v1/recordings/sessions/{id}/finalize`):** User taps "Stop". Client flushes the final partial chunk `N`, uploads it, and calls `/finalize` with `total_chunks = N + 1` and `default_lens = "detailed_explanation"`. FastAPI sets `status = 'queued'`, enqueues `process_lecture_pipeline_task.delay(session_id)`, and returns `202 Accepted` in `<50ms`.
5. **Durable 7-Step Worker Execution:**
   * **Step 1 (Stitch):** Verifies all `0..N` chunks exist in R2, concatenates them via FFmpeg (`-c copy -cues_to_front 1`), uploads `master_raw.webm` to R2, and sets `master_verified = True` (signaling the client it can delete local `IndexedDB` chunks once transcription completes).
   * **Step 2 (DSP):** Runs FFmpeg linear filters (`highpass=85`, `50Hz notch`, `adeclick`, `speechnorm`). Computes voiced vs. silent SNR. Generates `clean_human.m4a` (`20 dB` DeepFilterNet3) for student headphone playback and `asr_input.wav` (`12 dB` DeepFilterNet3 if `SNR < 15 dB`, else classical only).
   * **Step 3 (VAD & OffsetMap):** Runs **Silero VAD v6**, strips pauses `>2.0s`, creates `compact_asr.wav`, and persists the `TimestampOffsetMap` JSON.
   * **Step 4 (Multimodal Context & Keyterms):** Runs **IBM Docling** on any uploaded PDF handout and **Gemini 2.5 Flash Vision** on whiteboard photos (`timeline_annotations`). Extracts the **Top 50 Domain Keyterms** (or runs the 3x30s Bootstrap Audio sampler if the session is untitled).
   * **Step 5 (Context-Biased STT):** Routes `compact_asr.wav` + `keyterms` to **Sarvam AI Saaras v4 Batch API** (`mode="codemix"`, `with_diarization=True`) or **Deepgram Nova-3**. Maps returned compact timestamps back to wall-clock milliseconds via `TimestampOffsetMap`.
   * **Step 6 (Phonetic Repair & 3-Script Sync):** Passes segments in 10-minute windows to **Gemini 2.5 Flash** along with slide/board vocabulary to fix phonetic homophones and populate `text_codemix`, `text_latin`, and `text_english` in `transcript_segments` under `TranscriptRevision v1 (Default)`.
   * **Step 7 (Default Note Lens & RAG Indexing):** Synthesizes the user's default Note Lens (`detailed_explanation` or `executive_summary`), writes `note_artifacts`, chunks the note using **Anthropic Contextual Retrieval**, embeds via `text-embedding-004`, and inserts into `note_knowledge_chunks`.

---

## 5. Complete Database Design (ERD & Production DDL Schema)

Below is the complete, unified PostgreSQL 16 schema combining Users/Billing, Hierarchical Folders (`ltree`), Loose Files, Multi-Revision Transcripts, Multi-Lens Notes, Hybrid RAG Chunks, Agentic Chat, and Android Shared Clips.

### 5.1 Entity-Relationship Diagram (ERD)
```
[users_profile] 1 ────── * [usage_ledger] (Tracks monthly recording minutes & AI credits)
       │
       ├─────── * [folders] (Self-referencing parent_id + `ltree` materialized path)
       │              │
       │              └── (0..1: NULL = Loose File, UUID = Filed in Folder)
       │              ▼
       ├─────── * [workspace_items] (Unified polymorphic root: 'recording_session' | 'standalone_note' | 'web_clip')
       │              │
       │              ├── 0..1 ──► [recording_sessions] (Master raw R2 key, clean playback R2 key, SNR, duration_ms)
       │              │                  ├── * [audio_chunk_logs] (Tracks 0..N transport chunks & CRC32)
       │              │                  └── * [timeline_annotations] (Time-anchored [start_ms] photos, PDFs, pins)
       │              │
       │              ├── 0..* ──► [transcript_revisions] ("v1 - Fast Hinglish", "v2 - Heavy Exam Verified")
       │              │                  └── * [transcript_segments] (start_ms, end_ms, speaker, codemix, latin, english)
       │              │
       │              ├── 0..1 ──► [shared_web_clips] (Source URL, platform, user_intent_context, extracted_md)
       │              │
       │              └── 1..* ──► [note_artifacts] (Detailed, Summary, MoM, Flashcards JSONB, Quiz JSONB, Editor AST)
       │                                 └── * [note_knowledge_chunks] (Contextual text + pgvector(768) + tsvector)
       │
       └─────── * [chat_threads]
                      └── * [chat_messages]
                                 └── * [agent_pending_actions] (Confirmation cards for Email, Calendar, Research)
```

### 5.2 Complete Production SQL Schema (`migrations/001_initial_schema.sql`)

```sql
-- =================================================================================
-- 0. EXTENSIONS
-- =================================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "ltree";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =================================================================================
-- 1. USERS, SUBSCRIPTIONS & QUOTA LEDGER (Multi-Tenant SaaS Foundation)
-- =================================================================================
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    plan_tier TEXT NOT NULL DEFAULT 'free' CHECK (plan_tier IN ('free', 'student_pro', 'team_pro')),
    preferred_language_mode TEXT NOT NULL DEFAULT 'hinglish' CHECK (preferred_language_mode IN ('hinglish', 'hindi', 'english')),
    preferred_script TEXT NOT NULL DEFAULT 'codemix' CHECK (preferred_script IN ('codemix', 'latin', 'english')),
    monthly_audio_limit_seconds INT NOT NULL DEFAULT 5400, -- 90 mins free tier
    Monthly_audio_used_seconds INT NOT NULL DEFAULT 0,
    billing_cycle_reset_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '30 days'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE usage_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    workspace_item_id UUID,
    operation_type TEXT NOT NULL CHECK (operation_type IN ('stt_fast', 'stt_heavy', 'note_lens_gen', 'clip_extract', 'rag_query')),
    provider_used TEXT NOT NULL,             -- e.g., 'sarvam_saaras_v4', 'gemini_2_5_flash'
    audio_seconds_billed INT DEFAULT 0,
    tokens_billed INT DEFAULT 0,
    estimated_cost_inr NUMERIC(10, 4) NOT NULL DEFAULT 0,
    idempotency_key TEXT UNIQUE NOT NULL,    -- Prevents double-charging on worker retries!
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_usage_ledger_user_date ON usage_ledger (user_id, created_at DESC);

-- =================================================================================
-- 2. FOLDERS (ltree) & UNIFIED WORKSPACE ITEMS (Supports Loose Files!)
-- =================================================================================
CREATE TABLE folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    parent_folder_id UUID REFERENCES folders(id) ON DELETE CASCADE, -- NULL = Root Folder
    name TEXT NOT NULL,
    icon TEXT NOT NULL DEFAULT '📁',
    color_hex TEXT NOT NULL DEFAULT '#4F46E5',
    use_case_type TEXT NOT NULL DEFAULT 'classroom' CHECK (use_case_type IN ('classroom', 'meeting', 'pitch', 'personal')),
    path LTREE NOT NULL,                     -- Materialized path: 'root.f_sem5.f_os.f_unit2'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_folders_path_gist ON folders USING GIST (path);
CREATE INDEX idx_folders_user_parent ON folders (user_id, parent_folder_id);

CREATE TABLE workspace_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    folder_id UUID REFERENCES folders(id) ON DELETE SET NULL, -- NULL = Standalone Loose File!
    folder_path LTREE NOT NULL DEFAULT 'loose'::ltree,
    item_type TEXT NOT NULL CHECK (item_type IN ('recording_session', 'standalone_note', 'web_clip')),
    title TEXT NOT NULL,
    tags TEXT[] NOT NULL DEFAULT '{}',
    is_pinned BOOLEAN NOT NULL DEFAULT false,
    is_archived BOOLEAN NOT NULL DEFAULT false,
    ai_suggested_folder_id UUID REFERENCES folders(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_workspace_items_user_loose ON workspace_items (user_id, created_at DESC) WHERE folder_id IS NULL;
CREATE INDEX idx_workspace_items_path_gist ON workspace_items USING GIST (folder_path);
CREATE INDEX idx_workspace_items_user_type ON workspace_items (user_id, item_type, created_at DESC);

-- =================================================================================
-- 3. RECORDING SESSIONS, CHUNK LOGS & TIMELINE ANNOTATIONS
-- =================================================================================
CREATE TABLE recording_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_item_id UUID UNIQUE NOT NULL REFERENCES workspace_items(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'recording' CHECK (status IN (
        'recording', 'uploading', 'queued', 'stitching', 'dsp_processing', 
        'transcribing', 'synthesizing', 'ready', 'failed'
    )),
    language_mode TEXT NOT NULL DEFAULT 'hinglish',
    expected_total_chunks INT,
    verified_chunks_count INT NOT NULL DEFAULT 0,
    master_raw_r2_key TEXT,                  -- Immutable stitched WebM/Opus source of truth
    clean_playback_r2_key TEXT,              -- DeepFilterNet3 20dB cleaned M4A for human listening
    master_verified BOOLEAN NOT NULL DEFAULT false,
    duration_ms INT NOT NULL DEFAULT 0,
    speech_only_duration_ms INT DEFAULT 0,   -- After Silero VAD silence stripping
    estimated_snr_db REAL,
    vad_offset_map_json JSONB,               -- Bidirectional compact_ms <-> orig_ms map
    active_transcript_revision_id UUID,      -- Points to currently selected transcript revision
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audio_chunk_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES recording_sessions(id) ON DELETE CASCADE,
    seq_no INT NOT NULL,                     -- 0, 1, 2, ... 179
    start_offset_ms INT NOT NULL,
    end_offset_ms INT NOT NULL,
    byte_length INT NOT NULL,
    crc32_checksum TEXT NOT NULL,
    r2_object_key TEXT NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, seq_no)
);

CREATE TABLE timeline_annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES recording_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    start_ms INT NOT NULL,                   -- Anchored to wall-clock ms, NEVER segment_id!
    end_ms INT,
    annotation_type TEXT NOT NULL CHECK (annotation_type IN (
        'whiteboard_photo', 'pdf_handout', 'exam_alert_pin', 'user_bookmark', 'speaker_rename'
    )),
    r2_asset_key TEXT,
    user_note TEXT,
    extracted_vision_markdown TEXT,          -- Gemini 2.5 Flash Vision / IBM Docling output
    extracted_latex TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_timeline_annotations_session_time ON timeline_annotations (session_id, start_ms ASC);

-- =================================================================================
-- 4. MULTI-VERSION NAMED TRANSCRIPTS & 3-SCRIPT SEGMENTS
-- =================================================================================
CREATE TABLE transcript_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES recording_sessions(id) ON DELETE CASCADE,
    workspace_item_id UUID NOT NULL REFERENCES workspace_items(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    revision_number INT NOT NULL,            -- 1, 2, 3...
    display_name TEXT NOT NULL,              -- "v1 - Fast Hinglish (Default)", "v2 - Heavy Exam Verified"
    pipeline_tier TEXT NOT NULL CHECK (pipeline_tier IN ('fast_standard', 'smart_hybrid_retry', 'heavy_full_reprocess')),
    stt_provider TEXT NOT NULL,              -- 'sarvam_saaras_v4', 'deepgram_nova_3', 'whisper_v3_ensemble'
    dsp_config_json JSONB NOT NULL DEFAULT '{}',
    injected_keyterms TEXT[] NOT NULL DEFAULT '{}',
    speaker_map_json JSONB NOT NULL DEFAULT '{"SPEAKER_00": "Main Speaker / Professor"}',
    avg_confidence REAL NOT NULL DEFAULT 1.0,
    word_count INT NOT NULL DEFAULT 0,
    is_default BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, revision_number)
);

CREATE TABLE transcript_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    revision_id UUID NOT NULL REFERENCES transcript_revisions(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES recording_sessions(id) ON DELETE CASCADE,
    seq_index INT NOT NULL,
    speaker_id TEXT NOT NULL,                -- 'SPEAKER_00', 'SPEAKER_01'
    start_ms INT NOT NULL,                   -- Wall-clock ms on master recording
    end_ms INT NOT NULL,
    text_codemix TEXT NOT NULL,              -- Canonical: "अगर हम इस matrix का eigenvalue निकालें..."
    text_latin TEXT NOT NULL,                -- Roman Hinglish: "Agar hum is matrix ka eigenvalue nikalein..."
    text_english TEXT NOT NULL,              -- English: "If we calculate the eigenvalue of this matrix..."
    confidence REAL NOT NULL DEFAULT 1.0,
    is_low_confidence BOOLEAN NOT NULL DEFAULT false,
    fts TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(text_codemix, '') || ' ' || coalesce(text_latin, '') || ' ' || coalesce(text_english, ''))
    ) STORED
);
CREATE INDEX idx_segments_revision_seq ON transcript_segments (revision_id, seq_index ASC);
CREATE INDEX idx_segments_fts_gin ON transcript_segments USING GIN (fts);

-- =================================================================================
-- 5. MULTI-LENS EDITABLE NOTE ARTIFACTS & SHARED WEB CLIPS
-- =================================================================================
CREATE TABLE note_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_item_id UUID NOT NULL REFERENCES workspace_items(id) ON DELETE CASCADE,
    source_revision_id UUID REFERENCES transcript_revisions(id) ON DELETE SET NULL,
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    lens_type TEXT NOT NULL CHECK (lens_type IN (
        'detailed_explanation', 'executive_summary', 'minutes_of_meeting', 
        'flashcard_deck', 'interactive_quiz', 'smart_clip_note', 'custom_freeform'
    )),
    output_language TEXT NOT NULL DEFAULT 'english',
    editor_blocks_json JSONB NOT NULL DEFAULT '[]',    -- BlockNote / Tiptap AST with `is_user_edited` flags
    structured_payload_json JSONB,                     -- Typed JSON for Flashcards, Quizzes & MoM Action Tables
    markdown_mirror TEXT NOT NULL DEFAULT '',          -- Serialized Markdown for RAG indexing & export
    has_user_edits BOOLEAN NOT NULL DEFAULT false,
    version INT NOT NULL DEFAULT 1,
    last_indexed_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_note_artifacts_item ON note_artifacts (workspace_item_id, created_at ASC);

CREATE TABLE shared_web_clips (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_item_id UUID UNIQUE NOT NULL REFERENCES workspace_items(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    source_url TEXT,
    source_platform TEXT NOT NULL CHECK (source_platform IN (
        'youtube_video', 'youtube_playlist', 'instagram_reel', 'youtube_short', 
        'x_post', 'linkedin_post', 'web_article', 'whatsapp_text', 'raw_text'
    )),
    user_intent_context TEXT NOT NULL DEFAULT '',      -- "Why I saved this" (weighted 2.0x in RAG!)
    user_voice_memo_r2_key TEXT,
    extracted_raw_markdown TEXT,
    extracted_metadata_json JSONB DEFAULT '{}',        -- Author, duration, thumbnail, keyframe OCR
    ingestion_status TEXT NOT NULL DEFAULT 'queued' CHECK (ingestion_status IN ('queued', 'extracting', 'ready', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =================================================================================
-- 6. NOTES-FIRST HYBRID RAG KNOWLEDGE CHUNKS & AGENTIC CHAT
-- =================================================================================
CREATE TABLE note_knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    workspace_item_id UUID NOT NULL REFERENCES workspace_items(id) ON DELETE CASCADE,
    note_artifact_id UUID REFERENCES note_artifacts(id) ON DELETE CASCADE,
    folder_path LTREE NOT NULL DEFAULT 'loose'::ltree,
    section_heading_path TEXT NOT NULL,
    chunk_markdown TEXT NOT NULL,
    user_context_prefix TEXT NOT NULL DEFAULT '',
    contextualized_text TEXT NOT NULL,
    source_start_ms INT,
    content_hash TEXT NOT NULL,
    fts TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', coalesce(user_context_prefix, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(section_heading_path, '')), 'B') ||
        setweight(to_tsvector('simple', coalesce(chunk_markdown, '')), 'C')
    ) STORED,
    embedding VECTOR(768) NOT NULL
);
CREATE INDEX idx_nkc_embedding_hnsw ON note_knowledge_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_nkc_fts_gin ON note_knowledge_chunks USING GIN (fts);
CREATE INDEX idx_nkc_folder_gist ON note_knowledge_chunks USING GIST (folder_path);

CREATE TABLE chat_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'New Study Chat',
    scoped_folder_id UUID REFERENCES folders(id) ON DELETE SET NULL,
    scoped_workspace_item_id UUID REFERENCES workspace_items(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
    content_markdown TEXT NOT NULL,
    citations_json JSONB NOT NULL DEFAULT '[]',        -- [{note_id, title, start_ms, used_transcript_fallback}]
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE agent_pending_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    thread_id UUID REFERENCES chat_threads(id) ON DELETE CASCADE,
    source_note_id UUID REFERENCES note_artifacts(id) ON DELETE SET NULL,
    action_type TEXT NOT NULL CHECK (action_type IN ('reminder', 'email_draft', 'calendar_event', 'web_research')),
    action_payload_json JSONB NOT NULL,                -- {recipient, subject, body, due_at, query}
    status TEXT NOT NULL DEFAULT 'pending_approval' CHECK (status IN ('pending_approval', 'approved', 'executed', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 6. Complete REST & SSE API Specification (Every Route & Contract)

In FastAPI, every endpoint is grouped into logical routers under `/api/v1`. Below is the complete API specification table with exact paths, HTTP methods, request bodies, response payloads, and architectural notes:

| Domain | Method & Route | Request Payload / Query Params | Response Payload & Status Code | Architectural Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Folders & Loose Files** | `GET /api/v1/workspace/tree` | `?include_loose_count=true` | `200 OK`: `{ folders: [FolderNode], loose_items_count: 14, recordings_vault_count: 42 }` | Renders the left sidebar folder tree (`ltree`) and badge counts in 1 round-trip. |
| **Folders & Loose Files** | `POST /api/v1/workspace/folders` | `{ name: "Operating Systems", parent_folder_id: "uuid-sem5", icon: "⚙️", use_case_type: "classroom" }` | `201 Created`: `{ id, name, path: "root.sem5.os" }` | Computes `ltree` path from parent and creates folder. |
| **Folders & Loose Files** | `GET /api/v1/workspace/items` | `?folder_id=null` (Loose Files) OR `?folder_id=uuid&recursive=true` | `200 OK`: `{ items: [{ id, title, item_type, tags, suggested_folder, active_lenses: ["detailed_explanation", "flashcard_deck"] }] }` | Fetches either Loose Files (`WHERE folder_id IS NULL`) or folder contents (`WHERE folder_path <@ 'root.sem5'`). |
| **Folders & Loose Files** | `PATCH /api/v1/workspace/items/{item_id}/move` | `{ target_folder_id: "uuid-os" }` (or `null` to make Loose) | `200 OK`: `{ id, folder_id, folder_path }` | Updates `workspace_items.folder_path` AND cascades the new `folder_path` to `note_knowledge_chunks` so scoped RAG stays instant! |
| **Recording Capture** | `POST /api/v1/recordings/sessions` | `{ title: "Lecture 14", folder_id: null, language_mode: "hinglish" }` | `201 Created`: `{ session_id, workspace_item_id, presigned_chunk_urls: [{ seq_no: 0, put_url, r2_key }, ...] }` | Verifies user quota (`monthly_audio_used_seconds < limit`), initializes session, and pre-generates 20 R2 PUT URLs. |
| **Recording Capture** | `POST /api/v1/recordings/sessions/{id}/chunks/ack` | `{ acked_chunks: [{ seq_no: 0, start_ms: 0, end_ms: 30000, bytes: 121040, crc32: "a91f..." }], need_more_urls: true }` | `200 OK`: `{ verified_count: 1, next_presigned_urls: [...] }` | Logs uploaded chunks in `audio_chunk_logs` and issues the next batch of presigned URLs. |
| **Recording Capture** | `POST /api/v1/recordings/sessions/{id}/annotations` | `{ annotation_type: "whiteboard_photo" \| "exam_alert_pin", start_ms: 2535000, user_note: "KCL derivation" }` | `201 Created`: `{ annotation_id, presigned_asset_put_url }` | Anchors live whiteboard photos, uploaded PDFs, or `📌 Exam Alert` pins to exact millisecond offsets. |
| **Recording Capture** | `POST /api/v1/recordings/sessions/{id}/finalize` | `{ expected_total_chunks: 180, duration_ms: 5400000, default_lens: "detailed_explanation" }` | `202 Accepted`: `{ job_id, status: "queued" }` | Enqueues the durable 7-step Celery/Inngest pipeline and returns immediately. |
| **Recording Capture** | `GET /api/v1/recordings/sessions/{id}/events` | *(Server-Sent Events Stream)* | `200 OK (text/event-stream)`: `data: {"stage": "vad_compaction", "progress_pct": 35, "master_verified": true}` | Streams real-time pipeline progress to the UI; once `master_verified: true` & `status: "ready"`, client purges local `IndexedDB` chunks. |
| **Transcripts Vault** | `GET /api/v1/recordings/vault` | `?page=1&limit=20&date_from=2026-10-01` | `200 OK`: `{ recordings: [{ session_id, title, created_at, duration_ms, clean_audio_url, revisions: [{ id, display_name, stt_provider }] }] }` | Powers the chronological **Recordings & Transcripts Vault** tab. |
| **Transcripts (`⋯` Drawer)** | `GET /api/v1/recordings/sessions/{id}/transcripts/{rev_id}` | `?script=codemix` (`codemix` \| `latin` \| `english`) | `200 OK`: `{ revision_id, display_name, speaker_map, segments: [{ seq_index, speaker_id, start_ms, end_ms, text, is_low_confidence }] }` | Powers the hidden `⋯ → View Transcript` slide-over drawer and instant 1-click script switching (`CodeMix / Latin / English`). |
| **Transcripts (`⋯` Drawer)** | `POST /api/v1/recordings/sessions/{id}/transcripts/reprocess` | `{ display_name: "v2 - Heavy Exam Verified", pipeline_tier: "heavy_full_reprocess", stt_provider: "sarvam_saaras_v4", custom_keyterms: ["Eigenvalue", "Cayley-Hamilton"] }` | `202 Accepted`: `{ new_revision_id, status: "queued" }` | Re-runs DSP + STT on the immutable `master_raw_r2_key` to create a new named transcript revision without losing existing notes or pins! |
| **Transcripts (`⋯` Drawer)** | `PATCH /api/v1/recordings/sessions/{id}/speakers` | `{ speaker_id: "SPEAKER_00", new_display_name: "Prof. Kulkarni" }` | `200 OK`: `{ speaker_map: {"SPEAKER_00": "Prof. Kulkarni"} }` | Globally renames a speaker across all segments in `<10ms` via `speaker_map_json`. |
| **Multi-Lens Note Studio** | `POST /api/v1/items/{item_id}/notes/generate` | `{ lens_type: "flashcard_deck" \| "interactive_quiz" \| "detailed_explanation" \| "executive_summary" \| "minutes_of_meeting", source_revision_id: "uuid", output_language: "english" }` | `201 Created`: `{ note_artifact_id, lens_type, editor_blocks_json, structured_payload_json }` | Generates a brand-new Note Lens from any chosen transcript revision in ~5 seconds using Gemini 2.5 Flash. |
| **Multi-Lens Note Studio** | `PATCH /api/v1/notes/{note_id}/blocks` | `{ editor_blocks_json: [...], structured_payload_json: {...}, markdown_mirror: "..." }` | `200 OK`: `{ version: 4, reindex_scheduled: true }` | Saves user edits from BlockNote/Tiptap, preserves `is_user_edited: true` locks, and triggers debounced SHA-256 diff re-indexing for RAG. |
| **Multi-Lens Note Studio** | `POST /api/v1/notes/{note_id}/ai-inline-action` | `{ block_id: "blk_99", action: "expand_slide_derivation", source_start_ms: 2535000, source_end_ms: 2610000 }` | `200 OK (SSE Stream)`: Streams Markdown/LaTeX tokens | Powers inline `/` slash commands inside the editor, grounded strictly in that block's audio timestamp window and slide image. |
| **Search & Agentic RAG** | `GET /api/v1/search/hybrid` | `?q=Banker's+Algorithm+safe+state&folder_id=uuid&only_loose=false` | `200 OK`: `{ results: [{ note_id, workspace_item_id, title, section_heading, snippet_md, source_start_ms, rrf_score }] }` | Powers the instant `<100ms` `Cmd+K` Global Hybrid Search bar. |
| **Search & Agentic RAG** | `POST /api/v1/chat/threads/{thread_id}/messages` | `{ query: "What homework problems did Prof. Sharma assign, and remind me by Friday?", scoped_folder_id: "uuid" }` | `200 OK (SSE Stream)`: Streams answer tokens + `{ citations: [...], pending_actions: [{ id, action_type: "reminder", payload }] }` | Runs **Notes-Primary Hybrid RAG** (with automatic `transcript_segments` FTS fallback if confidence `<0.65`) and emits interactive Agentic Confirmation Cards. |
| **Android Clipper** | `POST /api/v1/clips/ingest` | `{ source_url: "https://instagram.com/reel/...", user_intent_context: "B+ Tree animation for DBMS", folder_id: null }` | `202 Accepted`: `{ workspace_item_id, clip_id, status: "queued" }` | Instant `<100ms` endpoint called by the Android Share Sheet overlay; queues background extraction via `yt-dlp` / Jina Reader / Gemini Vision. |

---

## 7. Low-Level Design (LLD) & Object-Oriented Programming (OOP) Architecture in Python

Since you want to learn how senior software engineers structure real production Python code using **Object-Oriented Programming (OOP)**, **SOLID Principles**, and **Design Patterns**, let's walk through the exact class hierarchy and why each pattern is chosen.

### 7.1 Which OOP Design Patterns Are We Using (And Why)?
1. **Strategy Pattern + Abstract Base Classes (`abc.ABC`):**
   * *Where used:* Speech-to-Text Providers (`SarvamSaarasProvider`, `DeepgramNovaProvider`, `WhisperEnsembleProvider`), Note Lens Generators (`DetailedSlideLensStrategy`, `FlashcardDeckLensStrategy`, `QuizLensStrategy`), and Clip Extractors (`YouTubeExtractor`, `ShortVideoReelExtractor`, `WebArticleExtractor`).
   * *Why:* Your `TranscriptionService` should **never** contain `if provider == "sarvam": ... elif provider == "deepgram": ...` scattered across 10 functions. By programming against an abstract interface `BaseSTTProvider`, you can add a brand-new STT model next year by creating one new class without touching a single line of existing service code (**Open/Closed Principle**).
2. **Factory & Router Pattern:**
   * *Where used:* `STTProviderRouter` and `ClipExtractorRouter`.
   * *Why:* Inspects runtime metadata (such as `language_mode="hinglish"` vs `"english"`, or URL domain `instagram.com` vs `medium.com`) and instantiates the exact Strategy object required.
3. **Chain of Responsibility / Pipeline Pattern:**
   * *Where used:* `AudioConditioningPipeline` (`WebMStitchStep -> ClassicalFFmpegStep -> SNREstimatorStep -> ConditionalDeepFilterNetStep -> SileroVADCompactionStep`).
   * *Why:* Each audio transformation step takes an immutable `AudioPipelineContext` dataclass, performs one focused job (**Single Responsibility Principle**), and passes the updated context to the next step. Furthermore, you can easily skip or swap steps during unit testing!
4. **Repository + Unit of Work Pattern:**
   * *Where used:* `WorkspaceRepository`, `NoteRepository`, `VectorSearchRepository`.
   * *Why:* Decouples your business logic from SQLAlchemy/PostgreSQL details (**Dependency Inversion Principle**).

### 7.2 Complete UML Class Diagram (Core Domain & Services)

```
+---------------------------------------------------------------------------------------------------+
|                                   PRESENTATION LAYER (FastAPI)                                    |
|  RecordingRouter  │  TranscriptRouter  │  NoteStudioRouter  │  RagChatRouter  │  ClipperRouter    |
+-------------------------------------------------+-------------------------------------------------+
                                                  │ (Depends on via FastAPI `Depends()`)
                                                  ▼
+---------------------------------------------------------------------------------------------------+
|                                 APPLICATION SERVICE LAYER (OOP)                                   |
|                                                                                                   |
|  +----------------------------------+         +------------------------------------------------+  |
|  |   TranscriptionPipelineService   |         |               NoteStudioService                |  |
|  +----------------------------------+         +------------------------------------------------+  |
|  | - dsp_pipeline: AudioDSPPipeline |         | - lens_registry: Dict[LensType, BaseLensGen]   |  |
|  | - stt_router: STTProviderRouter  |         | - note_repo: NoteRepository                    |  |
|  | - keyterm_ai: KeytermDistiller   |         | - rag_indexer: ContextualNoteIndexer           |  |
|  | - repair_ai: PhoneticRepairEngine|         +------------------------------------------------+  |
|  +----------------------------------+         | + generate_lens(item_id, lens_type, rev_id)    |  |
|  | + execute_pipeline(session_id)   |         | + update_blocks_preserving_locks(note_id, ast) |  |
|  | + reprocess_revision(req)        |         +------------------------+-----------------------+  |
|  +----------------+-----------------+                                  │                          |
+-------------------|----------------------------------------------------|--------------------------+
                    │                                                    │
         ┌──────────┴──────────┐                                         ▼
         ▼                     ▼                            +------------------------------------+
+------------------+  +------------------------+            |   <<interface>> BaseLensGenerator  |
| AudioDSPPipeline |  | <<interface>>          |            +------------------------------------+
+------------------+  | BaseSTTProvider (ABC)  |            | + build_prompt(ctx) -> str         |
| + stitch_webm()  |  +------------------------+            | + synthesize(ctx) -> LensArtifact  |
| + run_linear()   |  | + transcribe_batch()   |            +-----------------+------------------+
| + run_neural()   |  +-----------+------------+                              △
| + pack_vad()     |              △                                           │
+------------------+     ┌────────┴────────┐                    ┌─────────────┼─────────────┐
                         │                 │                    │             │             │
              +--------------------+ +--------------------+ +--------+ +-------------+ +---------+
              |SarvamSaarasProvider| |DeepgramNovaProvider| |Detailed| |FlashcardDeck| |QuizLens |
              +--------------------+ +--------------------+ |SlideGen| |Generator    | |Generator|
                                                            +--------+ +-------------+ +---------+
```

### 7.3 Production Python Code: Core OOP Classes & Design Patterns

Below is the concrete, production-ready Python code demonstrating how to write these classes cleanly using Python 3.12 type hints, `abc.ABC`, `dataclasses`, and `Pydantic v2`.

#### 7.3.1 The Strategy & Factory Pattern for Speech-to-Text (`app/providers/stt/`)

```python
# app/providers/stt/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass(frozen=True)
class RawDiarizedSegment:
    """Immutable Value Object returned by any STT Provider before offset mapping."""
    seq_index: int
    speaker_id: str          # e.g., "SPEAKER_00"
    compact_start_ms: int    # Timestamp in the VAD-compacted audio file
    compact_end_ms: int
    raw_text: str            # Provider output (e.g., Code-mixed Hinglish or English)
    confidence: float = 1.0

@dataclass(frozen=True)
class STTTranscriptionRequest:
    """Input contract for any STT Provider."""
    session_id: str
    audio_file_path: str
    language_mode: str       # 'hinglish' | 'hindi' | 'english'
    output_mode: str         # 'codemix' | 'translit' | 'transcribe'
    keyterms: List[str] = field(default_factory=list)
    enable_diarization: bool = True
    num_speakers_hint: Optional[int] = None

@dataclass(frozen=True)
class STTTranscriptionResult:
    provider_name: str
    model_version: str
    segments: List[RawDiarizedSegment]
    billed_audio_seconds: int
    avg_confidence: float

class BaseSTTProvider(ABC):
    """
    Abstract Base Class (Interface) for all Speech-to-Text engines.
    Enforces the Strategy Pattern: every STT engine must implement `transcribe()`.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        pass

    @abstractmethod
    async def transcribe(self, request: STTTranscriptionRequest) -> STTTranscriptionResult:
        """Transcribes a VAD-compacted audio file with speaker diarization and keyterm biasing."""
        pass
```

```python
# app/providers/stt/sarvam_provider.py
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from app.providers.stt.base import (
    BaseSTTProvider, STTTranscriptionRequest, STTTranscriptionResult, RawDiarizedSegment
)
from app.core.config import settings

class SarvamSaarasProvider(BaseSTTProvider):
    """
    Concrete Strategy for Sarvam AI Saaras v4 Batch API.
    Purpose-built for Indian Classroom Hinglish (`mode='codemix'`) with up to 50 domain keyterms.
    """

    @property
    def provider_id(self) -> str:
        return "sarvam_saaras_v4"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
    async def transcribe(self, request: STTTranscriptionRequest) -> STTTranscriptionResult:
        # Enforce Sarvam Saaras v4 constraint: max 50 keyterms, <=64 chars each
        sanitized_keyterms = [ term[:64].strip() for term in request.keyterms[:50] if term.strip() ]

        async with httpx.AsyncClient(timeout=300.0) as client:
            # 1. Submit Batch Job with Keyterm Prompting & Speaker Diarization
            with open(request.audio_file_path, "rb") as audio_stream:
                files = {"file": ("compact_lecture.wav", audio_stream, "audio/wav")}
                data = {
                    "model": "saaras:v4",
                    "mode": request.output_mode,  # 'codemix' keeps Hindi in Devanagari & tech terms in Latin
                    "with_diarization": str(request.enable_diarization).lower(),
                    "with_timestamps": "true",
                    "prompt": ", ".join(sanitized_keyterms)
                }
                response = await client.post(
                    "https://api.sarvam.ai/speech-to-text-translate/batch",
                    headers={"api-subscription-key": settings.SARVAM_API_KEY},
                    data=data,
                    files=files
                )
                response.raise_for_status()
                payload = response.json()

        raw_segments = []
        confidences = []
        for idx, entry in enumerate(payload.get("diarized_transcript", {}).get("entries", [])):
            conf = float(entry.get("confidence", 0.92))
            confidences.append(conf)
            raw_segments.append(
                RawDiarizedSegment(
                    seq_index=idx,
                    speaker_id=f"SPEAKER_{int(entry.get('speaker_id', 0)):02d}",
                    compact_start_ms=int(float(entry["start_time_seconds"]) * 1000),
                    compact_end_ms=int(float(entry["end_time_seconds"]) * 1000),
                    raw_text=entry["transcript"].strip(),
                    confidence=conf
                )
            )

        avg_conf = sum(confidences) / len(confidences) if confidences else 1.0
        billed_sec = int(payload.get("duration_seconds", 0))

        return STTTranscriptionResult(
            provider_name=self.provider_id,
            model_version="saaras:v4",
            segments=raw_segments,
            billed_audio_seconds=billed_sec,
            avg_confidence=avg_conf
        )
```

```python
# app/providers/stt/router.py
from app.providers.stt.base import BaseSTTProvider
from app.providers.stt.sarvam_provider import SarvamSaarasProvider
from app.providers.stt.deepgram_provider import DeepgramNovaProvider

class STTProviderRouter:
    """
    Factory & Router Pattern: Selects the optimal STT engine based on language mode
    or explicit user override during a multi-transcript re-run.
    """

    def __init__(self, sarvam: SarvamSaarasProvider, deepgram: DeepgramNovaProvider):
        self._providers: dict[str, BaseSTTProvider] = {
            sarvam.provider_id: sarvam,
            deepgram.provider_id: deepgram,
        }
        self._sarvam = sarvam
        self._deepgram = deepgram

    def resolve_provider(self, language_mode: str, explicit_provider_id: str | None = None) -> BaseSTTProvider:
        if explicit_provider_id and explicit_provider_id in self._providers:
            return self._providers[explicit_provider_id]
        
        # Default routing rule: Hinglish/Hindi -> Sarvam Saaras v4; Pure English -> Deepgram Nova-3
        if language_mode in ("hinglish", "hindi"):
            return self._sarvam
        return self._deepgram
```

#### 7.3.2 Multi-Lens Note Studio Strategy & Block-Locking Merge (`app/services/note_studio_service.py`)

Here is how we solve the **"AI Regeneration Overwrites User Edits"** problem using clean OOP and Block AST merging:

```python
# app/services/note_studio_service.py
import hashlib
from typing import Any, Dict, List
from uuid import UUID
from app.repositories.note_repo import NoteRepository
from app.repositories.transcript_repo import TranscriptRepository
from app.providers.llm.lens_generators import LensGeneratorRegistry
from app.workers.note_indexing_tasks import index_note_for_rag_task

class NoteStudioService:
    """
    Application Service managing Multi-Lens Note creation, Block-level user edit locking,
    and incremental RAG re-indexing.
    """

    def __init__(
        self,
        note_repo: NoteRepository,
        transcript_repo: TranscriptRepository,
        lens_registry: LensGeneratorRegistry,
    ):
        self._note_repo = note_repo
        self._transcript_repo = transcript_repo
        self._lens_registry = lens_registry

    async def generate_or_regenerate_lens(
        self,
        user_id: UUID,
        workspace_item_id: UUID,
        lens_type: str,
        source_revision_id: UUID,
        output_language: str = "english",
        existing_note_id: UUID | None = None,
    ) -> Dict[str, Any]:
        # 1. Fetch the chosen Transcript Revision + Time-Synced Whiteboard Photos & PDFs
        revision_context = await self._transcript_repo.get_full_multimodal_context(
            revision_id=source_revision_id
        )

        # 2. Resolve the Strategy Class for the requested Lens (Summary, Detailed, Flashcards, Quiz, MoM)
        generator_strategy = self._lens_registry.get_strategy(lens_type)
        generated_output = await generator_strategy.synthesize(
            context=revision_context,
            output_language=output_language
        )

        # 3. If regenerating an existing note where the user made manual edits, preserve locked blocks!
        if existing_note_id:
            existing_note = await self._note_repo.get_by_id(existing_note_id, user_id=user_id)
            if existing_note and existing_note.has_user_edits:
                merged_blocks = self._merge_preserving_user_edited_blocks(
                    old_blocks=existing_note.editor_blocks_json,
                    new_ai_blocks=generated_output.editor_blocks_json
                )
                generated_output.editor_blocks_json = merged_blocks

        # 4. Save Artifact & Enqueue Async Contextual RAG Indexing
        saved_note = await self._note_repo.upsert_note_artifact(
            user_id=user_id,
            workspace_item_id=workspace_item_id,
            source_revision_id=source_revision_id,
            lens_type=lens_type,
            title=generated_output.title,
            editor_blocks_json=generated_output.editor_blocks_json,
            structured_payload_json=generated_output.structured_payload_json,
            markdown_mirror=generated_output.markdown_mirror,
            existing_note_id=existing_note_id,
        )

        # Trigger background RAG chunk diffing & pgvector embedding
        index_note_for_rag_task.delay(str(saved_note.id))
        return saved_note.to_dict()

    @staticmethod
    def _merge_preserving_user_edited_blocks(
        old_blocks: List[Dict[str, Any]],
        new_ai_blocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Smart Block Merge:
        Any block in `old_blocks` where `attrs.is_user_edited == True` is preserved
        at its corresponding temporal anchor (`source_start_ms`), never overwritten by AI!
        """
        user_locked_blocks = [
            b for b in old_blocks if b.get("attrs", {}).get("is_user_edited") is True
        ]
        if not user_locked_blocks:
            return new_ai_blocks

        merged: List[Dict[str, Any]] = list(new_ai_blocks)
        for locked in user_locked_blocks:
            locked_ms = locked.get("attrs", {}).get("source_start_ms", 0)
            # Find the closest matching timestamp position in the new AI block list
            insert_idx = len(merged)
            for idx, candidate in enumerate(merged):
                cand_ms = candidate.get("attrs", {}).get("source_start_ms", 0)
                if cand_ms >= locked_ms:
                    insert_idx = idx
                    break
            merged.insert(insert_idx, locked)

        return merged

    async def save_user_block_edits(
        self,
        user_id: UUID,
        note_id: UUID,
        editor_blocks_json: List[Dict[str, Any]],
        structured_payload_json: Dict[str, Any] | None,
        markdown_mirror: str,
    ) -> Dict[str, Any]:
        """
        Called on 10-second idle debounce when a user edits their note, flashcards, or quiz.
        Only triggers RAG re-embedding if the SHA-256 content hash actually changed!
        """
        new_hash = hashlib.sha256(markdown_mirror.encode("utf-8")).hexdigest()
        note = await self._note_repo.get_by_id(note_id, user_id=user_id)

        updated_note = await self._note_repo.update_content(
            note_id=note_id,
            user_id=user_id,
            editor_blocks_json=editor_blocks_json,
            structured_payload_json=structured_payload_json,
            markdown_mirror=markdown_mirror,
            has_user_edits=True,
        )

        reindex_triggered = False
        if note.last_indexed_hash != new_hash:
            index_note_for_rag_task.delay(str(note_id))
            reindex_triggered = True

        return {"note_id": str(updated_note.id), "version": updated_note.version, "reindex_scheduled": reindex_triggered}
```

#### 7.3.3 The Two-Tier "Notes-Primary, Transcript-Fallback" Agentic RAG Service (`app/services/rag_agent_service.py`)

```python
# app/services/rag_agent_service.py
from typing import AsyncGenerator, Dict, Any, List
from uuid import UUID
from app.repositories.vector_search_repo import VectorSearchRepository
from app.repositories.transcript_repo import TranscriptRepository
from app.providers.llm.gemini_client import GeminiClient

class RagAgentService:
    """
    Implements Two-Tier Contextual Retrieval:
    - Tier 1 (Primary): Hybrid Search (pgvector + tsvector + RRF) strictly over curated Notes & Saved Clips.
    - Tier 2 (Fallback): If Tier 1 RRF confidence < threshold or LLM requests granular verbatim check,
      searches backing `transcript_segments` via Postgres Full-Text Search.
    - Emits structured Agentic Confirmation Cards (`agent_pending_actions`) for Reminders/Emails.
    """

    RRF_CONFIDENCE_THRESHOLD = 0.012  # Below this RRF score, auto-augment with Transcript FTS

    def __init__(
        self,
        vector_repo: VectorSearchRepository,
        transcript_repo: TranscriptRepository,
        gemini: GeminiClient,
    ):
        self._vector_repo = vector_repo
        self._transcript_repo = transcript_repo
        self._gemini = gemini

    async def answer_query_stream(
        self,
        user_id: UUID,
        thread_id: UUID,
        query: str,
        scoped_folder_path: str | None = None,
        only_loose_files: bool = False,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        # 1. Embed the user query using Gemini text-embedding-004 (768 dims)
        query_embedding = await self._gemini.embed_text(query)

        # 2. Tier 1: Search ONLY Curated Notes & Clips via Hybrid RRF SQL
        note_chunks = await self._vector_repo.hybrid_search_notes(
            user_id=user_id,
            query_text=query,
            query_embedding=query_embedding,
            folder_scope=scoped_folder_path,
            only_loose_files=only_loose_files,
            match_count=8,
        )

        # 3. Check if we need Tier 2 Backing Transcript Fallback (for granular room numbers, exact quotes, etc.)
        backing_transcript_hits = []
        top_score = note_chunks[0].rrf_score if note_chunks else 0.0
        if not note_chunks or top_score < self.RRF_CONFIDENCE_THRESHOLD:
            candidate_item_ids = [c.workspace_item_id for c in note_chunks] if note_chunks else None
            backing_transcript_hits = await self._transcript_repo.search_backing_transcripts_fts(
                user_id=user_id,
                query_text=query,
                workspace_item_ids=candidate_item_ids,
                limit=5,
            )

        # 4. Stream grounded answer + function-calling tool detection (Reminders / Email Drafts)
        async for event in self._gemini.stream_rag_response_with_tools(
            query=query,
            note_chunks=note_chunks,
            transcript_fallbacks=backing_transcript_hits,
        ):
            yield event
```

---

## 8. Production SaaS Engineering Checklist (How to Make It Real-User Ready)

Since your goal is a **fully production-ready SaaS application that real users can use**, writing the features is only 70% of the job. The remaining 30% is what separates a college hackathon project from a reliable SaaS:

### 8.1 Multi-Tenant Security (Row-Level Security + Application Guards)
* **Never Trust Client IDs:** Every single repository method (`get_by_id(note_id, user_id=current_user.id)`) **must** include `WHERE user_id = :user_id`.
* **Defense-in-Depth with Supabase RLS:** Enable PostgreSQL Row-Level Security (`ALTER TABLE workspace_items ENABLE ROW LEVEL SECURITY;`) so even if a bug exists in a query, User A can mathematically never read User B's lecture notes or audio files.
* **Private Cloudflare R2 Bucket:** Never make your R2 bucket public! Store all audio chunks, master recordings, and whiteboard photos in a private bucket and serve playback/download links exclusively via short-lived **Presigned GET URLs (`ExpiresIn=3600` seconds)** generated by FastAPI after verifying `session.user_id == current_user.id`.

### 8.2 Idempotency & Quota Protection (How Not to Go Bankrupt)
* **Pre-Flight Quota Check + Atomic Reservation:** Before starting a 90-minute transcription job on Sarvam AI (`~₹50`), check `user_profiles.monthly_audio_used_seconds + compact_duration_seconds <= monthly_audio_limit_seconds`.
* **Idempotency Keys on Every Worker Step:** What if your Celery worker finishes calling Sarvam AI (`₹50` billed), and then crashes 2 seconds later due to a database timeout? When Celery retries the task, a naive worker will call Sarvam AI **a second time** (`₹100` billed!).
  * *The Fix:* Cache the raw STT response JSON in Cloudflare R2 (`/sessions/{id}/cache/stt_raw_rev1.json`) keyed by `idempotency_key = f"stt:{session_id}:rev:{rev_no}"`. When the worker retries, it checks if `stt_raw_rev1.json` already exists in R2—if yes, it skips the paid API call and resumes directly from Step 6!

### 8.3 Deployment Topology & Monthly Infrastructure Cost at Launch (0 to 500 Users)

You can deploy the entire production stack for **under ₹1,500/month (`~$18/mo`) fixed overhead** before variable per-minute STT usage:

| Component | Recommended Production Host | Launch Tier Cost | Why This Setup Works |
| :--- | :--- | :--- | :--- |
| **Next.js 15 PWA Frontend** | **Vercel** (or Cloudflare Pages) | **$0 / mo** (Hobby/Free Tier) | Global Edge CDN, instant Git deploys, automatic HTTPS for `MediaRecorder` & `WakeLock`. |
| **FastAPI Web Server + Celery Worker** | **Railway.app** or **Render** (Docker Compose / 2 Services from 1 GitHub Repo) | **~$10–$15 / mo** (`2 vCPU / 4 GB RAM` worker container) | Runs both `Dockerfile.api` and `Dockerfile.worker` (with FFmpeg, Silero VAD, Docling, and DeepFilterNet3 pre-installed). |
| **PostgreSQL 16 + `pgvector` + `ltree` + Auth** | **Supabase** | **$0 / mo** (Free Tier up to 500 MB DB / 50,000 MAU; $25/mo Pro later) | Includes Auth, `pgvector`, `ltree`, and automated backups out of the box. |
| **Redis Queue & Rate Limiter** | **Upstash Redis** | **$0 / mo** (Free Tier up to 10,000 commands/day) | Serverless Redis for Celery/Inngest job queuing and SSE progress pub/sub. |
| **Audio & Asset Object Storage** | **Cloudflare R2** | **$0 / mo** (First 10 GB/mo free = ~450 hours of 32kbps Opus lectures; **$0 egress**) | Zero bandwidth charges when students replay lectures on their phones. |

---

## 9. Your Step-by-Step Build Order (First 30 Days Execution Plan)

To avoid feeling overwhelmed as a first-time builder, build the codebase in **5 vertical slices**:

1. **Slice 1 (Days 1–5): The Skeleton & Database Foundation**
   * Initialize the `backend/` folder with `uv init`, install `fastapi`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, and `pydantic-settings`.
   * Run the SQL migration in Section 5.2 on your Supabase project.
   * Build `folders.py` and `items.py` endpoints and test creating a Folder (`ltree`) and a Loose File in FastAPI's built-in `/docs` UI!
2. **Slice 2 (Days 6–12): The Audio Stitcher, VAD & Sarvam/Deepgram STT Pipeline**
   * Write the `AudioDSPPipeline` class (`stitch_webm` $\rightarrow$ `run_classical_classroom_dsp` $\rightarrow$ `pack_vad_utterances_into_semantic_chunks`).
   * Implement `SarvamSaarasProvider` and `DeepgramNovaProvider` behind `BaseSTTProvider`.
   * Test with a real 30-minute Hinglish lecture audio file from your phone and verify that `transcript_segments` populate with `text_codemix`, `text_latin`, and `text_english`!
3. **Slice 3 (Days 13–18): The Multi-Lens Note Studio (`Gemini 2.5 Flash`)**
   * Implement `LensGeneratorRegistry` with the Pydantic `response_schema` classes for *Detailed Slide Explanation*, *Executive Summary*, *Flashcards*, *Quiz*, and *Minutes of Meeting*.
   * Wire up `NoteStudioService` with the `_merge_preserving_user_edited_blocks` logic.
4. **Slice 4 (Days 19–24): Contextual Hybrid RAG & `Cmd+K` Search**
   * Implement the Markdown-AST chunker that prepends `[Folder Breadcrumb | Note Title | Section Heading]` to each note chunk, embeds via `text-embedding-004`, and calls the `hybrid_search_notes` PostgreSQL RRF function.
   * Add the backing transcript FTS fallback tool.
5. **Slice 5 (Days 25–30): Next.js PWA Recorder + BlockNote Studio UI**
   * Build the `Dexie.js` local chunk queue + `MediaRecorder` serial R2 uploader + WakeLock blackout screen.
   * Embed the **BlockNote** rich editor connected to `PATCH /api/v1/notes/{id}/blocks`, add the `[▶ mm:ss]` audio jump pills, and tuck the transcript viewer neatly into the `⋯` slide-over drawer!
