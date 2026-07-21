# SenseVoice GGUF Q8 local benchmark

Date: 2026-07-21

## Scope and environment

This benchmark compares the application's current SenseVoice provider with the
official GGUF Q8 runtime. It is a CPU benchmark, not a GPU benchmark.

- CPU: Intel Core i5-12600KF (10 cores / 16 logical processors)
- RAM: 32 GB
- OS: Windows
- Current provider: FunASR 1.3.14, PyTorch 2.12.1+cpu, `model.pt` (892.92 MiB)
- GGUF runtime: official `runtime-llamacpp-v0.1.4`, Windows x64 AVX2 binary
- GGUF model: `sensevoice-small-q8.gguf` (242.43 MiB)
- Q8 SHA-256: `4ae45c94422de949b387e2e0fb10d7e14e4c42c69db30c3444ecc7d4b844b7c5`
- Input: official `runtime/llama.cpp/tests/sample.wav`, repeated ten times to
  make a 60.0 second, 16 kHz mono PCM WAV. Both paths used FSMN-VAD.

The current application path is `SenseVoiceSmallTranscriber`: it constructs
`funasr.AutoModel(model="iic/SenseVoiceSmall", vad_model="fsmn-vad",
device="cpu")` and uses `generate(..., language="auto", use_itn=True)`.

## Reproduction

Download the official Windows AVX2 archive from the `runtime-llamacpp-v0.1.4`
release, plus `sensevoice-small-q8.gguf` from
`FunAudioLLM/SenseVoiceSmall-GGUF` and `fsmn-vad.gguf` from
`FunAudioLLM/fsmn-vad-GGUF`.

Run the GGUF path as follows (replace paths as appropriate):

```powershell
Measure-Command {
  .\llama-funasr-sensevoice.exe -m .\sensevoice-small-q8.gguf `
    -a .\sample-60s.wav --vad .\fsmn-vad.gguf
}
```

For the current provider, time `SenseVoiceSmallTranscriber.load_model()` in a
fresh Python process, then call `transcribe()` five times on the same WAV and
report the median. Do not include model download time in either result.

## Results

| Measurement | Current FunASR / FP checkpoint | GGUF Q8 native runtime |
| --- | ---: | ---: |
| Model weight | 892.92 MiB | 242.43 MiB |
| Fresh-process model load | 11.06 s | approx. 0.08 s process/model overhead* |
| 60 s audio, median end-to-end | 2.05 s (warm model) | 2.52 s (new process each run) |
| Throughput | 29.28 audio-s / wall-s | 23.85 audio-s / wall-s |
| Real-time factor | 0.0342 | 0.0419 |

\* The GGUF executable reports 2.43 s inference for the 60 s file; median
wall-clock time was 2.5154 s. The difference includes executable startup,
GGUF mapping, and process setup. This is a warm file-system-cache measurement,
not a cold-boot disk benchmark.

The Q8 runtime was also run successfully against the official Chinese,
Cantonese, English, Japanese, and Korean example MP3 files.

## Output validation

- The 6-second official regression sample matched the current provider exactly
  (12 characters; edit distance 0).
- On the synthetic 60-second repeated sample, output differed by 3 characters
  over 113 characters (normalised edit rate 2.65%).

Therefore Q8 is functionally usable for the supported languages, but this local
test does not establish bit-for-bit or transcript-for-transcript equivalence on
all audio. Use a representative multilingual evaluation set before making it
the sole provider.

## Interpretation

On this CPU, Q8 materially improves cold availability and storage footprint,
but it is about 18.6% slower for steady-state inference on this 60-second
sample. It should be evaluated primarily as a deployment/cold-start
optimization, not as a guaranteed throughput optimization.
