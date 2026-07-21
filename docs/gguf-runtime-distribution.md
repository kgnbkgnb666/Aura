# GGUF runtime distribution

Aura keeps native SenseVoice executables and GGUF model weights out of Git.

## Native runtime

Run `python scripts/sync-sensevoice-runtime.py` before development or packaging.
The script pins the official SenseVoice release `runtime-llamacpp-v0.1.4`,
detects the build platform, and stages only the matching executable under
`src-tauri/resources/sensevoice-gguf/`. Tauri then includes that directory in
the application bundle.

Supported official artifacts:

- Windows x64
- Linux x64
- Linux ARM64
- macOS ARM64

Generic x64 builds are used by default for CPU compatibility. Set
`AURA_GGUF_AVX2=1` in an AVX2-only release job to select the faster AVX2
artifact. Unsupported targets must build the upstream `runtime/llama.cpp`
runtime and set `AURA_SENSEVOICE_GGUF_BIN` to the resulting executable.

For cross-target builds, pass a Rust/Tauri target triple:

```shell
python scripts/sync-sensevoice-runtime.py --target aarch64-unknown-linux-gnu
```

Release one installer per row; do not put an AVX2 executable in a generic x64
installer.

| Release | Runtime staging command | Tauri bundle |
| --- | --- | --- |
| Windows x64 | `python scripts/sync-sensevoice-runtime.py --target x86_64-pc-windows-msvc` | `tauri build --bundles nsis` |
| Windows x64 AVX2 | the preceding command with `AURA_GGUF_AVX2=1` | `tauri build --bundles nsis` |
| Linux x64 | `python scripts/sync-sensevoice-runtime.py --target x86_64-unknown-linux-gnu` | `tauri build --bundles appimage,deb` |
| Linux x64 AVX2 | the preceding command with `AURA_GGUF_AVX2=1` | `tauri build --bundles appimage,deb` |
| Linux ARM64 | `python scripts/sync-sensevoice-runtime.py --target aarch64-unknown-linux-gnu` | build on an ARM64 runner |
| macOS Apple Silicon | `python scripts/sync-sensevoice-runtime.py --target aarch64-apple-darwin` | `tauri build --bundles dmg` |

Run each job on its native operating system/architecture, and package the Aura
Python sidecar for that same Tauri target. The GGUF staging script only supplies
the SenseVoice executable; it does not cross-compile the sidecar.

## Model weights

The application downloads Q8 SenseVoice and FSMN-VAD weights on first use into
`<model_cache_dir>/sensevoice-gguf`. Downloads are resumable and verified with
pinned SHA-256 hashes before becoming active. Set `AURA_HF_ENDPOINT` to use a
compatible Hugging Face mirror or an internal artifact proxy.

The default `sensevoice-small` provider now uses this native CPU runtime. The
legacy Python/FunASR implementation remains available internally as
`sensevoice-funasr`, and `whisper-large-v3` remains the broad-language fallback.
