# Lazy Note — Phase 1 Rolling-Window Pipeline Notebook: Session Record

> Context document for future agents/developers. Records **what** was done, **how**, **why**, and **what was saved where**, for the session that created `backend/notebooks/pipelinephase1.ipynb`.
> Date of session: 2026-10-28 / 2026-10-29.

---

## 1. Conversation timeline (3 user requests)

| # | User request (paraphrased) | Outcome |
| --- | --- | --- |
| 1 | Create `pipelinephase1.ipynb` using `samplepipeline.ipynb` as the base, but use the bigger real lecture `backend/notebooks/sample/Gnn part 1.m4a`, save results in the `result` folder with an organised file structure, and implement an **Asynchronous Rolling 10-Minute Macro-Batch Pipeline** (a long architecture review pasted by the user), documenting everything in markdown in detail because it will be used as context for agents. | New notebook created (26 cells, no outputs). |
| 2 | "I want to see the output result": comment out the parts that delete things and adjust accordingly. | All deletion code commented out; flags flipped; checks adapted. |
| 3 | Save this conversation in detail (what/how/why/results) to `docs/convo`. | This file. |

Project rule in force (`AGENTS.md`): write only what the user asks, **do not execute code/notebooks/tests unless told**. Consequently the notebook was **never run** by the assistant; see §8.

---

## 2. Input material

### 2.1 Base notebook `backend/notebooks/samplepipeline.ipynb`
Single-pass, synchronous pipeline on a 60 s clip of `conv1.m4a`:
1. Optional live browser recorder widget (5 s chunks, AGC/NS/AEC off) or sample clip.
2. Byte-level slicing of a WebM/Opus stream (40 KB chunks, only chunk 0 has EBML header).
3. `SimulatedUploadServer` (SHA-256 + sequence check).
4. Master remux: binary concatenation + `ffmpeg -c copy -fflags +genpts -err_detect ignore_err` → `master_raw.webm`.
5. Linear STT DSP: `highpass=85`, notches 50/100 Hz, `adeclick`, `speechnorm`, `lowpass=7600`, output 16 kHz mono PCM.
6. Silero VAD compaction (bridge gaps < 2.5 s, 250 ms pad), `TimestampOffsetMap`, ~10 min slices with `slice_compacted_start_ms`.
7. Simulated STT + timestamp projection, plots/metrics.
The file is ~3 MB because audio previews/widget output are embedded; it was read via a small script extracting cell sources rather than raw JSON.

### 2.2 Lecture audio
`backend/notebooks/sample/Gnn part 1.m4a` (~59.7 MB; other samples: `conv1.m4a`, `ai for autonomous sample.m4a`). Its duration is probed at notebook runtime (`ffprobe`); it was not probed during the session.

### 2.3 The user's architecture review (design spec)
Proposed **asynchronous rolling pipeline**: once 20 contiguous 30 s chunks (10 min) are verified on the server, a background job processes them while recording continues; on **Stop** only the tail remains (~66 % of a 15-min lecture, ~88 % of a 90-min lecture already transcribed). Four traps with fixes:

1. **Headerless WebM clusters** — only `chunk_0000` has the EBML header; a window starting at chunk 20 fails with `Invalid data found` unless the header is cached/prepended and chunks are not flushed early.
2. **Mid-word cut at the 10:00 boundary** — cut at the last natural breath pause (≥ 400 ms) from Silero VAD, keep the remainder as `carryover_tail.wav`, prepend it to the next window.
3. **Diarization across independent calls** — speaker IDs flip between windows; use `diarization=False` for pure lecture flow.
4. **Flush rules / immutable master** — client keeps a local master and purges the upload queue only after `master_verified`; server flushes heavy intermediates after each window, transport chunks only after `master_raw.webm` is verified, never the master (needed for re-transcription).

Also specified: 30 s chunks preferred over 15 s (half the HTTP/DB overhead, `(max_contiguous_seq+1) % 20 == 0` trigger), idempotency key `stt_win:{session}:{start}_{end}`, per-session sequential execution (Window 2 needs Window 1's carryover and `seq_index`), global wall-clock offset projection, state fields `last_processed_chunk_seq` and `carryover_start_ms`. The review ended asking whether to implement the rolling trigger + carryover state machine next — the notebook is that implementation in sandbox form.

---

## 3. Deliverable: `backend/notebooks/pipelinephase1.ipynb`

26 cells (13 markdown, 13 code), kernel metadata copied from the base notebook (`python3`, 3.14). Created by a **throw-away generator script** (kept in the assistant scratch dir, not in the repo) that wrote the ipynb JSON; every code cell was syntax-checked with `ast.parse`. The notebook was **not executed**.

### 3.1 What changed relative to the base
| Aspect | Base | Phase 1 notebook |
| --- | --- | --- |
| Audio | 60 s of `conv1.m4a` | full `Gnn part 1.m4a` (`LIMIT_MINUTES` optional for dry runs) |
| Chunks | 40 KB raw byte slices | **30 s cluster-aligned** WebM/Opus chunks |
| Trigger | once after Stop | rolling every 20 contiguous verified chunks + final window on Stop |
| Slicing | ~10 min after first speech boundary | window cut at last pause ≥ 400 ms + carryover tail |
| Offset map | one global | one per window, anchored to cluster Timecode |
| Flushing | none | policy implemented (later disabled by request, §6) |
| Live widget | present | removed (the lecture file is the simulated mic) |
| Output dir | `result/pipeline_test/` | `result/pipeline_phase1/` (numbered subfolders) |

### 3.2 Cell map
1. Title/overview markdown (why rolling, architecture diagram, four traps table, correctness rules).
2. Setup/config markdown + code (constants, result folder tree, `preview_audio`, `dir_size_bytes`).
3. Source lecture markdown + code (ffprobe, expected chunk/window plan, 30 s preview).
4. Transport markdown + code (EBML walker, MediaRecorder-like stream encode, cluster-aligned chunking, manifest).
5. Trap 1 markdown + demo code (decode chunks 20..24 with/without cached header).
6. Building blocks markdown + code (WAV helpers, DSP chain, Silero loader, `choose_cut`, `merge_and_pad`, `OffsetSegment`, `TimestampOffsetMap` + self-test, VAD load).
7. STT provider markdown + code (`SimulatedSTT`, `DeepgramSTT`, `build_stt_provider`).
8. Session state machine markdown + code (`ChunkRecord`, `RollingSession`).
9. Replay/run markdown + code (simulated client loop, Stop, finalize).
10. Report markdown + code (cut table, latency vs synchronous baseline).
11. Verification markdown + code (assert-style checklist).
12. Analysis markdown + code (timeline plot, VAD savings, pause plot, raw vs DSP spectrograms, metrics).
13. Export markdown + code (transcript files, summary JSON, result tree print).
14. Implementation contract markdown (endpoints, worker task, flushing policy, failure handling, open items).

---

## 4. How it works (design + rationale)

### 4.1 Config (production defaults unless marked notebook-only)
`CHUNK_SEC=30`, `WINDOW_CHUNKS=20`, `OPUS_BITRATE=32k`, `MIN_BREATH_PAUSE_MS=400`, `CARRYOVER_SEARCH_SEC=30`, `MAX_SILENCE_MS=2500`, `SPEECH_PAD_MS=250`, `VAD_THRESHOLD=0.45`, `MIN_SPEECH_MS=250`, `SESSION_ID=sess_gnn_part1`, `STT_PROVIDER` from env (`simulated` default). Notebook-only: `LIMIT_MINUTES`, `REPLAY_SPEEDUP=20.0` (uploads replayed 20× real time: one chunk per 1.5 s; rolling only helps if window processing time < window recording time).

### 4.2 Simulated client
- FFmpeg encodes the whole lecture once to mono 48 kHz Opus 32 kbps WebM with `-cluster_time_limit 30000` (~30 s clusters, like Chrome's recorder).
- A custom **EBML walker** (`scan_webm_clusters`) finds top-level `Cluster` elements (ID `0x1F43B675`) with start/end bytes and first-child `Timecode` (ID `0xE7`). Chunk *i* = bytes `[cluster_i.start, cluster_{i+1}.start)`; chunk 0 also owns the header; trailing `Cues` dropped (a live recorder never writes them).
- *Why a custom walker instead of fixed byte slices:* the base notebook's byte slices cut mid-cluster, so a window starting at an arbitrary chunk could not be decoded even with the header. Cluster alignment mirrors real `MediaRecorder` output and gives exact per-chunk wall-clock starts.
- Assumptions: `TimecodeScale = 1 ms`; known-size clusters (unknown-size raises explicit error).
- Client keeps an **upload queue** (`01_client/upload_queue/`) and a **local master** (`local_master_opfs.webm`, appended per chunk).

### 4.3 Server ingestion (`RollingSession.ack_chunk`)
Verify SHA-256 → parse cluster Timecode (→ `ChunkRecord.start_ms`) → store → cache header at seq 0 (`webm_header.bin`) → advance `max_contiguous_seq` → while `max_contiguous_seq - last_enqueued_seq >= 20` enqueue a window. Windows are **chunk-count based** (exact, testable trigger) but their real start comes from the Timecode, never from `20×30 s` arithmetic.

### 4.4 Window worker (`_process_window_impl`)
1. **Stitch** `header + chunks` (header omitted when `start_seq == 0`), SHA-verify each chunk, **decode + DSP in one FFmpeg call** (`-err_detect ignore_err`).
2. **Prepend carryover** (already conditioned; not re-filtered).
3. `combined_global_start_ms = window_first_chunk_Timecode − carryover_ms` → anchors to the exact cluster time, so drift cannot accumulate across windows (the carryover's own stored start is only informational; join drift is logged as `carryover_join_drift_ms`).
4. **One Silero pass** with fine settings (`min_silence 400 ms`, `pad 0`) used for both cut selection and compaction.
5. **`choose_cut`**: walk gaps (incl. trailing silence) from the end; pick the **midpoint of the last gap ≥ 400 ms whose midpoint lies in the last 30 s**; fallback = quietest 50 ms frame of the last 5 s (`cut_reason=forced_low_energy_frame`, logged risk). Final window: cut = end.
6. **`merge_and_pad`**: only stamps before the cut; bridge gaps < 2.5 s, pad 250 ms, never overlap, never bridge across the cut.
7. **Per-window `TimestampOffsetMap`** with global ms. STT sees only this window's compacted WAV, so timestamps start at 0 per window and `slice_compacted_start_ms` from the base notebook is no longer needed. Projection uses `bisect`: starts resolve to the island that contains/starts at the time, ends to the island that ends at/after it (boundary values never jump across a dropped silence). A cheap self-test asserts this.
8. **STT** (diarization off, idempotent via job key and `stt_jobs`), insert `TranscriptSegment`-like dicts with monotonic `seq_index`.
9. **Carryover** `[cut..end]` saved as `carryover_tail_win_XXX.wav`; session fields updated.
10. **Flush** (policy implemented; currently disabled, §6). Per-window report JSON written to `02_server/reports/`.

### 4.5 Concurrency model
`ThreadPoolExecutor(max_workers=1)` per session = the per-session sequential queue (production: per-session lock / chained queue / advisory lock). The main thread plays the client and keeps uploading while windows process in the background; worker logs are buffered thread-safely and drained by the main loop (prints from background threads are unreliable in Jupyter).

### 4.6 Stop / finalize
Enqueue final window (`last_enqueued_seq+1 .. last_seq`, possibly zero chunks if only carryover remains — so jobs = `N // 20 + 1`) → drain queue (re-raise worker exceptions) → build master (concat all chunks with SHA check → `ffmpeg -c copy -fflags +genpts` → ffprobe) → `master_verified` if duration within 1 s of the client stream and byte count matches → status `ready`.

### 4.7 STT providers
`SimulatedSTT` (default; one placeholder segment per 15 s; validates cuts/offset maps/timestamps, **not** recognition quality). `DeepgramSTT` (REST `/v1/listen`, `utterances=true`, `diarize=false`; **untested**, needs `DEEPGRAM_API_KEY`). Sarvam must implement the same contract (documented in the notebook): list of `{start_ms, end_ms, text}` relative to the uploaded WAV, diarization disabled.

### 4.8 Measurements and verification
- Report: per-window cut table (global cut time, reason, pause length, carryover, silence removed, processing time), windows finished before Stop, backlog at Stop, estimated synchronous baseline (`sum(t_total_s)`), speedup, peak server storage, forced cuts.
- Assert checklist: chunk completeness; job count; window 0 finished before Stop; window continuity (`next.combined_global_start ≈ prev.cut_global`, ±50 ms); segments inside `[combined_start, cut+pad]`; `seq_index` contiguous; `start_ms` non-decreasing; times within master duration; decoded window length vs cluster span (±300 ms); idempotent duplicate enqueue; flushing/retention checks; master verified; local master size equals sum of chunks.

---

## 5. Result folder produced when the notebook runs
`backend/notebooks/result/pipeline_phase1/`
```
00_source/        source_probe.json, previews/trap1 temp files
01_client/        browser_stream.webm, chunk_manifest.json, upload_queue/, local_master_opfs.webm
02_server/        chunks/, webm_header.bin, work/win_XXX/, carryover/, reports/window_XXX.json, master/master_raw.webm
03_transcripts/   transcript_segments.jsonl, transcript.txt, window_stt_raw/window_XXX.json
04_analysis/      phase1_rolling_analysis.png, samples/ (window0 raw/dsp 30 s), previews/
05_state/         session_state.json, pipeline_log.jsonl, phase1_summary.json
```
**Important:** these results **do not exist yet** — the notebook has not been executed in this session, so no numbers (duration, latency, speedup, check outcomes) were obtained. Run it to produce them.

---

## 6. Follow-up change: deletions disabled (request #2)
Reason: the user wanted to inspect all outputs. Edited the saved ipynb directly (string replacements on cell sources; syntax re-checked; no execution):
- `FLUSH_INTERMEDIATES=False`, `CLEAN_RUN=False`; the `shutil.rmtree(RESULT_DIR)` start-up wipe commented out (re-runs overwrite in place).
- Trap-1 demo temp files (`trap1_*.webm`) no longer unlinked.
- Per-window flush (`work/win_XXX/` rmtree + consumed carryover unlink) commented out.
- `master_concat_tmp.webm` no longer unlinked.
- Server transport-chunk flush after `master_verified` commented out.
- Client upload-queue purge commented out (log now says "purge SKIPPED (kept)").
- `LOCAL_MASTER.unlink()` replaced by truncation (`write_bytes(b"")`) so re-runs don't append twice.
- Verification: flush-related asserts remain inside `if FLUSH_INTERMEDIATES:`; an `else` check asserts the files are retained.
- Config markdown table updated. Blocks are marked `DELETION DISABLED`; set `FLUSH_INTERMEDIATES=True` and uncomment to restore production behaviour.
- Side effect: with the full lecture, disk use is large (source stream + per-window WAVs, several × the 60 MB source); use `LIMIT_MINUTES` for smaller runs.

---

## 7. Decisions and why
| Decision | Why |
| --- | --- |
| Cluster-aligned 30 s chunks via EBML walker | Mirrors real MediaRecorder; makes mid-stream windows decodable with a cached header; gives exact timecodes. |
| Cache header + never flush chunks before master verified | Trap 1; also enables window recompute after a crash. |
| Cut at midpoint of last pause ≥ 400 ms, carryover tail | Trap 2; midpoint keeps silence on both sides. |
| Single VAD pass (400 ms, pad 0) then derive compaction | Avoids two Silero runs per window; true pause lengths for cut selection. |
| Anchor each window to cluster Timecode | Prevents drift accumulation from decoded-duration arithmetic. |
| Per-window offset map | STT is called per window, so local time restarts at 0. |
| Single-worker executor | Window k+1 needs window k's carryover and `seq_index`. |
| Idempotency key + stored STT result | Retries never bill twice. |
| Simulated STT default | No API key/network assumed; validates timeline logic only. |
| `REPLAY_SPEEDUP=20` | A 1 h+ lecture at real time would take 1 h+; rolling benefit still demonstrable. |
| Generator script instead of hand-written JSON | Avoids JSON escaping errors in ~700 lines of embedded code; script only produced the file. |
| Not running the notebook | `AGENTS.md` forbids execution unless instructed. |

---

## 8. Known gaps / next steps
- **Notebook never executed**; first run may reveal environment issues (Silero weights need network on first load; `torch`, `matplotlib`, FFmpeg with `libopus`/`libmp3lame` required; the `-cluster_time_limit` muxer option and Chrome-like cluster sizing are assumed to behave as expected; the Trap-1 demo outcome should be verified, not assumed).
- Recommended: smoke-test with `LIMIT_MINUTES=25` (gives 2 chunk windows... i.e. ~50 chunks → 2 full windows + final), then the full lecture.
- Real STT not exercised: no WER, STT latency, provider file-size limits (Sarvam), or word-level quality around `cut_global_ms`. Re-run with `LAZYNOTE_STT_PROVIDER=deepgram` (or a Sarvam provider) and inspect words at each cut.
- Timecode scale/unknown-size clusters and non-WebM browsers (Safari → MP4/AAC) need fallbacks in production.
- Production persistence: update segment inserts + carryover + `last_processed_chunk_seq` in one DB transaction; persist carryover to R2; alert on window backlog.
- Notes/LLM stage unchanged from the base notebook (runs once after the final window over the full transcript).

## 9. Related docs in this folder
`Lazy Note Audio Transcription Hld Lld.md`, `Lazy Note Complete System Design Hld Lld Blueprint.md`, `Lazy Note --- Audio Pipeline & Backend Architecture Discussion.md`, `adaptive_voice_profiling_dsp.md`, `transcript archtechture update and discusstion.md`, etc. (architecture background; not re-read during this session).

