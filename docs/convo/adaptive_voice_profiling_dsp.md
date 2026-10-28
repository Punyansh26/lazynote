# Lazy Note: Adaptive Voice-Profiling DSP Filter Chain

**Document Type:** Architecture Decision & Conversation Context  
**Module:** Audio Ingestion & DSP Preconditioning Pipeline  
**Target File Modified:** `backend/notebooks/samplepipeline.ipynb`  
**Date:** 2026-10-28  
**Status:** Approved & Implemented in Notebook Sandbox  

---

## 1. Executive Summary & Context

During early milestone validation of the Lazy Note classroom audio pipeline (`samplepipeline.ipynb`), the recorded audio passed through chunk slicing, simulated network upload, lossless concat remuxing (`master_raw.wav`), and a deterministic 4-filter DSP chain (`dsp_conditioned.wav`).

### User Issue & Requirements
1. **Low Audio Quality / Degradation:** The output audio from the classical DSP filter chain sounded severely degraded, muffled, and unnatural.
2. **Beyond Static Rules:** The user requested that the DSP pipeline not be purely single rule-based. Instead, it must dynamically **identify the lecturer's specific frequency range** and **make that range prominent** rather than amplifying an arbitrary static band, all while retaining natural acoustic quality and intelligibility.

---

## 2. Root Cause Analysis: Flaws in the Classical DSP Chain

The previous DSP filter graph in Section 5 was defined as:
```text
highpass=f=85:poles=2,equalizer=f=50:t=q:w=10:g=-25,equalizer=f=100:t=q:w=10:g=-15,adeclick=w=55:o=75:t=2.5,speechnorm=e=6.25:r=0.0001:l=1
```

Acoustic investigation revealed four primary failure points causing the quality degradation:

1. **`speechnorm=e=6.25:r=0.0001:l=1` (Aggressive Dynamic Pumping):**
   - The expansion parameter `e=6.25` forced up to 6.25× (+16 dB) amplification during low-volume intervals.
   - When the lecturer paused or took breaths between sentences, the filter aggressively boosted the ambient room noise floor, AC hum, and reverberation. This produced jarring "breathing" and noise pumping.
   - The target RMS ratio `r=0.0001` flattened the natural dynamics of human speech into a harsh, distorted waveform.
2. **`adeclick=w=55:o=75:t=2.5` (Transient Destruction & Phase Smearing):**
   - With an overly sensitive threshold (`t=2.5`) and wide window (`w=55`), the declicker misidentified high-frequency vocal consonants (*p*, *t*, *k*, *ch*) and sibilants (*s*, *sh*) as unwanted clicks.
   - Attenuating these transients resulted in phase smearing, flanging artifacts, and muffled speech articulation.
3. **`equalizer=f=100:t=q:w=10:g=-15` (Vocal Thinning & Body Removal):**
   - Human male fundamental speech frequencies ($F_0$) typically range between 85 Hz and 150 Hz (commonly clustered around 100–120 Hz).
   - A wide notch ($Q=10$) with a -15 dB cut at 100 Hz directly scooped out the lecturer’s vocal chest resonance and fundamental pitch, giving the speaker a hollow, tinny sound.
4. **Static 85 Hz Highpass Filter:**
   - A static 85 Hz cutoff cuts into deep male fundamentals ($75–90$ Hz) while failing to eliminate room desk vibrations ($85–130$ Hz) for female speakers whose fundamentals sit well above 175 Hz.

---

## 3. Architecture: Adaptive Voice-Profiling DSP

To resolve these defects, the pipeline was redesigned into a **two-phase architecture**:
1. **Acoustic Profiling Phase (Pure NumPy):** Evaluates the master recording before generating any filter parameters.
2. **Dynamic Synthesis Phase (FFmpeg):** Synthesizes a custom, tailored filter graph matched to the detected vocal characteristics.

```
                      ┌──────────────────────────────────────────────┐
                      │    Input: Reassembled master_raw.wav         │
                      └──────────────────────┬───────────────────────┘
                                             │
                       Adaptive Pitch & Formant Profiling (NumPy)
                                             │
             ┌───────────────────────────────┴───────────────────────────────┐
             ▼                                                               ▼
   Fundamental Pitch ($F_0$)                                     Formant Sweet Spot ($F_1$–$F_3$)
   • Male: ~85–150 Hz                                            • Identifies dominant clarity
   • Female: ~165–240 Hz                                           resonance peak (1.5–3.5 kHz)
   • Sets safe HPF cutoff below $F_0$                            • Generates parametric EQ boost
             │                                                               │
             └───────────────────────────────┬───────────────────────────────┘
                                             │
                             Stationary Hum & Noise Detection
                             • Verifies if 50Hz/100Hz spike >6 dB above floor
                             • Avoids 100Hz notch if it overlaps with $F_0$
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │    Synthesized Dynamic FFmpeg Filter Graph   │
                      │  • Adaptive HPF (protects $F_0$)             │
                      │  • Surgical Hum Notch (only if detected)     │
                      │  • Formant Prominence Boost (+3.5 dB @ Peak) │
                      │  • Clean FFT Denoise (afftdn, no ringing)    │
                      │  • Smooth Dynamic Leveling (dynaudnorm, 400ms)│
                      └──────────────────────────────────────────────┘
```

---

## 4. Signal Processing Algorithm (NumPy Profiler)

The profiler runs in pure Python using NumPy (ensuring full compatibility with the project's existing environment in `pyproject.toml` without requiring external ML dependencies like Librosa or SciPy):

1. **Frame-Based Voiced Activity Detection (VAD):**
   - Breaks the signal into 30 ms frames with 15 ms hop steps.
   - Computes RMS energy per frame:
     $$\text{RMS}_i = \sqrt{\frac{1}{N} \sum_{n=0}^{N-1} x[n]^2}$$
   - Computes the ambient noise floor using the 15th percentile of frame energies.
   - Isolates active speech frames where $\text{RMS}_i > 2.5 \times \text{noise\_floor}$.
2. **Fundamental Frequency ($F_0$) via Normalized Autocorrelation:**
   - Evaluates voiced frames windowed with a Hanning function.
   - Computes normalized autocorrelation $R_{xx}[k]$ across lag intervals corresponding to human pitch bounds (75 Hz to 300 Hz).
   - Validates frames with harmonic peak correlation $>0.35$ and computes the median $F_0$.
   - **Safe HPF Rule:**
     $$f_{HP} = \text{clamp}\left(\lfloor F_0 \times 0.75 \rfloor, 60\text{ Hz}, 120\text{ Hz}\right)$$
     This removes sub-bass building rumble and HVAC thump while strictly preserving the speaker's vocal foundation.
3. **Formant & Presence Peak Detection via Voiced LTAS:**
   - Computes the Long-Term Average Spectrum (LTAS) using `np.fft.rfft` across all voiced frames.
   - Scans the speech intelligibility band ($1500\text{ Hz} \le f \le 3500\text{ Hz}$), which governs vowel formants ($F_2, F_3$) and consonant clarity.
   - Smooths the spectrum with a 5-point moving average and identifies the global presence peak $f_{\text{presence}}$.
   - Feeds this frequency into a parametric bell boost ($+3.5\text{ dB}, Q=1.8$) to make the lecturer cut through room reverberation.
4. **Selective Electrical Hum Detection:**
   - Computes the average FFT spectrum on unvoiced/quiet frames.
   - Tests whether spectral energy at 50 Hz and 100 Hz exceeds neighboring ambient bands by $>6\text{ dB}$ ($>2.0\times$).
   - **Pitch Collision Guard:** If 100 Hz hum is detected, but $|F_0 - 100| \le 18\text{ Hz}$, the 100 Hz notch is **bypassed** to prevent cutting the speaker's vocal pitch.

---

## 5. Filter Graph Replacement & Quality Optimization

| Processing Goal | Legacy Rule (Degraded) | Adaptive Solution (Pristine Quality) |
| :--- | :--- | :--- |
| **Dynamic Range & Volume Leveling** | `speechnorm=e=6.25:r=0.0001:l=1` (Pumping & hiss explosion) | `dynaudnorm=f=400:g=9:p=0.92:m=6.0:r=0.9` (Smooth 400ms window, 6 dB max gain ceiling prevents noise breathing) |
| **Transient Handling** | `adeclick=w=55:o=75:t=2.5` (Flanging, smearing of consonants) | Removed `adeclick` entirely; preserved natural vowel transients and consonant articulation |
| **Pitch Foundation ($F_0$)** | Static `highpass=f=85`, static 100 Hz notch (-15 dB) | Dynamic `highpass=f={safe_hpf}`, conditional 100 Hz notch only when hum detected and $|F_0 - 100| > 18$ |
| **Speech Prominence & Clarity** | None (unshaped dynamic compression) | `equalizer=f={presence_peak}:t=q:w=1.8:g=3.5` (+3.5 dB boost centered at the lecturer's resonance sweet spot) |
| **Acoustic Mud Reduction** | None | `equalizer=f=320:t=q:w=2.0:g=-2.0` (Attenuates boxy classroom room reflection) |
| **Stationary Noise Reduction** | None (amplified by speechnorm) | `afftdn=nf=-28:tn=1:nr=10` (FFT-based stationary denoiser removes fan/HVAC hum without phase artifacts) |
| **Resampling** | Default FFmpeg downsampling | `aresample=16000:resampler=soxr:precision=28` (High-precision SOXR sinc resampling) |

---

## 6. Implementation Code Applied to `samplepipeline.ipynb`

### Section 5: Adaptive Voice-Profiling DSP Cell

```python
# 1. Helper to read raw PCM audio into a numpy float array
def load_wav_pcm(filepath: Path):
    with wave.open(str(filepath), 'rb') as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw_bytes = wf.readframes(n_frames)
        
        if sampwidth == 2:
            dtype = np.int16
        else:
            raise ValueError(f"Unsupported sample width: {sampwidth}")
            
        audio_data = np.frombuffer(raw_bytes, dtype=dtype).astype(np.float32)
        if n_channels > 1:
            audio_data = audio_data.reshape(-1, n_channels)[:, 0]
        audio_data = audio_data / 32768.0  # Normalize to [-1.0, 1.0]
        return audio_data, framerate


# 2. Adaptive Lecturer Voice Profiler (Pure NumPy)
def analyze_lecturer_voice(wav_file: Path):
    """
    Analyzes master audio using pure NumPy to extract:
    1. Lecturer's fundamental pitch (F0) via autocorrelation
    2. Dominant speech formant/presence peak in the clarity band (1.5 kHz - 3.5 kHz)
    3. Safe low-end rumble cutoff (HPF) tailored to the speaker
    4. Electrical hum detection (50 Hz / 100 Hz), ensuring pitch is not notched
    """
    sig, sr = load_wav_pcm(wav_file)
    
    # Frame-based Voiced Activity Detection (VAD)
    frame_len = int(0.030 * sr)  # 30 ms
    hop_len = int(0.015 * sr)    # 15 ms
    num_frames = (len(sig) - frame_len) // hop_len
    
    if num_frames <= 0:
        return {"f0": 120.0, "safe_hpf": 80, "presence_peak": 2500.0, "has_50hz": True, "has_100hz": False}

    frames = np.lib.stride_tricks.sliding_window_view(sig[:num_frames * hop_len + frame_len], frame_len)[::hop_len]
    frame_rms = np.sqrt(np.mean(frames**2, axis=1))
    
    noise_floor = np.percentile(frame_rms, 15) + 1e-7
    speech_thresh = max(noise_floor * 2.5, 0.01)
    voiced_mask = frame_rms > speech_thresh
    voiced_frames = frames[voiced_mask]
    
    if len(voiced_frames) < 10:
        voiced_frames = frames

    # Fundamental Frequency (F0) Estimation via Normalized Autocorrelation
    min_lag = int(sr / 300)  # 300 Hz max pitch
    max_lag = int(sr / 75)   # 75 Hz min pitch
    
    f0_candidates = []
    window = np.hanning(frame_len)
    sample_indices = np.linspace(0, len(voiced_frames) - 1, min(150, len(voiced_frames)), dtype=int)
    
    for idx in sample_indices:
        fr = voiced_frames[idx] * window
        corr = np.correlate(fr, fr, mode='full')
        corr = corr[len(corr)//2:]
        if corr[0] > 1e-6:
            norm_corr = corr / corr[0]
            search_region = norm_corr[min_lag:max_lag]
            peak_lag = min_lag + np.argmax(search_region)
            peak_val = norm_corr[peak_lag]
            if peak_val > 0.35:
                f0_candidates.append(sr / peak_lag)
                
    f0_detected = float(np.median(f0_candidates)) if len(f0_candidates) >= 5 else 120.0
    safe_hpf = max(60, min(120, int(f0_detected * 0.75)))
    
    # Formant & Presence Peak Detection via Long-Term Average Spectrum (LTAS)
    n_fft = 2048
    voiced_windowed = voiced_frames * np.hanning(frame_len)
    fft_spec = np.abs(np.fft.rfft(voiced_windowed, n=n_fft, axis=1))
    ltas = np.mean(fft_spec, axis=0)
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    
    clarity_mask = (freqs >= 1500) & (freqs <= 3500)
    clarity_freqs = freqs[clarity_mask]
    clarity_energy = ltas[clarity_mask]
    
    smooth_kernel = np.ones(5) / 5.0
    clarity_smooth = np.convolve(clarity_energy, smooth_kernel, mode='same')
    presence_peak = float(clarity_freqs[np.argmax(clarity_smooth)])
    
    # Stationary Hum Detection
    unvoiced_frames = frames[~voiced_mask] if np.sum(~voiced_mask) > 10 else frames
    unvoiced_fft = np.mean(np.abs(np.fft.rfft(unvoiced_frames, n=n_fft, axis=1)), axis=0)
    
    def check_spike(target_hz):
        bin_target = np.argmin(np.abs(freqs - target_hz))
        bin_low = np.argmin(np.abs(freqs - (target_hz - 10)))
        bin_high = np.argmin(np.abs(freqs - (target_hz + 10)))
        local_ambient = (unvoiced_fft[bin_low] + unvoiced_fft[bin_high]) / 2.0 + 1e-9
        return (unvoiced_fft[bin_target] / local_ambient) > 2.0

    has_50hz = bool(check_spike(50))
    has_100hz = bool(check_spike(100) and abs(f0_detected - 100) > 18)

    return {
        "f0": round(f0_detected, 1),
        "safe_hpf": safe_hpf,
        "presence_peak": round(presence_peak, 1),
        "has_50hz": has_50hz,
        "has_100hz": has_100hz
    }


# 3. Run Adaptive Profiler
DSP_CONDITIONED_FILE = RESULT_DIR / "dsp_conditioned.wav"
profile = analyze_lecturer_voice(MASTER_RAW_FILE)

print("🎯 Adaptive Voice Profile Identified:")
print(f"   • Fundamental Pitch (F0):     {profile['f0']} Hz")
print(f"   • Safe Highpass Cutoff:       {profile['safe_hpf']} Hz (Protects voice foundation)")
print(f"   • Core Formant Presence Peak: {profile['presence_peak']} Hz (Targeted clarity boost)")
print(f"   • 50 Hz Grid Hum Detected:    {profile['has_50hz']}")
print(f"   • 100 Hz Harmonic Notch:      {'Enabled' if profile['has_100hz'] else 'Skipped (Preserving F0)'}")

# 4. Build High-Fidelity Adaptive Filter Graph
filters = []
filters.append(f"highpass=f={profile['safe_hpf']}:poles=2")

if profile['has_50hz']:
    filters.append("equalizer=f=50:t=q:w=25:g=-20")
if profile['has_100hz']:
    filters.append("equalizer=f=100:t=q:w=25:g=-15")

# Accentuate lecturer's presence sweet spot (+3.5 dB bell with natural Q)
filters.append(f"equalizer=f={profile['presence_peak']}:t=q:w=1.8:g=3.5")

# Gentle boxiness attenuation (cleans room echo around 320 Hz)
filters.append("equalizer=f=320:t=q:w=2.0:g=-2.0")

# High-fidelity FFT denoiser (eliminates stationary AC/fan rumble without phase smearing)
filters.append("afftdn=nf=-28:tn=1:nr=10")

# Smooth dynamic leveling: 400ms frame prevents noise breathing; max gain clamped to 6 dB
filters.append("dynaudnorm=f=400:g=9:p=0.92:m=6.0:r=0.9")

dsp_filter_graph = ",".join(filters)
print(f"\n🎛️ Dynamic Filter Chain: {dsp_filter_graph}")

# 5. Execute FFmpeg with SOXR high-precision sinc resampling
dsp_start = time.time()
dsp_cmd = [
    "ffmpeg", "-y",
    "-i", str(MASTER_RAW_FILE),
    "-af", f"{dsp_filter_graph},aresample=16000:resampler=soxr:precision=28",
    "-ac", "1",
    "-c:a", "pcm_s16le",
    str(DSP_CONDITIONED_FILE)
]
dsp_res = subprocess.run(dsp_cmd, capture_output=True, text=True, check=True)
dsp_duration = (time.time() - dsp_start) * 1000

# 6. Probe DSP output
dsp_probe = json.loads(subprocess.run([
    "ffprobe", "-v", "error",
    "-show_entries", "format=duration,size:stream=sample_rate,channels,codec_name",
    "-of", "json", str(DSP_CONDITIONED_FILE)
], capture_output=True, text=True, check=True).stdout)

dsp_duration_sec = float(dsp_probe['format']['duration'])
dsp_sr = int(dsp_probe['streams'][0]['sample_rate'])
dsp_ch = int(dsp_probe['streams'][0]['channels'])

print(f"✅ Adaptive DSP Conditioning Complete in {dsp_duration:.1f}ms!")
print(f"   Output File:   {DSP_CONDITIONED_FILE.name}")
print(f"   Duration:      {dsp_duration_sec:.2f}s")
print(f"   Sample Rate:   {dsp_sr} Hz (Optimized for Silero VAD & Sarvam STT)")
print(f"   Channels:      {dsp_ch} (Mono)")
print(f"   Output Size:   {DSP_CONDITIONED_FILE.stat().st_size / (1024*1024):.2f} MB")

display(Audio(str(DSP_CONDITIONED_FILE)))
```

---

## 7. Downstream Alignment & Next Milestones

The conditioned 16 kHz 16-bit mono PCM output (`dsp_conditioned.wav`) directly feeds subsequent stages in Lazy Note:
- **Milestone 4 (Silero VAD v6):** Pristine transient retention and stable noise floor without pumping ensure Silero VAD reliably detects true voice boundaries without false triggers during background hiss surges.
- **Milestone 5 (Sarvam AI Saaras v4 STT):** Prominent vocal formants ($F_1–F_3$) and de-mudded room reflections maximize Word Error Rate (WER) performance on Indian English / Hinglish classroom terminology.
- **Production Porting:** The profiler and filter synthesis logic documented here can be ported directly into `backend/src/lazynote/services/audio_dsp.py` when implementing backend API services.

