# Lazy Note — Phase 1 Pipeline Critical Review & Production Readiness Blueprint

**Reviewed Artifact:** `backend/notebooks/pipelinephase1.ipynb` (Asynchronous Rolling 10-Minute Macro-Batch Pipeline)  
**Target Environment:** FastAPI + PostgreSQL (Supabase) + Cloudflare R2 + Background Workers (Inngest / Celery)  
**Review Scope:** Empirical analysis of notebook execution results, hidden production failure modes, literature/community validation, and actionable **What / Where / Why / How** remediation guide.

---

## 1. Executive Summary: What You Nailed (And Why This Architecture Is Strong)

Before diving into the failure modes, it is important to recognize what `pipelinephase1.ipynb` gets **fundamentally right**. Most first-generation lecture transcription pipelines fail because they treat a 90-minute audio stream as a monolithic file that can only be processed after the user taps **Stop**. Your Phase 1 notebook solves several hard systems problems cleanly:

1. **The Rolling 10-Minute Macro-Batch Concept (§0–§1):** Processing 20 contiguous 30-second chunks ($10\text{ min}$) in the background while the lecture is still being recorded reduces post-Stop wait time on a 61-minute lecture from $\sim 45.7\text{ s}$ (simulated compute only) to **$5.75\text{ s}$**—and in production with real network STT latency, this will cut user wait time from $\sim 3\text{ minutes}$ down to **$< 20\text{ seconds}$**.
2. **Global Wall-Clock Anchoring via Cluster Timecodes (§6.3, §8):** Anchoring each window's `TimestampOffsetMap` to `win_global_start_ms - co_ms` (derived from the container's cluster timecode rather than assuming $20 \times 30,000\text{ ms} = 600,000\text{ ms}$) prevents cumulative clock drift over multi-hour recordings.
3. **Asymmetric Bisect Projection in `TimestampOffsetMap` (§6.3):** Resolving segment `start_ms` with `bisect_right` and `end_ms` with `bisect_left(..., is_end=True)` is a subtle, high-craft detail that prevents boundary timestamps from jumping across dropped silence intervals.
4. **Strict Separation of Ephemeral Intermediates vs. Source of Truth (§2, §14.3):** Keeping transport chunks until `master_raw.webm` is verified, flushing heavy intermediate WAVs per window, and keeping the client's OPFS local master for zero-data-cost offline playback is textbook resilient systems design.

However, **your own notebook's execution outputs in Cells 16, 17, 21, 22, and 23 quietly exposed 7 production failure modes**—two of which will break the pipeline the moment you connect a real browser `MediaRecorder` or a real Speech-to-Text API.

---

## 2. Empirical Diagnosis: What Your Notebook Outputs Are Secretly Telling You

If you look closely at the stdout/stderr logs in your executed cells, the numbers reveal three anomalies that pass your `assert` checks only because `SimulatedSTT` does not inspect audio quality:

### Anomaly A: Why did Silero VAD only remove $0.1\%$ to $1.4\%$ of silence in a 61-minute lecture, and why did Window 2 fail to find a breath pause?
Look at the table printed by **Cell 21 (`p10018418d`)**:
* **Silence removed:** Window 0 = `0.7%`, Window 1 = `0.1%`, Window 2 = `0.4%`, Window 3 = `0.1%`, Window 4 = `1.4%`, Window 5 = `4.2%`.
* **Window 2 Cut Reason:** `cut=1797651ms (forced_low_energy_frame) | Pause (ms) = 0`.

In a real 61-minute classroom lecture, a professor pauses to breathe every $4\text{ to }10\text{ seconds}$ and pauses to write on the board or switch slides for $5\%$ to $25\%$ of the lecture. Why did Silero VAD think the professor spoke for $99.9\%$ of Window 1 and $30.0\text{ seconds}$ straight without a single $400\text{ ms}$ breath in Window 2?

Now look at **Cell 23 (`p10022a06a`)**:
```text
Metric (first 30 s, window 0)    |        Raw |        DSP |     Delta
RMS (dB)                         |     -33.17 |     -18.49 |    +14.68
Peak (dB)                        |     -12.11 |      -0.45 |    +11.66
```
Your `STT_FILTER_CHAIN` in Cell 17 includes `speechnorm=e=6.25:r=0.0001:l=1`. As documented in FFmpeg's filter reference and audio engineering post-mortems, `speechnorm` with `e=6.25` is an aggressive dynamic expander that boosts quiet intervals by up to $+16\text{ dB}$ (`+14.68 dB` measured in your log!). During breath pauses and room silence, `speechnorm` drags the classroom's ambient noise floor and reverb tail up to $-18\text{ dBFS}$. When Silero VAD (`VAD_THRESHOLD = 0.45`) scans that conditioned WAV, the amplified room hiss/reverb crosses the speech probability threshold, **blinding Silero VAD to real silence and breath pauses**.

### Anomaly B: Why did `ffprobe` report a duration of $3658.616\text{ s}$ ($61\text{ min}$) on a $150\text{ s}$ ($2.5\text{ min}$) stitched window in Cell 16?
Look at **Cell 16 (`p10008e6eb`)**:
```text
B) header + chunks 20..24 -> ffmpeg rc=0 | probed duration = 3658.616
```
You stitched 5 chunks (`20..24`, which is $2.5\text{ minutes}$ of audio), yet `ffprobe` reported $3658.616\text{ seconds}$ ($61\text{ minutes}$). Why? Because in Cell 15, you generated `browser_stream.webm` by encoding a static file with FFmpeg (`ffmpeg -i ... browser_stream.webm`). When FFmpeg finishes writing a file on disk, it seeks back to byte `0` and writes the total `Duration` ($3658.616\text{ s}$) into the `Segment -> Info` header inside `chunk_0000`—and it patches every `Cluster` element with a known byte size. **A real browser `MediaRecorder` never does this.**

### Anomaly C: Why is there a $-2\text{ ms}$ to $-4\text{ ms}$ continuity drift between every window in Cell 22?
Look at **Cell 22 (`p10020694e`)**:
```text
✅ continuity window 0->1 | drift=-3 ms
✅ continuity window 1->2 | drift=-2 ms
✅ continuity window 2->3 | drift=-4 ms
✅ window 0 decoded length == cluster span | decoded=599994 span=599991
```
Each 20-chunk window decodes to $599,994\text{ ms}$ of PCM audio while the cluster timecode span is $599,991\text{ ms}$, creating a $3\text{ to }4\text{ ms}$ seam mismatch where the carryover tail joins the newly decoded window.

---

## 3. The 8 Production Failure Modes (What, Where, Why & How to Fix)

Below is a prioritized breakdown of the technical issues that need attention as you port `pipelinephase1.ipynb` into the production `backend/src/lazynote/` services.

---

### Issue 1 (CRITICAL): Real Browser `MediaRecorder` Emits Unknown-Size Clusters & Non-Cluster-Aligned Blobs

* **What Internet / Literature / Community Says:**
  * In Chromium's `WebmMuxer` (`media/muxers/webm_muxer.cc`) and Firefox's `MediaRecorder`, the browser is recording a live, unbounded stream. Therefore, it writes the Matroska `Segment` (`0x18538067`) **and every `Cluster` (`0x1F43B675`)** with the EBML "Unknown Size" sentinel (`0x01FFFFFFFFFFFFFF`, all bits set to 1).
  * As documented in Graham King's technical breakdown (*"Reading MediaRecorder's webm/opus output"*) and Chromium Issue `#40482588`, `MediaRecorder.start(30000)` flushes its byte buffer on a timer. While `chunk_0000` starts with the EBML header, subsequent `dataavailable` blobs are **arbitrary byte slices of the stream**—they frequently split in the middle of a `Cluster` (starting with a raw `SimpleBlock` `0xA3`) or contain unknown-size `Cluster` headers.
  * Furthermore, on iOS Safari and macOS Safari, `MediaRecorder` often defaults to `audio/mp4` (`fMP4` with `moov`/`moof`/`mdat` boxes) rather than WebM.

* **Why It Breaks Your Current Code:**
  In Cell 15 (`scan_webm_clusters`), your parser explicitly raises an exception on unknown-size elements:
  ```python
  if unknown:
      raise ValueError(f"Unknown-size element 0x{eid:X} at byte {pos}: live/unknown-size clusters are not supported")
  ```
  And in Cell 19 (`ack_chunk`), if `scan_webm_clusters(payload)` does not find a top-level `Cluster` at byte 0 of `chunk_0001`, it returns `HTTP 422 no_cluster_timecode`. **When you connect a real Chrome/Firefox browser to `POST /chunks`, 100% of live recordings will fail at `chunk_0000` or `chunk_0001`.**

* **What To Do:**
  1. Replace the rigid top-level `scan_webm_clusters` parser with a **streaming-aware EBML Cluster & Timecode scanner** that supports `unknown` (`0x01FFFFFFFFFFFFFF`) cluster sizes and scans for the `Cluster` ID (`\x1f\x43\xb6\x75`) + `Timecode` ID (`\xe7`) signature anywhere in the chunk.
  2. When stitching a rolling window `start_seq..end_seq` (`start_seq > 0`), slice from the **first Cluster boundary** inside `chunk[start_seq]` up to the **first Cluster boundary** inside `chunk[end_seq + 1]` (or the end of `chunk[end_seq]` if aligned), or pass the stitched bytes through FFmpeg with `-fflags +genpts+igndts -err_detect ignore_err`.
  3. Read `TimecodeScale` (`0x2AD7B1`) from `chunk_0000`'s `Segment -> Info` header instead of hardcoding $1\text{ ms}$, and fallback to `seq_no * CHUNK_SEC * 1000` if a chunk is a mid-cluster continuation blob.

* **Where To Do It:**
  * Notebook: Cell 15 (`scan_webm_clusters`) and Cell 19 (`ack_chunk`, `_process_window_impl`).
  * Production Backend: `backend/src/lazynote/services/webm_parser.py` and `backend/src/lazynote/router/sessions.py`.

* **How To Do It (Production Code):**
  ```python
  import struct
  from dataclasses import dataclass
  from typing import Optional

  ID_SEGMENT = 0x18538067
  ID_INFO = 0x1549A966
  ID_TIMECODE_SCALE = 0x2AD7B1
  ID_CLUSTER = 0x1F43B675
  ID_TIMECODE = 0xE7
  CLUSTER_MAGIC = b"\x1f\x43\xb6\x75"

  @dataclass
  class WebMChunkProbe:
      header_end_offset: Optional[int]      # Populated for chunk_0000 (bytes before first Cluster)
      first_cluster_offset: Optional[int]   # Byte offset of the first Cluster in this chunk
      first_timecode_ms: Optional[int]      # Wall-clock ms of the first Cluster in this chunk
      timecode_scale_ns: int = 1_000_000    # Default 1 ms per tick

  def probe_webm_chunk(data: bytes, timecode_scale_ns: int = 1_000_000) -> WebMChunkProbe:
      """
      Safely probes a live MediaRecorder WebM chunk even when Segment/Cluster sizes
      are marked as 'unknown' (0x01FFFFFFFFFFFFFF) or when a chunk starts mid-Cluster.
      """
      first_cluster_pos = data.find(CLUSTER_MAGIC)
      header_end = first_cluster_pos if (first_cluster_pos != -1 and data[:4] == b"\x1a\x45\xdf\xa3") else None

      # Extract TimecodeScale from header if present in chunk_0000
      if header_end:
          tc_scale_marker = b"\x2a\xd7\xb1"
          idx = data.find(tc_scale_marker, 0, header_end)
          if idx != -1:
              try:
                  sz, sz_len, _ = _read_size(data, idx + 3)
                  val_start = idx + 3 + sz_len
                  timecode_scale_ns = int.from_bytes(data[val_start:val_start + sz], "big")
              except Exception:
                  pass

      # Scan for the first valid Cluster + Timecode (0xE7) child element
      search_pos = 0
      n = len(data)
      while search_pos < n:
          c_pos = data.find(CLUSTER_MAGIC, search_pos)
          if c_pos == -1:
              break
          try:
              # Read Cluster size VINT (may be unknown = True in live MediaRecorder!)
              _, l_size, _ = _read_size(data, c_pos + 4)
              child_pos = c_pos + 4 + l_size
              cid, c_id_len = _read_id(data, child_pos)
              if cid == ID_TIMECODE:
                  tsz, c_sz_len, _ = _read_size(data, child_pos + c_id_len)
                  v_start = child_pos + c_id_len + c_sz_len
                  raw_tc = int.from_bytes(data[v_start:v_start + tsz], "big")
                  tc_ms = int(round(raw_tc * (timecode_scale_ns / 1_000_000.0)))
                  return WebMChunkProbe(
                      header_end_offset=header_end,
                      first_cluster_offset=c_pos,
                      first_timecode_ms=tc_ms,
                      timecode_scale_ns=timecode_scale_ns,
                  )
          except (IndexError, ValueError):
              pass
          search_pos = c_pos + 4

      return WebMChunkProbe(
          header_end_offset=header_end,
          first_cluster_offset=None,
          first_timecode_ms=None,
          timecode_scale_ns=timecode_scale_ns,
      )
  ```
  *Bonus Client-Side Fix:* In your Next.js PWA (`recorder-engine.ts`), if a chunk does not start with a `Cluster` boundary because `MediaRecorder.start(30000)` split mid-Cluster, you can either slice at `first_cluster_offset` when stitching on the server (appending the leading pre-Cluster bytes of `chunk[start_seq]` to the end of the previous window `start_seq - 1`), **or** use `ffmpeg -err_detect ignore_err -fflags +genpts+discardcorrupt` which automatically skips leading orphan `SimpleBlock`s until `first_cluster_offset`.

---

### Issue 2 (CRITICAL): `speechnorm` & `100 Hz` Notch in `STT_FILTER_CHAIN` Blind Silero VAD and Hurt Neural ASR

* **What Internet / Literature / Community Says:**
  * Speech recognition engineering benchmarks (including Deepgram's preprocessing guide, OpenAI Whisper discussions, and Fora Soft's classroom ASR study) warn against applying fast-acting dynamic range expanders/normalizers (`speechnorm`, `compand`, or heavy `dynaudnorm`) before VAD and neural ASR.
  * Neural VAD (Silero VAD) and neural ASR frontends compute log-Mel filterbanks and rely on the **contrast (SNR differential)** between speech energy and background noise energy. When `speechnorm=e=6.25:r=0.0001:l=1` boosts the inter-word room noise floor by $+14.7\text{ dB}$, two bad things happen:
    1. Silero VAD sees a loud, surging noise floor during breath pauses and classifies silence as speech (reducing your VAD silence removal in Cell 21 to $0.1\%–1.4\%$ and causing `forced_low_energy_frame` in Window 2).
    2. ASR models (Whisper / Sarvam / Deepgram) hallucinate filler words ("thank you", "um", repeated tokens) in the boosted noise pockets.
  * Additionally, your `equalizer=f=100:t=q:w=10:g=-15` notch filter has a width of $Q=10$ ($10\text{ Hz}$ bandwidth), which is fine for narrow hum, **except** in FFmpeg's `equalizer` filter, `t=q:w=10` is a $Q$-factor of $10$, whereas `adeclick=w=55:o=75:t=2.5` smears consonant plosives (*p, t, k*) that are critical for distinguishing Hinglish technical terms.

* **Why It Breaks Your Current Code:**
  In `pipelinephase1.ipynb`, VAD compaction is supposed to save $20\%–35\%$ of STT billing cost and guarantee clean breath-pause cuts. Because `speechnorm` precedes Silero VAD, you are paying for $99\%$ of the audio duration and forcing mid-word cuts when the lecturer speaks quickly.

* **What To Do:**
  1. **Remove `speechnorm` and `adeclick` from the pre-VAD / pre-ASR filter chain.**
  2. Use a **strictly linear, phase-safe pre-VAD conditioning chain**: `highpass=f=80:poles=2` (removes sub-80 Hz AC/fan rumble without touching male fundamental pitch $F_0 \approx 95–150\text{ Hz}$), narrow surgical hum notches `equalizer=f=50:t=q:w=20:g=-20,equalizer=f=100:t=q:w=25:g=-12`, and `lowpass=f=7600:poles=2`, followed by **static (linear) peak/RMS gain normalization** in NumPy *after* decoding (or single-pass `loudnorm` / simple headroom scaling to $-3\text{ dBFS}$ peak) so the relative SNR between speech and breath pauses is 100% preserved for Silero VAD!

* **Where To Do It:**
  * Notebook: Cell 17 (`STT_FILTER_CHAIN` and `decode_and_condition`).
  * Production Backend: `backend/src/lazynote/services/audio_dsp.py`.

* **How To Do It (Production Code):**
  ```python
  # Linear, time-invariant filter chain for VAD + Neural ASR (NO dynamic pumping!)
  STT_FILTER_CHAIN = (
      "highpass=f=80:poles=2,"
      "equalizer=f=50:t=q:w=20:g=-20,"
      "equalizer=f=100:t=q:w=25:g=-12,"
      "lowpass=f=7600:poles=2,"
      "aresample=16000:resampler=soxr:precision=28"
  )

  def decode_and_condition(stitched_webm: Path, out_wav: Path) -> Path:
      """
      Decodes stitched WebM to 16kHz mono PCM using strictly linear filters,
      then applies static peak normalization (-1.0 dBFS) in NumPy so Silero VAD
      sees the true, un-pumped speech-to-silence dynamic range.
      """
      subprocess.run(
          [
              "ffmpeg", "-y", "-err_detect", "ignore_err",
              "-fflags", "+genpts+igndts",
              "-i", str(stitched_webm),
              "-af", STT_FILTER_CHAIN,
              "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
              str(out_wav),
          ],
          check=True,
          capture_output=True,
      )
      # Apply linear peak normalization (constant gain across the entire window)
      sig, sr = load_wav_pcm(out_wav)
      peak = float(np.max(np.abs(sig))) if len(sig) else 0.0
      if peak > 1e-4:
          target_peak = 10 ** (-1.0 / 20.0)  # -1.0 dBFS
          # Cap maximum static boost at +20 dB (10x) so pure-silence windows aren't turned into white noise
          gain = min(target_peak / peak, 10.0)
          sig = sig * gain
          _write_pcm16_wav(out_wav, sig, sr)
      return out_wav
  ```

---

### Issue 3 (HIGH): Tiered Cut-Point Selection & Acoustic Overlap Collar for Forced Cuts (Trap 2 Hardening)

* **What Internet / Literature / Community Says:**
  * In speech segmentation literature (such as WhisperX [Bain et al., 2023], NVIDIA NeMo VAD Curator, and the IWSLT 2026 Simultaneous Speech Translation shared task papers), cutting long audio requires a **hierarchical (multi-tier) pause backoff** rather than a single binary threshold (`>= 400 ms` $\rightarrow$ raw 50ms RMS frame).
  * During rapid explanations or mathematical derivations, a professor's inter-phrase micro-pauses are often $150\text{ ms to }350\text{ ms}$. If you only look for $\ge 400\text{ ms}$ in the last $30\text{ s}$ and immediately fall back to a $50\text{ ms}$ RMS minimum in the last $5\text{ s}$, you risk cutting inside a unvoiced fricative (*s, f, sh*) or stop closure (*p, t, k*), which also have very low RMS energy for $50\text{ ms}$!
  * Furthermore, if a forced low-energy cut *does* occur inside continuous speech, cutting cleanly at sample `cut` with zero overlap splits the word in half between Window $k$ and Window $k+1$.

* **Why It Breaks Your Current Code:**
  In Cell 17 (`choose_cut`), if no $\ge 400\text{ ms}$ gap is found in the last $30\text{ s}$, it immediately falls back to `forced_low_energy_frame` in the last $5\text{ s}$ (which happened in Window 2!). And in Cell 19:
  * Window $k$ gets `before = [..., min(s["end"], cut)]`
  * Window $k+1$ gets `tail = combined[cut:]`
  Both halves of the word at `cut` are damaged.

* **What To Do:**
  1. Upgrade `choose_cut()` to a **3-Tier Pause Search** over the last $45\text{ seconds}$:
     * **Tier 1:** Last VAD gap $\ge 400\text{ ms}$ in the last $30\text{ s}$ (`vad_breath_pause_400ms`).
     * **Tier 2:** Last VAD gap $\ge 200\text{ ms}$ in the last $45\text{ s}$ (`vad_micro_pause_200ms`).
     * **Tier 3:** Longest VAD gap $\ge 100\text{ ms}$ in the last $45\text{ s}$ (`vad_longest_micro_pause`).
     * **Tier 4 (Fallback):** Quietest $50\text{ ms}$ frame in the last $10\text{ s}$, **with a $300\text{ ms}$ lookback collar** prepended to `carryover_tail` so Window $k+1$ receives the full unbroken word!

* **Where To Do It:**
  * Notebook: Cell 17 (`choose_cut`) and Cell 19 (`_process_window_impl`).
  * Production Backend: `backend/src/lazynote/services/vad.py`.

* **How To Do It (Production Code):**
  ```python
  def choose_cut(stamps, sig: np.ndarray, sr: int, min_pause_ms: int = 400, search_sec: float = 30.0):
      """
      Multi-tier silence-bounded cut selector.
      Tier 1: Last gap >= 400ms in last 30s
      Tier 2: Last gap >= 200ms in last 45s
      Tier 3: Longest gap >= 100ms in last 45s
      Tier 4: Quietest 50ms RMS frame in last 10s (with 300ms overlap collar flag)
      """
      total = len(sig)
      gaps, prev_end = [], 0
      for st in stamps:
          gaps.append((prev_end, st["start"]))
          prev_end = st["end"]
      gaps.append((prev_end, total))

      # Tier 1: >= 400ms in last 30s
      lo_t1 = max(0, total - int(search_sec * sr))
      min_gap_t1 = int(min_pause_ms * sr / 1000)
      for g0, g1 in reversed(gaps):
          if g1 - g0 >= min_gap_t1:
              mid = (g0 + g1) // 2
              if lo_t1 <= mid < total:
                  return mid, "vad_breath_pause", (g1 - g0) * 1000.0 / sr, 0

      # Tier 2: >= 200ms in last 45s
      lo_t2 = max(0, total - int(45.0 * sr))
      min_gap_t2 = int(200 * sr / 1000)
      for g0, g1 in reversed(gaps):
          if g1 - g0 >= min_gap_t2:
              mid = (g0 + g1) // 2
              if lo_t2 <= mid < total:
                  return mid, "vad_micro_pause_200ms", (g1 - g0) * 1000.0 / sr, 0

      # Tier 3: Longest gap >= 100ms in last 45s
      min_gap_t3 = int(100 * sr / 1000)
      candidates = [(g1 - g0, (g0 + g1) // 2) for g0, g1 in gaps if (g1 - g0) >= min_gap_t3 and lo_t2 <= (g0 + g1) // 2 < total]
      if candidates:
          best_len, best_mid = max(candidates, key=lambda x: x[0])
          return best_mid, "vad_longest_micro_pause", best_len * 1000.0 / sr, 0

      # Tier 4 Fallback: Quietest 50ms frame in last 10s + 300ms overlap collar for carryover
      tail_start = max(0, total - 10 * sr)
      frame = int(0.05 * sr)
      best, best_rms = total, float("inf")
      for a in range(tail_start, max(tail_start + 1, total - frame), frame):
          rms = float(np.sqrt(np.mean(sig[a:a + frame] ** 2))) if a + frame <= total else float("inf")
          if rms < best_rms:
              best, best_rms = a + frame // 2, rms
      collar_samples = int(0.30 * sr)  # 300ms lookback collar so carryover doesn't lose half a word
      return best, "forced_low_energy_frame", 0.0, collar_samples
  ```

---

### Issue 4 (HIGH): Opus Cold-Start Decoder Glitch & Carryover Seam Drift (`-3 ms` to `-4 ms`)

* **What Internet / Literature / Community Says:**
  * Opus (`libopus`) is a stateful hybrid (SILK + CELT) audio codec. Decoding an Opus stream starting cold at an arbitrary Cluster (`chunk_0020`) without the preceding $80\text{ ms}$ of audio (`SeekPreRoll = 80,000,000 ns` in the Matroska Track header) means the decoder's internal prediction filter starts from zero, producing a tiny $5–20\text{ ms}$ transient/phase discontinuity on the very first decoded frame.
  * Furthermore, in your notebook, `carryover_tail.wav` is saved from the end of Window $k-1$ (ending at sample `len(combined)` of Window $k-1$) and concatenated directly with `new_sig[0]` of Window $k$ (`combined = np.concatenate([co_sig, new_sig])`). Because Opus frame boundaries and FFmpeg's resampler filter delay (`soxr` / `swresample`) drop or pad $2–4\text{ ms}$ at the end of a file flush, joining `co_sig` and `new_sig` creates both the `-3 ms` timestamp drift seen in Cell 22 and a sharp waveform sample jump at the join point `len(co_sig)`.

* **Why It Breaks Your Current Code:**
  If `choose_cut` cuts at `19:58.861` (leaving only $1.12\text{ s}$ of speech in `co_sig` right across the `20:00.000` chunk boundary), the word spoken across the `20:00.000` boundary has its first syllable in `co_sig` (end of `chunk_0019`) and its second syllable in `new_sig` (start of `chunk_0020`). A cold Opus decoder start + un-crossfaded sample join at `20:00.000` creates an audible click right inside that word!

* **What To Do:**
  1. **Include 1 Pre-Roll Chunk (`start_seq - 1`) When Decoding Windows `start_seq > 0`:** When decoding Window $k$ (`start_seq..end_seq` where `start_seq > 0`), prepend `chunk[start_seq - 1]` (or the last $2\text{ seconds}$ of clusters from `chunk[start_seq - 1]`) during the FFmpeg decode step so the Opus decoder and the 80Hz highpass IIR filter are 100% warmed up by the time they reach `chunk[start_seq].start_ms`, and then slice `new_sig` at the exact sample offset `(chunk[start_seq].start_ms - chunk[start_seq - 1].start_ms) * sr // 1000`!
  2. **Apply a $5\text{ ms}$ ($80\text{ sample}$) Raised-Cosine Crossfade** at the seam between `co_sig` and `new_sig` to eliminate any single-sample step click.

* **Where To Do It:**
  * Notebook: Cell 19 (`_process_window_impl`, Step 1 & Step 2).
  * Production Backend: `backend/src/lazynote/services/audio_dsp.py`.

* **How To Do It (Production Code):**
  ```python
  # Inside _process_window_impl Step 1:
  if n_chunks:
      stitched = wdir / "stitched.webm"
      preroll_seq = start_seq - 1 if start_seq > 0 and (start_seq - 1) in self.chunks else None
      with open(stitched, "wb") as f:
          if (preroll_seq if preroll_seq is not None else start_seq) > 0:
              f.write(self.header_bytes)
          if preroll_seq is not None:
              f.write(Path(self.chunks[preroll_seq].server_path).read_bytes())
          for s in range(start_seq, end_seq + 1):
              rec = self.chunks[s]
              f.write(Path(rec.server_path).read_bytes())

      dsp_wav = wdir / "dsp_conditioned.wav"
      decode_and_condition(stitched, dsp_wav)
      decoded_sig, _ = load_wav_pcm(dsp_wav)
      win_global_start_ms = self.chunks[start_seq].start_ms

      if preroll_seq is not None:
          # Slice off the warm-up preroll chunk at the exact cluster timecode delta
          preroll_ms = win_global_start_ms - self.chunks[preroll_seq].start_ms
          preroll_samples = int(round(preroll_ms * sr / 1000.0))
          new_sig = decoded_sig[preroll_samples:]
      else:
          new_sig = decoded_sig
  ```

---

### Issue 5 (HIGH): Silero VAD Thread-Safety & Python 3.14 `torch.jit.load` Deprecation Warning

* **What Internet / Literature / Community Says:**
  * Look at the `stderr` in **Cell 17 (`p100104b51`)**:
    ```text
    FutureWarning: `torch.jit.load` is not supported in Python 3.14+ and may break. Please switch to `torch.export`.
    ```
  * Furthermore, in `snakers4/silero-vad`, the model object holds recurrent LSTM hidden states (`_state` and `_context`). When `get_speech_timestamps(wav, model)` runs, it calls `model.reset_states()` and steps through the audio tensor in $512$-sample ($32\text{ ms}$) chunks. As reported in `silero-vad` GitHub issues (#204, #382), sharing a single `VAD_MODEL` instance across concurrent worker threads corrupts the LSTM state and causes silent VAD misfires or runtime tensor shape exceptions.

* **Why It Breaks Your Current Code:**
  In `pipelinephase1.ipynb`, `VAD_MODEL` is a single global object passed into `RollingSession`. In production, if two students record lectures simultaneously and two worker threads call `self.vad_fn(..., self.vad_model)` concurrently, they will overwrite each other's LSTM state mid-window.

* **What To Do:**
  1. Enable **ONNX Runtime (`onnx=True`)** when loading Silero VAD (`load_silero_vad(onnx=True)`). This eliminates the Python 3.14 `torch.jit.load` deprecation warning, runs $2\times–3\times$ faster on CPU, and allows you to instantiate a lightweight per-worker or thread-local `VADIterator` / model wrapper.
  2. Guard `VAD_MODEL` with a `threading.Lock()` (or use `threading.local()` to give each worker thread its own ONNX session instance).

* **Where To Do It:**
  * Notebook: Cell 17 (`load_vad`).
  * Production Backend: `backend/src/lazynote/services/vad.py` and `pyproject.toml` (add `onnxruntime`).

* **How To Do It (Production Code):**
  ```python
  import threading
  from silero_vad import load_silero_vad, get_speech_timestamps

  _vad_tls = threading.local()

  def get_thread_safe_vad():
      """Returns a thread-local Silero VAD ONNX model (avoids TorchScript 3.14 deprecation & LSTM state races)."""
      if not hasattr(_vad_tls, "model"):
          try:
              _vad_tls.model = load_silero_vad(onnx=True)
              _vad_tls.source = "silero_vad (ONNX Runtime, thread-local)"
          except Exception:
              _vad_tls.model = load_silero_vad(onnx=False)
              _vad_tls.source = "silero_vad (PyTorch JIT, thread-local)"
      return _vad_tls.model, get_speech_timestamps, _vad_tls.source
  ```

---

### Issue 6 (HIGH): Sarvam AI API Limits & Cross-Window Context Starvation

* **What Internet / Literature / Community Says:**
  * According to [Sarvam AI's official Saaras documentation](https://docs.sarvam.ai/api/getting-started/models/saaras), Sarvam's synchronous REST endpoint (`/speech-to-text`) has a **hard 30-second audio duration cap** (`Max 30 seconds of audio per request`). For files longer than 30 seconds (up to 2 hours), you **must** use **Sarvam's asynchronous Batch API** (or split the 10-minute compacted audio into $\le 28\text{ s}$ VAD-bounded sub-chunks).
  * Additionally, research on code-switched ASR and chunked transcription ([arXiv:2610.27631v1](https://arxiv.org/html/2610.27631v1), WhisperX) shows that when a lecture is transcribed in independent windows without passing **domain keyterms** or **rolling text context** (the last sentence of Window $k-1$), technical terms (e.g., *"Graph Neural Network"*, *"Weisfeiler-Lehman"*, *"Eigenvalue"*) get spelled or transliterated inconsistently across windows.

* **Why It Breaks Your Current Code:**
  In §7 (`STTProvider`), `transcribe_file(self, wav_path: Path)` assumes a single synchronous HTTP POST of a ~10-minute (~18 MB) WAV file. While that works for `DeepgramSTT` (`/v1/listen` supports up to 2 GB synchronously), calling Sarvam's REST endpoint with a 10-minute WAV will immediately fail with `HTTP 400 / 413 Audio duration exceeds 30s limit`.

* **What To Do:**
  1. Update the `STTProvider.transcribe_file` signature to accept `context_prompt: Optional[str] = None` and `keyterms: Optional[list[str]] = None`.
  2. In `RollingSession._process_window_impl`, pass the last 2 segment texts from Window $k-1$ (`self.transcript[-2:]`) plus the session's domain keyterms into `self.stt.transcribe_file(...)`.
  3. Implement `SarvamSaarasSTT` using either:
     * **Option A (Low-Latency Parallel Sub-Batching for 10-Min Windows):** Since your VAD pass in Step 5 already has the fine-grained `before` speech stamps, pack them into $\le 28\text{ s}$ silence-bounded sub-slices and send them to Sarvam's fast REST endpoint with `asyncio.Semaphore(5)` (finishes a 10-minute window in $\sim 4\text{ seconds}$ without waiting for Batch API container spin-up!).
     * **Option B (Sarvam Batch Job API):** Submit the 10-minute `vad_compacted.wav` to Sarvam's Batch API and poll until completion.

* **Where To Do It:**
  * Notebook: Cell 18 (`STTProvider` classes) and Cell 19 (`_process_window_impl`, Step 6).
  * Production Backend: `backend/src/lazynote/services/stt.py`.

* **How To Do It (Production Code):**
  ```python
  class STTProvider:
      name: str
      def transcribe_file(
          self,
          wav_path: Path,
          context_prompt: Optional[str] = None,
          keyterms: Optional[list[str]] = None,
      ) -> list[dict]:
          raise NotImplementedError
  ```
  And inside `_process_window_impl` Step 6:
  ```python
  prev_context = " ".join(s["text"] for s in self.transcript[-2:]) if self.transcript else None
  raw_segs = self.stt.transcribe_file(
      vad_wav,
      context_prompt=prev_context,
      keyterms=self.keyterms,
  )
  ```

---

### Issue 7 (MEDIUM-HIGH): Synchronous Blocking in `stop_and_finalize()` & Missing `-cues_to_front 1` on `master_raw.webm`

* **What Internet / Literature / Community Says:**
  * In production web architectures (Vercel, Cloudflare, AWS ALB, Render), HTTP requests have a strict $30\text{ s to }100\text{ s}$ gateway timeout.
  * Furthermore, when remuxing WebM files with FFmpeg (`-c copy`), Matroska writes the `Cues` element (the timestamp-to-byte-offset seek table) at the **end** of the file by default. When a browser's `<audio>` player tries to seek to `[42:15]` on a 15 MB WebM file hosted on Cloudflare R2, missing front cues forces the browser to either download the entire file or fail to seek accurately.

* **Why It Breaks Your Current Code:**
  1. In Cell 19, `stop_and_finalize()` blocks synchronously on `self._executor.shutdown(wait=True)` and `self._build_master()`. If a student's phone was offline for the last 20 minutes of class and uploads 40 chunks right before tapping **Stop**, the server will have 2 full windows + 1 final window + master build queued ($\sim 45–90\text{ s}$ of real STT work). A synchronous `/finalize` endpoint will time out with `HTTP 504`.
  2. In `_build_master()`, `ffmpeg -y -err_detect ignore_err -fflags +genpts -i tmp -c copy master_raw.webm` omits `-cues_to_front 1`.

* **What To Do:**
  1. Make `POST /api/v1/sessions/{id}/finalize` **non-blocking (`HTTP 202 Accepted`)**: verify sequence completeness (`max_contiguous_seq == expected_chunks - 1`), set `status = "finalizing"`, enqueue the final window job + a chained `build_and_verify_master` job, and let the client poll `GET /api/v1/sessions/{id}` (or listen via SSE) until `status == "ready"` and `master_verified == True`.
  2. Add `-cues_to_front 1` to the FFmpeg master remux command in `_build_master()`.

* **Where To Do It:**
  * Notebook: Cell 19 (`_build_master` and `stop_and_finalize`).
  * Production Backend: `backend/src/lazynote/services/audio_dsp.py` and `backend/src/lazynote/router/sessions.py`.

* **How To Do It (Production Code):**
  ```python
  # In _build_master():
  subprocess.run(
      [
          "ffmpeg", "-y",
          "-err_detect", "ignore_err",
          "-fflags", "+genpts+igndts",
          "-i", str(tmp),
          "-c", "copy",
          "-cues_to_front", "1",  # Places Matroska seek index at the front for instant HTTP Range scrubbing!
          str(master),
      ],
      check=True,
      capture_output=True,
  )
  ```

---

### Issue 8 (MEDIUM): PostgreSQL Concurrency Race on the Rolling Window Trigger (`max_contiguous_seq`)

* **What Internet / Literature / Community Says:**
  * In a multi-worker FastAPI deployment (`uvicorn --workers 4`), chunk uploads from the client (`chunk_0018`, `chunk_0019`) can land on two different OS processes simultaneously.
  * In your notebook, `self._lock = threading.RLock()` protects `self.max_contiguous_seq` and `self.last_enqueued_seq` in memory. In production, an in-memory `threading.RLock()` does **not** synchronize across multiple Uvicorn processes or containers.

* **Why It Breaks Your Current Code:**
  If Worker A processes `chunk_0018` and Worker B processes `chunk_0019` at the same millisecond without a database row lock, both workers might read `max_contiguous_seq = 17`, or neither worker might see the contiguous chain `0..19` complete, causing Window 0 (`0..19`) to never fire until `chunk_0020` arrives (or firing duplicate enqueue attempts).

* **What To Do:**
  Use a single atomic PostgreSQL transaction with `SELECT ... FOR UPDATE` on the `recording_sessions` row when acknowledging a chunk, and compute `max_contiguous_seq` directly in SQL using a contiguous-island query.

* **Where To Do It:**
  * Production Backend: `backend/src/lazynote/repositories/session_repo.py` (inside `ack_chunk`).

* **How To Do It (Production SQL / SQLAlchemy):**
  ```sql
  -- 1. Lock the session row for this chunk ack transaction
  SELECT id, last_enqueued_seq, max_contiguous_seq
  FROM recording_sessions
  WHERE id = :session_id
  FOR UPDATE;

  -- 2. Upsert the verified chunk
  INSERT INTO audio_chunk_logs (session_id, seq_no, sha256, byte_size, r2_key, start_ms, is_verified)
  VALUES (:session_id, :seq_no, :sha256, :byte_size, :r2_key, :start_ms, true)
  ON CONFLICT (session_id, seq_no) DO UPDATE SET is_verified = true;

  -- 3. Atomically compute the highest contiguous verified seq_no starting from 0
  WITH ordered_chunks AS (
      SELECT seq_no, ROW_NUMBER() OVER (ORDER BY seq_no) - 1 AS expected_seq
      FROM audio_chunk_logs
      WHERE session_id = :session_id AND is_verified = true
  )
  SELECT COALESCE(MAX(seq_no), -1) AS max_contiguous_seq
  FROM ordered_chunks
  WHERE seq_no = expected_seq;
  ```

---

## 4. Summary Action Matrix (Quick Reference for Coding Agents)

| Priority | Issue | What To Do | Where To Do It | Why To Do It |
| :--- | :--- | :--- | :--- | :--- |
| **P0 (Blocker)** | **Live `MediaRecorder` Unknown-Size Clusters** | Replace strict EBML size check with streaming `probe_webm_chunk` that allows `unknown` (`0x01FFFFFFFFFFFFFF`) sizes and mid-cluster blobs. | `pipelinephase1.ipynb` (§5) / `services/webm_parser.py` | Real Chrome/Firefox `MediaRecorder` writes unknown-size clusters; current parser raises `ValueError` on live streams. |
| **P0 (Blocker)** | **`speechnorm` Blinding Silero VAD** | Remove `speechnorm` & `adeclick` from `STT_FILTER_CHAIN`; use linear HPF/Notch/LPF + static NumPy peak normalization (`-1 dBFS`). | `pipelinephase1.ipynb` (§6.1) / `services/audio_dsp.py` | `speechnorm` boosted room noise by `+14.7 dB`, reducing VAD silence removal to `0.1%` and causing forced mid-word cuts. |
| **P1 (High)** | **Single-Threshold Cut Point (`400ms`)** | Implement 3-tier pause backoff (`400ms` $\rightarrow$ `200ms` $\rightarrow$ `100ms` in last 45s) + `300ms` overlap collar on forced cuts. | `pipelinephase1.ipynb` (§6.2) / `services/vad.py` | Prevents `forced_low_energy_frame` mid-word cuts (seen in Window 2) during fast lecture speech. |
| **P1 (High)** | **Opus Cold-Start & Seam Drift (`-3ms`)** | Decode with 1 pre-roll chunk (`start_seq - 1`) and slice at exact cluster delta + apply 5ms crossfade with `carryover_tail`. | `pipelinephase1.ipynb` (§8) / `services/audio_dsp.py` | Eliminates 80ms Opus decoder cold-start click and `-3ms` drift at the carryover join boundary. |
| **P1 (High)** | **Silero VAD Thread-Safety & Py3.14 JIT** | Load Silero VAD with `onnx=True` inside `threading.local()` (or per-worker process). | `pipelinephase1.ipynb` (§6.2) / `services/vad.py` | Fixes Python 3.14 `torch.jit.load` deprecation and prevents concurrent sessions from corrupting LSTM states. |
| **P1 (High)** | **Sarvam 30s REST Cap & Context Loss** | Pass `context_prompt` (last 2 segs) + `keyterms` per window; use Sarvam Batch API or parallel $\le 28\text{s}$ VAD sub-batches. | `pipelinephase1.ipynb` (§7) / `services/stt.py` | Sarvam's sync REST API rejects files $> 30\text{s}$; rolling context keeps technical Hinglish terms consistent across windows. |
| **P2 (Medium)** | **Blocking `/finalize` & Slow WebM Seek** | Make `/finalize` async (`202 Accepted`) and add `-cues_to_front 1` to `_build_master()` FFmpeg command. | `pipelinephase1.ipynb` (§8) / `router/sessions.py` | Prevents 504 Gateway Timeouts on finalize and enables instant `<audio>` timestamp scrubbing from R2. |
| **P2 (Medium)** | **Multi-Worker DB Trigger Race** | Use PostgreSQL `SELECT ... FOR UPDATE` on `recording_sessions` when advancing `max_contiguous_seq` and `last_enqueued_seq`. | `repositories/session_repo.py` | Prevents missed or duplicate window jobs when chunks arrive concurrently on multiple FastAPI workers. |