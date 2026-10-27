# Lazy Note — Backend Agent Guidelines & Architecture Rules

This file defines the engineering guidelines, architectural invariants, and specifications for all agents and developers working in `backend/`.

---

## 1. Stack & Tooling Invariants

- **Runtime & Package Manager:** Python 3.12+ managed via `uv` (`pyproject.toml` and `uv.lock`). Use `uv add` or `uv run` to manage packages and run servers.
- **Web Framework:** FastAPI with Pydantic v2 schemas for all request/response models.
- **Database & ORM:** PostgreSQL (Supabase) via SQLAlchemy 2.0 (asyncio) and `asyncpg`.
- **Migrations:** Alembic. Every schema modification must be created as a reproducible migration in `alembic/versions/`.
- **Primary Package Location:** `backend/src/lazynote/`. All application code lives inside this package.

---

## 2. Core Audio & Processing Pipeline Architecture

The immediate backend milestone implements the focused **Audio $\rightarrow$ DSP & VAD $\rightarrow$ Transcript $\rightarrow$ Notes** pipeline. Image, camera snapshot, and slide PDF context uploads are deferred to subsequent phases.

### 2.1 Separation of Transport Slices vs. Semantic Segments
- **Client Transport Chunks & Edge Persistence:** The recording client captures audio in 30-second slices (`MediaRecorder.start(30000)`) and buffers them locally in `IndexedDB` (`Dexie.js`) or OPFS. Chunks are uploaded sequentially with `session_id`, `sequence_number`, `start_ms`, `end_ms`, and byte length. The client retains the recorded audio locally for offline playback and user reuse—backend verification must never require or assume the client deletes its offline audio cache.
- **Storage Abstraction:** Audio chunks and assets are managed via a storage interface (`StorageService`) with a local disk driver (`/uploads/`) for rapid development and a presigned Cloudflare R2 / S3 driver for production.
- **Master Remuxing:** WebM/Opus chunks only have the EBML container header in `chunk_0`. Chunks must never be sent individually to STT or DSP. Upon session finalization, FFmpeg concatenates all received chunks into an immutable, playable master audio file.

### 2.2 Classical DSP Filter Chain (Pre-ASR)
Before speech detection and transcription, the assembled master audio is processed through a lossless-for-ASR classical filter chain using FFmpeg:
- **Highpass Filter (`85Hz`, 2 poles):** Strips low-frequency AC rumble, desk bumps, and classroom background HVAC.
- **Notch Equalizers (`50Hz` and `100Hz`, Q=10):** Neutralizes Indian power-grid electrical hum and ground loops.
- **De-clicking (`adeclick`):** Removes transient pen clicks, desk taps, and microphone handling noise.
- **Volume Leveling (`speechnorm`):** Balances far-field lecturer volume and limits loud transient coughs.
- **Output Standard:** 16 kHz, 16-bit mono PCM WAV (`pcm_s16le`).

### 2.3 Silero VAD & Timestamp Offset Mapping
- **Silero VAD v6:** Scans the DSP-conditioned audio to detect active speech intervals `[(start_ms, end_ms), ...]`.
- **Silence Pruning:** Non-speech pauses $> 2.5\text{ seconds}$ (such as blackboard writing or attendance) are identified to eliminate STT silence hallucination loops and reduce transcription billable duration by 20–35%.
- **`TimestampOffsetMap`:** A non-destructive lookup structure maps every active speech segment from the compacted audio timeline back to exact wall-clock milliseconds on the original recording.

### 2.4 Lecture-Only Processing (No Diarization Overhead)

Phase 1 is built **strictly for classroom lectures**. Because classroom lectures are single-lecturer events for note-taking purposes, **speaker identification and diarization are completely omitted from Phase 1**:
1. **Silence-Trimmed 10-Minute Slicing:** The segmenter seeks natural breath pauses ($\ge 400\text{ ms}$) in the audio near 10-minute marks (e.g. between 9:30 and 10:15) to slice audio cleanly without cutting words.
2. **Pure Timestamped STT:** 10-minute segments are dispatched to Sarvam AI Saaras v4 (`mode="codemix"`, without diarization). Word and sentence timestamps are projected back to absolute lecture milliseconds:
   $$\text{lecture\_ms} = \text{slice\_start\_ms} + \text{segment\_start\_ms}$$
3. **No Cross-Chunk Boundary Issues:** Because diarization is omitted, there is zero risk of speaker label fragmentation between chunks.
4. **Structured Note Generation:** The continuous timestamped transcript stream is sent to Gemini 2.5 Flash to generate structured, topic-sectioned study notes with KaTeX formulas and review questions.


---

## 3. Directory Layout & Organization

Maintain the following package layout under `backend/src/lazynote/`:

```
backend/src/lazynote/
├── __init__.py
├── main.py                  # FastAPI app factory, middleware, CORS, lifespan
├── config.py                # Pydantic BaseSettings (Supabase, R2, AI keys)
├── database/
│   ├── __init__.py
│   ├── session.py           # SQLAlchemy async engine and get_db session dependency
│   └── models/
│       ├── __init__.py
│       ├── session.py       # RecordingSession model (use_case_type, status, etc.)
│       ├── chunk.py         # AudioChunk model (seq_no, offsets, status, file path)
│       └── transcript.py    # TranscriptSegment and NoteArtifact models
├── schemas/
│   ├── __init__.py
│   ├── session.py           # Session create/response schemas
│   ├── chunk.py             # Chunk upload/ack schemas
│   └── transcript.py        # Transcript and note schemas
├── router/
│   ├── __init__.py
│   ├── health.py            # /health check
│   ├── sessions.py          # /api/v1/sessions (create, finalize, status)
│   ├── chunks.py            # /api/v1/sessions/{id}/chunks
│   └── notes.py             # /api/v1/sessions/{id}/notes
└── services/
    ├── __init__.py
    ├── storage.py           # StorageService (LocalDiskStorage / CloudflareR2Storage)
    ├── audio_dsp.py         # FFmpeg remuxing and classical DSP filter chain
    ├── vad.py               # Silero VAD & TimestampOffsetMap generator
    ├── stt.py               # Speech-to-text adapters (Sarvam Saaras v4, Deepgram)
    └── notes.py             # LLM prompt & note generation service
```

---

## 4. Development & Execution Rules

1. **Non-Blocking Processing:** Never run FFmpeg remuxing, DSP, VAD, or STT calls inside the synchronous HTTP request-response cycle. Use background tasks or worker jobs.
2. **Source of Truth:** The raw uploaded chunks and reconstructed master recording are immutable. Filtered, compacted, or normalized audio files are derived assets and must never overwrite the original audio.
3. **Error Resilience:** Individual chunk upload failures or missing chunks must leave the session in a recoverable state (`status: "uploading"` or `"failed_verification"`), preventing transcription until all chunks are verified.
4. **Environment Variables:** All secrets and credentials (`POSTGRES_CONNECTION_STRING`, R2 keys, API keys) must be loaded from environment variables or `.env` via `config.py`. Never hardcode secrets.
