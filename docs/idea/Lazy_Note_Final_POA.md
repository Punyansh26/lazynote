# Lazy Note --- Final Plan of Action (POA)

**Version:** 1.0\
**Date:** 27 October 2026\
**Scope:** Phase 1: reliable lecture capture through a saved,
timestamped transcript\
**Product direction:** Build the reliable audio foundation for a later
notes-first learning workspace.

------------------------------------------------------------------------

## 1. Executive decision

Lazy Note should be built in this order:

1.  **Never lose recoverable audio.**
2.  **Make uploads resumable and verifiable.**
3.  **Produce a useful transcript reliably.**
4.  **Measure quality on real Indian classroom recordings.**
5.  **Add context-aware correction and transcript versions.**
6.  **Build notes, search and learning tools on top of this
    foundation.**

The immutable original recording is the source of truth. Filtered audio,
transcripts, translations, notes and embeddings are derived artifacts. A
new processing run must never overwrite the original audio or silently
destroy an earlier transcript or user edit.

The initial release should favor a small, observable, recoverable
pipeline over a large collection of speculative optimizations.

## 2. Product and engineering goals

### Phase 1 goals

-   Record long lectures, targeting 60--120 minutes.
-   Continue recording when the network is unavailable, within the
    tested limitations of the chosen browser/device.
-   Persist captured audio locally and upload it with retry and
    integrity verification.
-   Reconstruct and validate a complete master recording in durable
    cloud storage.
-   Transcribe English, Hindi and code-switched Hinglish, with technical
    vocabulary handled as well as the selected provider allows.
-   Save timestamped transcript segments and expose processing status
    and errors.
-   Support future re-transcription without replacing the master
    recording or breaking timeline annotations.
-   Measure quality, reliability, latency and cost on representative
    audio.

### Not Phase 1 requirements

-   Building or training a custom ASR model.
-   Aggressive denoising on every recording.
-   A custom VAD compaction system before the chosen provider is
    evaluated.
-   Automatic ensemble transcription for every lecture.
-   Three fully synchronized transcript scripts before the canonical
    transcript works.
-   Full note generation, RAG, flashcards, quizzes, or the Android
    share-sheet clipper.
-   A promise of uninterrupted browser recording when the OS kills or
    suspends the page.

## 3. Working technology baseline

  -----------------------------------------------------------------------
  Layer                   Working choice          Decision note
  ----------------------- ----------------------- -----------------------
  Frontend                Existing Next.js 15 App Preserve the current
                          Router, TypeScript,     app; do not restart it.
                          Tailwind, PWA           

  Local recording queue   IndexedDB via Dexie;    Persist every emitted
                          evaluate OPFS for       blob and its manifest
                          larger binary storage   before considering it
                                                  safely queued. Test
                                                  browser quotas and
                                                  lifecycle behavior.

  Backend API             Existing FastAPI /      Continue from the
                          Python 3.12             working upload
                                                  endpoint.

  Validation              Pydantic v2             Validate all session,
                                                  chunk and finalization
                                                  requests.

  ORM / DB                SQLAlchemy 2 async +    Use migrations; inspect
                          asyncpg + Supabase      and test current files
                          PostgreSQL              before assuming
                                                  integration is
                                                  complete.

  Schema migrations       Alembic                 Every schema change
                                                  should be reproducible.

  Media storage           Cloudflare R2 using     Browser uploads
                          server-created          directly to object
                          presigned URLs          storage; secrets stay
                                                  server-side.

  Background jobs         Choose one durable      Do not run long
                          workflow after a small  transcription inside a
                          spike: Inngest or       request handler. Pick
                          Celery + Redis          based on retries,
                                                  operational complexity
                                                  and deployment.

  ASR                     Provider adapter with   Benchmark Sarvam and at
                          one primary long-form   least one credible
                          provider                alternative on the same
                                                  sample set before
                                                  locking the provider.
                                                  Verify current API
                                                  limits, language modes,
                                                  diarization, keyterms
                                                  and pricing from
                                                  official docs.

  Audio utilities         FFmpeg; optional VAD /  Start with inspection
                          enhancement behind      and conservative
                          feature flags           conditioning. Add more
                                                  only when measurements
                                                  justify it.

  Authentication          Supabase Auth with      Enforce ownership on
                          server-side JWT         every session, asset
                          verification            and job operation.
  -----------------------------------------------------------------------

**Do not change the agreed stack casually.** If a decision is still
pending, run a bounded evaluation and document the result before
committing to it.

## 4. End-to-end target workflow

1.  User taps **Record**.
2.  Browser requests microphone permission, selects the intended input,
    and displays a live signal-health indicator.
3.  A session ID is created locally so recording can begin even if the
    network is unavailable.
4.  The capture API emits ordered transport blobs. The app writes each
    blob to local storage with sequence number, byte length,
    timestamps/offsets, MIME type and checksum.
5.  Upload runs independently from capture. The client requests
    short-lived presigned URLs and uploads pending chunks with bounded
    concurrency, retry/backoff and idempotent object keys.
6.  User taps **Stop**. The recorder flushes its final data. The client
    records the final expected chunk count and attempts to upload all
    pending chunks.
7.  The backend finalization operation verifies the manifest and object
    presence. Missing chunks keep the session recoverable; they must not
    trigger transcription.
8.  A worker assembles/remuxes the complete source stream and validates
    duration, decodability, expected chunk coverage and checksum/size
    metadata. The immutable master is stored in R2.
9.  Only after master verification does the session enter the
    transcription queue.
10. The worker inspects the audio and records technical metadata. A
    conservative ASR-ready derivative may be created if testing supports
    it.
11. Context is prepared from available title, subject, vocabulary and
    optional course materials. Missing context must not block
    transcription.
12. The primary long-form ASR provider generates timestamped segments.
    Provider errors are recorded and retried according to policy.
13. Output validation checks schema, monotonic timestamps, duration
    bounds, empty/repeated output and transcript coverage. Uncertain
    segments can be flagged for later review.
14. Raw ASR output is saved as an immutable transcript revision.
15. Optional terminology repair/script conversion creates a separate
    derived revision or synchronized text view. It must not silently
    overwrite raw output.
16. The client shows the transcript and its status. Local chunks can be
    cleaned up only after the server confirms a verified master and the
    configured retention policy permits deletion.

## 5. Architecture principles

### 5.1 Separate capture chunks from transcription windows

Transport chunks exist for crash recovery and network retries. They are
not automatically valid standalone audio files and should not be sent
individually to an ASR service unless the format and provider explicitly
support that use.

Transcription windows are an independent processing decision. Prefer the
provider's long-form API initially. Introduce custom VAD segmentation
only after a benchmark shows a real need.

### 5.2 Preserve original audio

-   Store original audio as immutable source media.
-   Store normalized/filtered/enhanced audio as derived assets with
    pipeline version and configuration.
-   Never replace the master with a denoised version.
-   Verify the stored master is readable before client cleanup.
-   Define retention, user deletion and failed-upload recovery policies
    explicitly.

### 5.3 Treat browser recording as best-effort, not infallible

PWA recording behavior varies across iOS Safari, Android browsers,
device vendors, battery-saving modes and storage pressure. Wake Lock or
media-session behavior may help in some environments but cannot
guarantee recording survives OS termination.

Test target devices. Warn users about unsupported/at-risk states,
storage limits, microphone changes and Bluetooth headset inputs. If
reliable background recording becomes a hard product requirement,
evaluate a native Android capture client separately.

### 5.4 Use measured DSP, not assumptions

Initial pipeline: - Inspect codec, duration, sample rate, channel count,
clipping, silence and approximate noise conditions. - Produce a
compatible ASR input only when required. - Test conservative
high-pass/normalization against the original. - Keep neural enhancement
optional and gated by measured benefit. - Preserve the original waveform
for playback and future processing. - Compare word error rate (WER),
character error rate (CER), technical-term accuracy and subjective
playback quality. Human-playback cleanup and ASR preprocessing may need
different settings.

### 5.5 Use context without hallucinating

Start with: - session title and user-supplied subject/course; - optional
keyterms/tags; - optional PDF/slide text when available.

A context distiller or LLM can be added later to rank a bounded keyterm
list. Do not make slides/OCR or an LLM call a prerequisite for basic
transcription. Any post-ASR correction must preserve raw output,
timestamps and speaker IDs and must avoid replacing acoustically
uncertain words solely because a term seems plausible.

### 5.6 Version transcripts immutably

Each transcription run records its provider/model, request options,
language/script mode, context terms, audio asset, DSP configuration,
timestamps, status, errors, and cost/latency where available. New runs
create new revisions.

Anchor user bookmarks, photos and notes to `session_id` plus absolute
`start_ms` / `end_ms` on the original timeline, not solely to a
transient transcript segment ID.

## 6. Data model: minimum useful version

Use migrations and adapt existing models after inspecting the current
repository. Avoid implementing every future table at once.

### Initial entities

**RecordingSession** - `id`, `user_id`, `title` - `status`,
`created_at`, `started_at`, `ended_at` - `duration_ms`, `mime_type` -
`expected_chunk_count` - `master_audio_asset_id` (nullable until
verified) - `active_transcript_revision_id` (nullable)

**AudioChunk** - `id`, `session_id`, `sequence_number` - `object_key`,
`byte_length`, `checksum` - `start_offset_ms`, `end_offset_ms` -
`upload/verification status`, `created_at` - unique constraint on
`(session_id, sequence_number)`

**AudioAsset** - `id`, `session_id`, `kind` (`original_master`,
`normalized`, `enhanced_playback`, etc.) - `object_key`, `content_type`,
`byte_length`, `checksum`, `duration_ms` - `pipeline_version`,
`created_at`

**ProcessingJob** - `id`, `session_id`, `job_type`, `status`,
`attempt_count` - `stage`, `progress` (optional), `last_error_code`,
`last_error_message` - `started_at`, `finished_at`, `created_at` -
idempotency key / deduplication constraint

**TranscriptRevision** - `id`, `session_id`, `revision_number`,
`parent_revision_id` (optional) - `kind` (`raw_asr`, `corrected`,
`script_conversion`, `translation`, `human_edited`) - `provider`,
`model`, `configuration_json`, `context_json` - `status`, `created_at`,
`completed_at` - unique constraint on `(session_id, revision_number)`

**TranscriptSegment** - `id`, `revision_id`, `sequence_number` -
`start_ms`, `end_ms`, `speaker_label` (nullable) - `raw_text` or `text`,
optional confidence and quality flags - optional derived
script/translation fields only if they have clear versioning semantics

Add folders, embeddings, note artifacts, transcript full-text indexes
and annotation entities when the product requires them. Do not store
audio bytes in PostgreSQL.

## 7. State machines and recovery

### Session lifecycle

Suggested high-level states:
`recording → upload_pending → uploaded → queued → processing → completed`

Terminal/exception states: `failed` and `cancelled`, with a defined
retry or recovery path.

Keep detailed processing stage and retry metadata separate from the
high-level session state.

### Required invariants

-   A chunk sequence number is unique within a session.
-   Retrying the same upload/finalization request is idempotent.
-   No transcription job starts until the master asset is verified.
-   A partial upload is recoverable and never marked complete.
-   A failed processing stage can resume from a durable checkpoint where
    safe.
-   A transcript revision is not marked ready until its segments pass
    validation and are committed.
-   A new revision never overwrites a prior revision.
-   The original master is not deleted as a side effect of
    transcription.
-   All object access and status operations are authorized for the
    session owner.

### Retry policy

Use bounded exponential backoff with jitter for transient
network/5xx/provider errors. Distinguish retryable failures (timeout,
rate limit, temporary provider outage) from permanent failures
(unsupported media, invalid request, unauthorized access). Persist
attempt count and last error. Avoid infinite retries and avoid
duplicating billable jobs.

## 8. API plan

Keep API contracts small and explicit. Names can be aligned with the
current router conventions.

1.  `POST /api/v1/sessions` --- create session and return ID.
2.  `POST /api/v1/sessions/{id}/chunks/presign` --- authorize upload and
    return short-lived upload URL(s).
3.  `POST /api/v1/sessions/{id}/chunks/complete` --- acknowledge
    uploaded chunk metadata for server verification.
4.  `POST /api/v1/sessions/{id}/finalize` --- submit expected chunk
    count and finalize intent; idempotent.
5.  `GET /api/v1/sessions/{id}` --- session state and recovery details.
6.  `GET /api/v1/sessions/{id}/processing-status` --- job stage,
    retryable error and transcript status.
7.  `GET /api/v1/sessions/{id}/transcripts` --- list transcript
    revisions.
8.  `GET /api/v1/transcript-revisions/{revision_id}` --- paginated or
    complete segments as appropriate.

The current `POST /api/v1/uploads` endpoint is already a useful working
milestone. Do not delete or rewrite it prematurely. Decide whether it
remains a simple-upload path for development/small files or becomes a
compatibility endpoint while the session/chunk workflow is built. Add
authentication and ownership checks before exposing user data in a
multi-user deployment.

## 9. Implementation phases and exit criteria

### Phase 0 --- Repository and contract audit

Tasks: - Inspect the actual backend/frontend tree, current upload route,
DB session/model files, environment variables and tests. - Run the
backend and existing tests from `backend/`. - Verify environment
configuration and ensure secrets are not committed. - Write down the
exact current state; do not assume proposed code exists just because it
appears in an architecture document.

Exit criteria: - App starts reproducibly. - Existing upload route
behavior is documented and covered by tests. - Database integration
status is known.

### Phase 1 --- Persist upload metadata in PostgreSQL

Tasks: - Finish async SQLAlchemy engine/session setup. - Configure
`DATABASE_URL` safely via environment variables. - Complete the Upload
model and Pydantic response schema. - Add Alembic and apply a migration
to a development database. - Save upload metadata transactionally;
handle the case where file storage succeeds but DB persistence fails,
and vice versa. - Add ownership and lifecycle fields when session
workflow begins.

Exit criteria: - Valid upload returns metadata and persists it in
PostgreSQL. - Invalid extension, empty file, oversize file, write error
and DB error are handled predictably. - Tests do not require production
secrets.

### Phase 2 --- Recording session and local persistence

Tasks: - Create a session before or while recording, including
offline-generated ID support. - Implement browser microphone permission,
start/stop lifecycle, visible recording state and elapsed duration. -
Persist every emitted blob and manifest locally. - Handle final partial
chunk, refresh/crash recovery and duplicate events. - Inspect browser
support for MIME types; use capability detection rather than assuming
WebM everywhere. - Add storage quota checks and a clear user warning. -
Test mic selection, Bluetooth input warnings and screen-lock behavior.

Exit criteria: - A test recording can be stopped/recovered without
losing already-persisted chunks. - Recording does not depend on network
availability. - Unsupported browser behavior is detected and
communicated.

### Phase 3 --- Resumable chunk upload and master verification

Tasks: - Add R2 bucket configuration and server-generated short-lived
presigned URLs. - Use deterministic object keys and ordered chunk
sequence numbers. - Add checksum/size metadata and bounded
retry/backoff. - Implement server-side manifest verification and
idempotent finalization. - Assemble/remux using a format-aware
procedure; validate with FFmpeg/ffprobe. - Verify master duration,
decodability and object checksum metadata. - Keep local chunks until
server verification is confirmed.

Exit criteria: - Simulated offline periods, duplicate uploads and retry
storms do not corrupt a session. - Missing/reordered chunks prevent
finalization and can be retried. - The verified master can be played and
its duration is plausible. - Local cleanup occurs only after verified
master confirmation and policy checks.

### Phase 4 --- Durable processing worker

Tasks: - Select Inngest or Celery + Redis using a short proof of
concept. - Implement job creation, deduplication, retry policy and
persisted stage transitions. - Move all long-running audio processing
out of HTTP request handlers. - Add structured logs and useful error
codes. - Make worker restarts safe.

Exit criteria: - A worker restart does not lose a queued job. -
Duplicate finalize requests do not create duplicate billable
transcription runs. - Failed stages can be retried without redoing
verified stages unnecessarily.

### Phase 5 --- Baseline transcription

Tasks: - Create a provider adapter with normalized request/response
schemas. - Benchmark Sarvam and at least one alternative on the same
representative recordings; verify current provider documentation and
pricing. - Begin with the provider's long-form capability if it handles
the target duration and required language modes. - Persist raw
timestamped segments and provider metadata. - Validate timestamps,
ordering, empty/repetitive output, duration bounds and failure cases. -
Store raw provider response for debugging where policy and provider
terms permit.

Exit criteria: - A complete verified master produces a saved transcript
revision. - Provider failures are visible and retryable. - Transcript
timestamps map to the original recording timeline. - A user can open and
read the transcript after a page reload.

### Phase 6 --- Audio quality and contextual vocabulary

Tasks: - Create a small, consented evaluation set with human-verified
transcripts. - Compare original audio against conservative FFmpeg
conditioning. - Add VAD or neural enhancement only if it measurably
improves accuracy or usability. - Add title/subject/keyterm context; add
slide/PDF extraction as an optional enhancement. - Evaluate
code-switching, technical-term accuracy and script quality. - Add
cautious terminology repair as a separate derived revision.

Exit criteria: - Changes are backed by measured improvements on the
evaluation set. - No pipeline overwrites original audio or raw ASR. -
Unsupported or uncertain corrections remain reviewable.

### Phase 7 --- Versioning, quality flags and reprocessing

Tasks: - Add immutable transcript revisions and active-revision
selection. - Record model, provider, DSP config, context and job
metadata for every run. - Anchor notes/bookmarks to original session
time ranges. - Add user-triggered re-transcription and a limited
selective retry only if confidence/quality signals are trustworthy. -
Add revision comparison and safe switching.

Exit criteria: - Reprocessing creates a new revision. - Switching
revisions preserves timeline annotations. - Raw ASR and
corrected/script-converted views remain distinguishable.

### Phase 8 --- Product hardening and pilot

Tasks: - Run a pilot on actual target phones, browsers and classroom
conditions. - Add privacy/consent messaging, deletion controls and
retention behavior. - Test permissions revoked, low storage, network
loss, server outage, provider outage, app refresh, worker restart and
malformed audio. - Add operational dashboards and alerting for stuck
jobs and upload failures. - Document known PWA background-recording
limitations.

Exit criteria: - The pilot meets agreed reliability and quality
targets. - Failure recovery is understandable to users. - No known
data-loss path is left without a documented mitigation or warning.

### Phase 9 --- Phase 2 learning workspace

Only after Phase 1 is reliable: - Notes-first interface with transcript
hidden by default but accessible. - Editable note artifacts and
regeneration that preserves user edits. - Folders/subfolders and loose
files. - Summaries, detailed notes, flashcards, quizzes and meeting
minutes. - Search and notes-primary retrieval with transcript
fallback. - Future Android share-sheet capture.

## 10. Evaluation plan and initial release gates

Build a small, representative evaluation set before tuning DSP or
choosing a permanent ASR provider. Obtain appropriate consent and remove
sensitive material where required.

Include: - English, Hindi and intra-sentence Hinglish. - Technical
lectures across more than one subject. - Distant professor speech,
student questions, fan/AC noise, reverberation and long pauses. -
Different phone models, microphone positions and recording durations. -
Clear and difficult examples, with human-verified reference transcripts.

Measure: - **WER / CER:** overall transcription errors. -
**Technical-term accuracy:** names, acronyms, equations and domain
terms. - **Code-switching quality:** language/script behavior within
sentences. - **Timestamp error:** alignment against the original
timeline. - **Capture/upload recovery:** completed and recovered
sessions under fault injection. - **Processing latency:** median and
tail latency after upload completion. - **Cost per recorded hour:**
include STT, LLM, storage, egress and worker costs. - **User
usefulness:** whether students can follow, search and revisit the
lecture.

Set numeric targets only after a baseline run; do not promote unverified
vendor or architecture-document numbers into guarantees.

## 11. Key risks and mitigations

  -----------------------------------------------------------------------
  Risk                                Mitigation
  ----------------------------------- -----------------------------------
  Browser or OS kills recording       Device/browser test matrix, local
                                      persistence, visible warning,
                                      recovery tests; native capture if
                                      strict background guarantees become
                                      necessary.

  Browser emits non-independent media Treat blobs as transport pieces;
  blobs                               reconstruct and validate the stream
                                      before decoding.

  Local storage eviction or full disk Persistent-storage request where
                                      supported, quota checks, storage
                                      warnings, conservative cleanup
                                      policy.

  Weak network or repeated upload     Retry queue, checksums, idempotent
  failures                            keys, bounded concurrency, offline
                                      tests.

  Audio enhancement reduces ASR       Compare against raw audio, gate
  accuracy                            optional enhancement, preserve
                                      source.

  VAD compaction breaks timestamps    Avoid initially; if added, test a
                                      bidirectional offset map and verify
                                      mapped segments on known audio.

  Code-mixed words are normalized     Preserve raw output, benchmark
  incorrectly                         script modes, use contextual terms
                                      cautiously, keep derived
                                      corrections reversible.

  LLM "repairs" acoustically          Restrict repair scope; never let
  uncertain speech incorrectly        plausibility alone override audio
                                      evidence.

  Provider pricing/API behavior       Provider adapter, current-doc
  changes                             verification, usage monitoring and
                                      alternative-provider benchmark.

  Duplicate jobs or billable retries  Idempotency keys, unique
                                      constraints, durable checkpoints
                                      and bounded retries.

  Transcript revision breaks notes    Anchor annotations to session time
                                      ranges, not segment IDs.

  Private audio or transcript leaks   Authentication, owner-scoped
                                      authorization, short-lived URLs,
                                      secret management and explicit
                                      retention/deletion rules.
  -----------------------------------------------------------------------

## 12. Claims that must be treated as hypotheses

The architecture draft includes precise claims about processing time,
model speed, word-error improvements, cost per lecture, provider limits,
keyterm caps and device market behavior. These values can change and may
depend heavily on setup and benchmark methodology.

Before using them as engineering commitments: 1. Check the provider's
current official documentation. 2. Run a reproducible benchmark on the
same audio and configuration. 3. Record hardware, duration, audio
format, model/version, settings and retries. 4. Compare both quality and
cost. 5. Document the measured result and date.

Specific cautions: - Upload time depends on sustained throughput; 21.6
MB cannot upload in 15 seconds at 4 KB/s. - A VAD model's ability to
detect speech does not guarantee it correctly identifies all relevant
classroom speech or coughs. - Removing silence may reduce billable audio
duration for some pricing models, but only if the provider charges by
submitted duration and the transformation preserves timing/quality
requirements. - Global diarization, language mode, batch duration limits
and keyterm constraints must be verified for the exact
provider/model/API version selected. - PWA background recording cannot
be guaranteed by Wake Lock or Media Session alone.

## 13. Immediate next actions

Work in this order and complete each checkpoint before moving on:

1.  **Audit the current repository.** Confirm which DB/session/model
    changes actually exist and run the current upload tests.
2.  **Finish upload metadata persistence in Supabase PostgreSQL.** Add
    migration and failure-path tests.
3.  **Define the recording session and chunk manifest contracts.** Agree
    on states, sequence numbers, checksums, offsets and idempotency.
4.  **Implement browser-local persistence.** Do not begin with cloud DSP
    or transcription.
5.  **Add R2 presigned chunk uploads and master verification.** Test
    offline, retry, duplicate and missing-chunk scenarios.
6.  **Choose and implement a durable worker.** Keep long jobs out of
    FastAPI request handlers.
7.  **Benchmark long-form ASR providers.** Use the same consented audio
    sample set and reference transcript.
8.  **Save the first raw timestamped transcript revision.** Make the
    end-to-end vertical slice work before optimizing it.
9.  **Measure DSP/context improvements.** Add only improvements
    supported by the evaluation set.
10. **Pilot on real target devices.** Fix data-loss, reliability and
    usability issues before building Phase 2.

## 14. Definition of Phase 1 done

Phase 1 is ready for a limited pilot when a user can:

-   Start a lecture recording and see that capture is active.
-   Continue recording during a network outage within the tested
    device/browser constraints.
-   Stop and recover the recording after transient failures.
-   Upload and verify every chunk without silently accepting gaps.
-   Retrieve a durable, playable master recording.
-   Receive a timestamped transcript with visible processing status and
    actionable errors.
-   Re-run transcription into a new revision without losing the original
    audio or existing annotations.
-   Understand what is stored, how long it is retained, and how to
    delete it.

**Final guiding principle:** Build for recoverability first, measurable
transcription quality second, and intelligent learning features third.
Do not add pipeline complexity until a real recording, benchmark or user
need justifies it.
