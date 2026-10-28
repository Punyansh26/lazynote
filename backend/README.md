# Lazy Note — Backend API & Processing Engine

The Python backend service for **Lazy Note**, built with FastAPI, SQLAlchemy 2.0 (async), and Alembic. It powers reliable classroom lecture recording, audio conditioning, speech transcription, and AI note generation.

---

## 1. Phase 1 Architecture: Audio-to-Notes Pipeline

Phase 1 focuses **strictly on classroom lecture processing**, with speaker diarization removed to keep transcription fast, cost-effective, and free of multi-chunk identity fragmentation.

```
30s Client Audio Blobs (Buffered & Retained in IndexedDB/OPFS for Offline Playback)
       │
       ▼
FastAPI Chunk Ingestion (/uploads/ or Cloudflare R2)
       │
       ▼ (Finalize Session)
FFmpeg Master Remuxing (Concatenates blobs into decodable master)
       │
       ▼
Classical Classroom DSP (85Hz highpass, 50/100Hz notch, declick, speechnorm -> 16kHz mono WAV)
       │
       ▼
Silero VAD v6 (Prunes >2.5s silence, generates TimestampOffsetMap)
       │
       ▼
Silence-Bounded Slicing (Slices audio at natural pauses near 10-minute marks)
       │
       ▼
Sarvam AI Saaras v4 STT (Hinglish/Indian English, with_diarization=False)
       │
       ▼
Chronological Timestamped Transcript Segments in PostgreSQL
       │
       ▼
Google Gemini 2.5 Flash (Generates structured study notes with KaTeX math)
```

---

## 2. Tech Stack

- **Framework:** FastAPI with Pydantic v2
- **Database:** Supabase PostgreSQL via SQLAlchemy 2.0 (`asyncio`) + `asyncpg`
- **Migrations:** Alembic
- **Package Manager:** `uv`
- **Audio DSP:** FFmpeg (classical filter chain) + Silero VAD v6 (ONNX/PyTorch)
- **Speech-to-Text:** Sarvam AI Saaras v4 API
- **AI Notes:** Google Gemini 2.5 Flash

---

## 3. Directory Layout

```
backend/
├── alembic/                 # Alembic async database migrations
│   ├── versions/            # Migration scripts (e.g. 0001_initial_schema.py)
│   └── env.py               # Async migration runner connected to lazynote models
├── alembic.ini              # Alembic configuration
├── src/lazynote/
│   ├── __init__.py          # Package metadata & version
│   ├── main.py              # FastAPI application factory, lifespan & CORS
│   ├── config.py            # Pydantic BaseSettings & async database URL normalization
│   ├── database/
│   │   ├── __init__.py      # Base, engine, async_session_factory, get_db export
│   │   ├── session.py       # Async SQLAlchemy engine & get_db dependency
│   │   └── models/          # RecordingSession, AudioChunk, TranscriptSegment, NoteArtifact
│   ├── schemas/             # Pydantic request/response schemas (session, chunk, transcript)
│   ├── router/              # API endpoints (/health, /api/v1/sessions, /chunks, /notes)
│   └── services/            # Storage, AudioDSP, Silero VAD, STT, and Notes services
├── tests/
│   ├── conftest.py          # Pytest async fixtures
│   ├── unit/                # Unit test suite (test_config.py)
│   ├── integration/         # Integration test suite (test_health.py)
│   └── sample/              # Sample lecture audio for pipeline testing
├── scripts/                 # Standalone utility & pipeline verification scripts
├── notebooks/               # Exploratory audio analysis and DSP experimentation
├── uploads/                 # Local chunk and master audio storage (.gitignore protected)
├── pyproject.toml           # Project dependencies & build config managed via uv
├── requirements.txt         # Pinned requirements mirror
├── .env.example             # Documented environment template
└── AGENTS.md                # Engineering invariants & architecture rules for agents
```

---

## 4. Development Commands

```bash
# Install dependencies
uv sync

# Run database migrations
uv run alembic upgrade head

# Run tests
uv run pytest

# Start development server
uv run uvicorn lazynote.main:app --reload --port 8000
# or
uv run lazynote
```
