"""Small helpers for the external binaries VODER shells out to.

VODER calls ``ffmpeg`` from many places (dialogue assembly, SFX, speed changes,
music mixing).  On Windows ffmpeg is almost never on PATH, and the failure was
a confusing ``FileNotFoundError: [WinError 2]`` after the models had already
loaded.

``ensure_ffmpeg`` finds a system ffmpeg, or unpacks the one shipped by the
``imageio-ffmpeg`` wheel into a stable folder and prepends it to ``PATH`` so
every existing ``ffmpeg`` call keeps working unchanged.
"""

import os
import shutil
import sys

_BIN_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache"),
    "VODER",
    "bin",
)


def _local_ffmpeg():
    return os.path.join(_BIN_DIR, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")


def _install_from_imageio():
    """Copy the bundled ffmpeg into the VODER bin folder; return its path."""
    try:
        import imageio_ffmpeg
    except Exception:
        return None
    try:
        source = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None
    if not source or not os.path.isfile(source):
        return None

    target = _local_ffmpeg()
    try:
        os.makedirs(_BIN_DIR, exist_ok=True)
        if not os.path.isfile(target) or os.path.getsize(target) != os.path.getsize(source):
            shutil.copy2(source, target)
        try:
            os.chmod(target, 0o755)
        except OSError:
            pass
        return target
    except OSError:
        # Fall back to using the wheel copy in place.
        return source


def ensure_ffmpeg(verbose=False):
    """Make sure ``ffmpeg`` is callable; return its path or None.

    Adds the folder to ``PATH`` so that subprocess and ``os.system`` calls that
    only say ``ffmpeg`` work for this process and for everything it starts.
    """
    existing = shutil.which("ffmpeg")
    if existing:
        return existing

    path = _install_from_imageio()
    if not path:
        if verbose:
            print("[ffmpeg] ffmpeg was not found and imageio-ffmpeg is not installed.",
                  flush=True)
        return None

    folder = os.path.dirname(path)
    if folder and folder not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = folder + os.pathsep + os.environ.get("PATH", "")
    if verbose:
        print(f"[ffmpeg] using {path}", flush=True)
    return path


def has_ffprobe():
    return shutil.which("ffprobe") is not None
