from __future__ import annotations

import argparse
import os
import platform
import shutil
import stat
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path


RELEASE_TAG = "runtime-llamacpp-v0.1.4"
RELEASE_BASE = f"https://github.com/FunAudioLLM/SenseVoice/releases/download/{RELEASE_TAG}"


def target_asset(target: str | None, avx2: bool) -> tuple[str, str]:
    value = (target or "").lower()
    system = platform.system().lower()
    machine = platform.machine().lower()
    if value:
        system = "windows" if "windows" in value else "darwin" if "darwin" in value else "linux"
        machine = "arm64" if "aarch64" in value or "arm64" in value else "x64"

    if system == "windows" and machine in {"amd64", "x86_64", "x64"}:
        suffix = "-avx2" if avx2 else ""
        return f"funasr-llamacpp-windows-x64{suffix}.zip", "llama-funasr-sensevoice.exe"
    if system == "linux" and machine in {"amd64", "x86_64", "x64"}:
        suffix = "-avx2" if avx2 else ""
        return f"funasr-llamacpp-linux-x64{suffix}.tar.gz", "llama-funasr-sensevoice"
    if system == "linux" and machine in {"aarch64", "arm64"}:
        return "funasr-llamacpp-linux-arm64.tar.gz", "llama-funasr-sensevoice"
    if system in {"darwin", "macos"} and machine in {"aarch64", "arm64"}:
        return "funasr-llamacpp-macos-arm64.tar.gz", "llama-funasr-sensevoice"
    raise SystemExit(
        f"No official prebuilt SenseVoice runtime for {system}/{machine}. "
        "Build runtime/llama.cpp from source and set AURA_SENSEVOICE_GGUF_BIN."
    )


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Aura-build/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage the official SenseVoice GGUF runtime")
    parser.add_argument("--target", default=os.environ.get("TAURI_ENV_TARGET_TRIPLE"))
    parser.add_argument("--avx2", action="store_true", default=os.environ.get("AURA_GGUF_AVX2") == "1")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "src-tauri" / "resources" / "sensevoice-gguf",
    )
    args = parser.parse_args()
    asset, executable_name = target_asset(args.target, args.avx2)
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / executable_name
    version_file = args.output / "VERSION"
    expected_version = f"{RELEASE_TAG}\n{asset}\n"
    if not args.force and destination.is_file() and version_file.is_file():
        if version_file.read_text(encoding="ascii") == expected_version:
            print(f"SenseVoice runtime already staged: {destination}")
            return

    with tempfile.TemporaryDirectory(prefix="aura-sensevoice-runtime-") as temporary:
        temporary_path = Path(temporary)
        archive = temporary_path / asset
        print(f"Downloading {RELEASE_BASE}/{asset}")
        download(f"{RELEASE_BASE}/{asset}", archive)
        extracted = temporary_path / "extracted"
        extracted.mkdir()
        if asset.endswith(".zip"):
            with zipfile.ZipFile(archive) as package:
                package.extractall(extracted)
        else:
            with tarfile.open(archive, "r:gz") as package:
                package.extractall(extracted)
        source = next(extracted.rglob(executable_name), None)
        if source is None:
            raise SystemExit(f"{executable_name} was not found in {asset}")
        for stale in args.output.glob("llama-funasr-sensevoice*"):
            stale.unlink()
        shutil.copy2(source, destination)
        destination.chmod(destination.stat().st_mode | stat.S_IEXEC)
        version_file.write_text(expected_version, encoding="ascii")
        print(f"Staged {destination}")


if __name__ == "__main__":
    main()
