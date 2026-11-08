"""Automatic dependency bootstrap for VODER.

VODER imports many optional packages only when a feature is first used, so a
missing package used to show up as a cryptic ``ModuleNotFoundError`` halfway
through a job.  This module checks the packages listed in
``app/requirements.txt`` when VODER starts and installs whatever is missing,
printing every step so the terminal shows what is happening.

It only uses the Python standard library, so it can run before torch, numpy or
any other heavy import.
"""

import importlib
import importlib.metadata as _metadata
import json
import os
import re
import subprocess
import sys
import time as _time

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.dirname(_PACKAGE_DIR)
APP_DIR = os.path.dirname(_SRC_DIR)
REQUIREMENTS_FILE = os.path.join(APP_DIR, "requirements.txt")

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")


def _cache_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache")
    path = os.path.join(base, "VODER")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return ""
    return path


_CACHE_DIR = _cache_dir()
_FAILURE_FILE = os.path.join(_CACHE_DIR, "dependency_failures.json") if _CACHE_DIR else ""

# A package that just failed to build should not be retried on every single
# start (ctc-forced-aligner takes minutes to fail on a machine without the C++
# build tools).  It is retried automatically after this many seconds, or right
# away with "python voder.py deps --force".
RETRY_FAILED_AFTER = 7 * 24 * 60 * 60


def _load_failures():
    if not _FAILURE_FILE:
        return {}
    try:
        with open(_FAILURE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return {str(k): float(v) for k, v in data.items()}
    except (OSError, ValueError, TypeError):
        pass
    return {}


def _save_failures(failures):
    if not _FAILURE_FILE:
        return
    try:
        with open(_FAILURE_FILE, "w", encoding="utf-8") as handle:
            json.dump(failures, handle, indent=2, sort_keys=True)
    except OSError:
        pass


def _record_failure(spec, failures):
    failures[_normalized(requirement_name(spec)) or spec] = _time.time()
    _save_failures(failures)


def _clear_failure(spec, failures):
    key = _normalized(requirement_name(spec)) or spec
    if failures.pop(key, None) is not None:
        _save_failures(failures)


def _recently_failed(spec, failures):
    key = _normalized(requirement_name(spec)) or spec
    stamp = failures.get(key)
    return bool(stamp) and (_time.time() - stamp) < RETRY_FAILED_AFTER


def _log(message=""):
    try:
        print(message, flush=True)
    except Exception:
        pass


def _banner(title):
    _log("")
    _log("=" * 66)
    _log(f" VODER - {title}")
    _log("=" * 66)


def read_requirements(path=REQUIREMENTS_FILE):
    """Return the requirement specs from a requirements.txt file.

    Comments, blank lines, nested requirement files and pip options are
    skipped: this is only used to detect what is missing, and pip handles the
    actual resolution.
    """
    specs = []
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
            lines = handle.readlines()
    except OSError:
        return specs

    for raw in lines:
        line = raw.replace("\ufeff", "").split("#", 1)[0].strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith(("-r ", "--requirement", "-c ", "--constraint",
                               "-e ", "--editable", "--index-url",
                               "--extra-index-url", "--find-links", "-f ")):
            continue
        if line.startswith(("http://", "https://", "git+", "file:")):
            continue
        specs.append(line)
    return specs


def requirement_name(spec):
    """Extract the distribution name from a requirement spec."""
    match = _NAME_RE.match(spec.strip())
    return match.group(0) if match else ""


def _normalized(name):
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def is_installed(spec):
    name = requirement_name(spec)
    if not name:
        return True
    try:
        _metadata.version(name)
        return True
    except _metadata.PackageNotFoundError:
        return False
    except Exception:
        # Unknown metadata problems should not block startup.
        return True


def missing_requirements(path=REQUIREMENTS_FILE):
    """Return the requirement specs that are not installed, deduplicated."""
    seen = set()
    missing = []
    for spec in read_requirements(path):
        name = requirement_name(spec)
        key = _normalized(name)
        if not key or key in seen:
            continue
        seen.add(key)
        if not is_installed(spec):
            missing.append(spec)
    return missing


def _upgrade_pip():
    _log("[deps] pip is missing; bootstrapping it with ensurepip...")
    try:
        subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"],
                       check=False)
    except Exception as exc:
        _log(f"[deps] Could not run ensurepip: {exc}")


# Packages that already power working VODER features (CUDA torch, the numpy
# ABI, transformers, protobuf, Qt).  Some old pins in requirements.txt would
# make pip downgrade them - descript-audiotools asks for protobuf<3.20, for
# example - which silently breaks every feature that already worked.  Installs
# therefore run with a constraints file that holds these packages at the
# version that is installed right now.
_PROTECTED_PACKAGES = (
    "torch", "torchaudio", "torchvision", "numpy", "scipy", "protobuf",
    "transformers", "tokenizers", "huggingface-hub", "PyQt5",
)


def _write_constraints_file():
    """Pin the packages VODER already relies on; return the file path."""
    import tempfile

    lines = []
    for name in _PROTECTED_PACKAGES:
        try:
            version = _metadata.version(name)
        except Exception:
            continue
        lines.append(f"{name}=={version}")
    if not lines:
        return None
    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".txt", prefix="voder-constraints-", delete=False, encoding="utf-8"
    )
    handle.write("\n".join(lines) + "\n")
    handle.close()
    return handle.name


def _start_pip(cmd):
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )


# Inference-only packages.  f5-tts and habibi-tts declare their whole training
# and demo stack (gradio, wandb, datasets, bitsandbytes) and installing that
# would also drag transformers/huggingface-hub to incompatible versions.  VODER
# imports neither, so these are installed without their dependency metadata.
_NO_DEPS_PACKAGES = {
    "f5-tts", "habibi-tts", "vocos", "encodec", "torchdiffeq", "pypinyin",
    "rjieba",
}


def _pip_install(spec, constraints_path=None):
    """Install one requirement, streaming pip's output line by line.

    A dropped download is retried once before the package is reported as
    failed, because the first run on a new machine pulls a lot of wheels.
    """
    cmd = [sys.executable, "-m", "pip", "install",
           "--disable-pip-version-check", "--no-input", "--prefer-binary",
           "--retries", "5", "--timeout", "60"]
    if constraints_path:
        cmd += ["-c", constraints_path]
    if _normalized(requirement_name(spec)) in _NO_DEPS_PACKAGES:
        cmd.append("--no-deps")
    cmd.append(spec)

    _log("")
    code = -1
    build_error = False
    for attempt in (1, 2):
        _log(f"[deps] Installing {spec} ..." + (" (retry)" if attempt == 2 else ""))
        try:
            process = _start_pip(cmd)
        except FileNotFoundError:
            _upgrade_pip()
            try:
                process = _start_pip(cmd)
            except Exception as exc:
                _log(f"[deps] FAILED to start pip: {exc}")
                return False
        except Exception as exc:
            _log(f"[deps] FAILED to start pip: {exc}")
            return False

        conflict = False
        network = False
        for line in process.stdout:
            line = line.rstrip()
            if not line:
                continue
            lowered = line.lower()
            if ("resolutionimpossible" in lowered
                    or "cannot install" in lowered
                    or "conflicting dependencies" in lowered
                    or "incompatible" in lowered):
                conflict = True
            if ("timed out" in lowered or "connection" in lowered
                    or "temporary failure" in lowered or "read time" in lowered):
                network = True
            if ("failed building wheel" in lowered
                    or "microsoft visual c++" in lowered
                    or "error c1083" in lowered
                    or "failed to build" in lowered):
                build_error = True
            _log("    " + line)
        code = process.wait()

        if code == 0:
            _log(f"[deps] Done: {spec}")
            importlib.invalidate_caches()
            return True

        if attempt == 1 and network and not conflict:
            _log("[deps] Download problem - trying once more.")
            continue
        break

    if conflict:
        _log(f"[deps] FAILED: {spec} needs a package version that would break")
        _log("[deps]         the packages you already have, so it was left alone.")
    elif build_error:
        _log(f"[deps] FAILED: {spec} has no ready-made Windows build and could")
        _log("[deps]         not compile. Install the Visual Studio Build Tools")
        _log("[deps]         ('Desktop development with C++') and try again.")
    else:
        _log(f"[deps] FAILED: {spec} (pip exit code {code})")
    return False


def ensure_dependencies(requirements_path=None, check_only=False, quiet=False, force=False):
    """Install every requirement that is missing.

    Returns True when nothing is missing at the end, False when at least one
    package could not be installed.  Set VODER_SKIP_DEPS=1 to bypass the
    check entirely.  ``force`` retries packages that failed recently.
    """
    if os.environ.get("VODER_SKIP_DEPS", "").strip().lower() in ("1", "true", "yes", "on"):
        if not quiet:
            _log("[deps] Dependency check skipped (VODER_SKIP_DEPS is set).")
        return True

    path = requirements_path or REQUIREMENTS_FILE
    if not os.path.isfile(path):
        if not quiet:
            _log(f"[deps] requirements.txt not found at {path}; skipping.")
        return True

    missing = missing_requirements(path)
    if not missing:
        if not quiet:
            _log("[deps] All required packages are installed.")
        return True

    failures = _load_failures()
    skipped = [spec for spec in missing if not force and _recently_failed(spec, failures)]
    missing = [spec for spec in missing if spec not in skipped]

    if skipped and not quiet:
        _log("[deps] Skipping package(s) that failed recently: "
             + ", ".join(skipped))
        _log("[deps] Run 'python voder.py deps --force' to try them again now.")

    if not missing:
        if not quiet:
            _log("[deps] Everything else is installed; VODER can continue.")
        return False

    if not quiet:
        _banner("installing missing dependencies")
        _log(f"[deps] Found {len(missing)} missing package(s):")
        for spec in missing:
            _log(f"[deps]   - {spec}")
        _log("[deps] They will be installed now. The first run can take a while.")

    if check_only:
        return False

    constraints_path = _write_constraints_file()
    failed = []
    total = len(missing)
    started = _time.monotonic()
    try:
        for index, spec in enumerate(missing, start=1):
            if not quiet:
                _log("")
                _log(f"[deps] --- {index}/{total} --- {spec} ---")
            if _pip_install(spec, constraints_path):
                _clear_failure(spec, failures)
            else:
                failed.append(spec)
                _record_failure(spec, failures)
    finally:
        if constraints_path:
            try:
                os.unlink(constraints_path)
            except OSError:
                pass

    elapsed = _time.monotonic() - started

    # Some packages provide import names that differ from the distribution
    # name; re-check using metadata to report an accurate final state.
    still_missing = missing_requirements(path)
    if not quiet:
        if still_missing:
            _log("")
            _banner("dependency installation incomplete")
            _log(f"[deps] Installed {total - len(still_missing)}/{total} package(s) "
                 f"in {elapsed:.0f}s.")
            _log("[deps] These packages are still missing:")
            for spec in still_missing:
                _log(f"[deps]   - {spec}")
            _log("[deps] Everything else still works. Run 'python voder.py deps'")
            _log("[deps] after fixing the errors above to try them again.")
        else:
            _banner("dependencies ready")
            _log(f"[deps] Installed {total} package(s) in {elapsed:.0f}s. "
                 "VODER can continue.")
    return not still_missing


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    check_only = "--check" in argv or "--missing" in argv
    force = "--force" in argv
    ok = ensure_dependencies(check_only=check_only, force=force)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
