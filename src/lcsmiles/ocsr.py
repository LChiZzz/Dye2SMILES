from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


class OCSRError(RuntimeError):
    """Raised when optical chemical structure recognition fails."""


def _runtime_candidates() -> list[Path]:
    candidates: list[Path] = []
    runtime_dir_name = "osra-runtime-win" if os.name == "nt" else "osra-runtime"

    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        candidates.append(meipass / "osra-runtime")

        executable = Path(sys.executable).resolve()
        candidates.append(executable.parent / "osra-runtime")
        candidates.append(executable.parent / "_internal" / "osra-runtime")
        candidates.append(executable.parents[1] / "Frameworks" / "osra-runtime")
        candidates.append(executable.parents[1] / "Resources" / "osra-runtime")
        candidates.append(executable.parent.parent / "Resources" / "osra-runtime")

    source_root = Path(__file__).resolve().parents[2]
    candidates.append(source_root / "packaging" / runtime_dir_name)
    candidates.append(source_root / "packaging" / "osra-runtime")
    candidates.append(source_root / "osra-runtime")
    candidates.append(source_root.parent / "osra-runtime")
    return candidates


def _find_bundled_osra() -> tuple[str, Path] | None:
    executable_name = "osra.exe" if os.name == "nt" else "osra"
    for runtime_root in _runtime_candidates():
        osra = runtime_root / "bin" / executable_name
        if osra.exists():
            return str(osra), runtime_root
    return None


def find_osra() -> tuple[str | None, Path | None]:
    bundled = _find_bundled_osra()
    if bundled:
        return bundled

    configured = os.environ.get("OSRA_PATH")
    if configured:
        return configured, None

    found = shutil.which("osra")
    return found, None


def _prepend_env_path(env: dict[str, str], key: str, value: Path) -> None:
    current = env.get(key)
    env[key] = str(value) + (os.pathsep + current if current else "")


def _osra_env(runtime_root: Path | None) -> dict[str, str]:
    env = os.environ.copy()
    if runtime_root is None:
        return env

    bin_dir = runtime_root / "bin"
    lib_dir = runtime_root / "lib"
    share_dir = _runtime_share_dir(runtime_root)

    _prepend_env_path(env, "PATH", bin_dir)
    _prepend_env_path(env, "DYLD_LIBRARY_PATH", lib_dir)
    _prepend_env_path(env, "LD_LIBRARY_PATH", lib_dir)

    graphicsmagick_config = share_dir / "GraphicsMagick-1.3.45" / "config"
    if graphicsmagick_config.exists():
        env.setdefault("MAGICK_CONFIGURE_PATH", str(graphicsmagick_config))

    return env


def _runtime_share_dir(runtime_root: Path) -> Path:
    local_share = runtime_root / "share"
    if local_share.exists():
        return local_share

    app_resources_share = runtime_root.parent.parent / "Resources" / runtime_root.name / "share"
    if app_resources_share.exists():
        return app_resources_share

    return local_share


def _osra_dictionary_args(runtime_root: Path | None) -> list[str]:
    if runtime_root is None:
        return []

    share_dir = _runtime_share_dir(runtime_root)
    dictionary_args: list[str] = []
    for flag, filename in (("-A", "chain.txt"), ("-a", "superatom.txt"), ("-l", "spelling.txt")):
        dictionary = share_dir / filename
        if dictionary.exists():
            dictionary_args.extend([flag, str(dictionary)])
    return dictionary_args


def recognize_image_smiles(path: str | Path) -> list[str]:
    image_path = Path(path).expanduser().resolve()
    osra, runtime_root = find_osra()
    if not osra:
        raise OCSRError(
            "OSRA is not installed or not on PATH. Install OSRA, or set OSRA_PATH "
            "to the osra executable."
        )

    try:
        completed = subprocess.run(
            [osra, *_osra_dictionary_args(runtime_root), str(image_path)],
            check=False,
            capture_output=True,
            env=_osra_env(runtime_root),
            text=True,
            timeout=120,
        )
    except OSError as exc:
        raise OCSRError(f"Could not run OSRA: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise OCSRError("OSRA timed out after 120 seconds") from exc

    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise OCSRError(f"OSRA failed with exit code {completed.returncode}: {stderr}")

    return _parse_osra_output(completed.stdout)


def _parse_osra_output(stdout: str) -> list[str]:
    smiles_values: list[str] = []
    for line in stdout.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        smiles_values.append(text.split()[0])
    return smiles_values
