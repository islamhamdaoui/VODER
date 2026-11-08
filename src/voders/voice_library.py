"""Persistent voice profile library for VODER.

Voice clones trained by VODER are stored as files in the project ``voices``
folder (``.tts`` for standard voices, ``.ttse`` for enhanced voices).  This
module is the single place that discovers those files, so the GUI and the CLI
always agree about which voices exist and where they are.

It only uses the Python standard library, so it can safely be imported by the
GUI without pulling in torch or any model code.
"""

import os
import re
import time

# app/src/voders/voice_library.py  ->  app/src/voders -> app/src -> app -> repo
_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.dirname(_PACKAGE_DIR)
APP_DIR = os.path.dirname(_SRC_DIR)
PROJECT_ROOT = os.environ.get("VODER_HOME") or os.path.dirname(APP_DIR)

VOICE_EXTENSIONS = (".tts", ".ttse")
KIND_STANDARD = "standard"
KIND_ENHANCED = "enhanced"
_KIND_ORDER = {KIND_STANDARD: 0, KIND_ENHANCED: 1}

_FILENAME_RE = re.compile(r"^voder_(tts|ttse)_(.+?)_(\d{8}_\d{6})$", re.IGNORECASE)


def voices_dir():
    """The canonical folder new voice profiles are written to."""
    return os.path.join(PROJECT_ROOT, "voices")


def voice_search_dirs():
    """Every folder searched for voice profiles (canonical first).

    Old VODER versions stored voices next to the source tree when the GUI was
    launched from ``app/src``; those folders are still scanned so existing
    voices are never lost.
    """
    candidates = [
        voices_dir(),
        os.path.join(os.getcwd(), "voices"),
        os.path.join(_SRC_DIR, "voices"),
        os.path.join(APP_DIR, "voices"),
    ]
    seen = set()
    result = []
    for path in candidates:
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            continue
        seen.add(key)
        result.append(os.path.abspath(path))
    return result


def ensure_voices_dir():
    os.makedirs(voices_dir(), exist_ok=True)
    return voices_dir()


def sanitize_voice_name(name):
    """Turn user input into a safe, predictable voice name."""
    name = (name or "").strip().lower()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" ._-")
    return name[:60]


def _split_filename(path):
    """Return (name, kind, timestamp, extension) parsed from a voice file."""
    base = os.path.basename(path)
    stem, ext = os.path.splitext(base)
    ext = ext.lower()
    match = _FILENAME_RE.match(stem)
    if match:
        kind = KIND_ENHANCED if match.group(1).lower() == "ttse" else KIND_STANDARD
        return match.group(2), kind, match.group(3), ext
    kind = KIND_ENHANCED if ext == ".ttse" else KIND_STANDARD
    return stem, kind, "", ext


class VoiceProfile:
    """One saved voice on disk (a single .tts or .ttse file)."""

    __slots__ = ("name", "path", "kind", "timestamp", "modified", "size")

    def __init__(self, name, path, kind, timestamp, modified, size):
        self.name = name
        self.path = path
        self.kind = kind
        self.timestamp = timestamp
        self.modified = modified
        self.size = size

    @property
    def display_name(self):
        if not self.name:
            return os.path.basename(self.path)
        return self.name[:1].upper() + self.name[1:]

    @property
    def kind_label(self):
        return "Enhanced" if self.kind == KIND_ENHANCED else "Standard"

    @property
    def is_enhanced(self):
        return self.kind == KIND_ENHANCED

    def describe(self):
        try:
            stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(self.modified))
        except Exception:
            stamp = ""
        return f"{self.display_name} - {self.kind_label} voice ({stamp})"

    def __repr__(self):
        return f"VoiceProfile(name={self.name!r}, kind={self.kind!r}, path={self.path!r})"


def list_voices(include_legacy=True):
    """Return every saved voice, newest file wins for each name + kind."""
    found = {}
    dirs = voice_search_dirs() if include_legacy else [voices_dir()]
    for folder in dirs:
        try:
            entries = os.listdir(folder)
        except OSError:
            continue
        for filename in entries:
            if not filename.lower().endswith(VOICE_EXTENSIONS):
                continue
            path = os.path.join(folder, filename)
            try:
                if not os.path.isfile(path):
                    continue
                stat = os.stat(path)
            except OSError:
                continue
            name, kind, timestamp, _ext = _split_filename(path)
            if not name:
                continue
            profile = VoiceProfile(name, os.path.abspath(path), kind, timestamp,
                                   stat.st_mtime, stat.st_size)
            key = (name.casefold(), kind)
            previous = found.get(key)
            if previous is None or profile.modified > previous.modified:
                found[key] = profile
    return sorted(
        found.values(),
        key=lambda p: (p.name.casefold(), _KIND_ORDER.get(p.kind, 9)),
    )


def group_voices(voices=None):
    """Group profiles by name: {folded_name: {name, kinds, profiles}}."""
    groups = {}
    for profile in (voices if voices is not None else list_voices()):
        key = profile.name.casefold()
        group = groups.setdefault(
            key, {"name": profile.name, "kinds": set(), "profiles": []}
        )
        group["profiles"].append(profile)
        group["kinds"].add(profile.kind)
    return groups


def profiles_for_name(name):
    folded = (name or "").strip().casefold()
    return [p for p in list_voices() if p.name.casefold() == folded]


def find_voice(name, kind=None, prefer_enhanced=False):
    """Find a saved voice by name (case-insensitive). Returns a path or None."""
    raw = (name or "").strip().strip('"').strip("'")
    if not raw:
        return None

    # A direct path always wins.
    if os.path.isfile(raw):
        ext = os.path.splitext(raw)[1].lower()
        if ext in VOICE_EXTENSIONS:
            return os.path.abspath(raw)

    profiles = list_voices()
    folded = raw.casefold()
    matches = [p for p in profiles if p.name.casefold() == folded]

    if not matches:
        # Allow the user to paste the file stem or full file name.
        stem = os.path.splitext(os.path.basename(raw))[0].casefold()
        matches = [
            p for p in profiles
            if os.path.splitext(os.path.basename(p.path))[0].casefold() == stem
        ]

    if not matches:
        return None

    if kind:
        exact = [p for p in matches if p.kind == kind]
        if exact:
            matches = exact

    wanted = KIND_ENHANCED if prefer_enhanced else KIND_STANDARD
    matches.sort(key=lambda p: (0 if p.kind == wanted else 1,
                                -p.modified))
    return matches[0].path


def resolve_voice(value, prefer_enhanced=False):
    """Resolve a voice reference to a profile path.

    Accepts a saved voice name, ``Character: name`` (the form used by VODER's
    command line), a file name, or a full path.  Returns None when the value is
    not a saved voice profile.
    """
    raw = (value or "").strip().strip('"').strip("'")
    if not raw:
        return None

    direct = find_voice(raw, prefer_enhanced=prefer_enhanced)
    if direct:
        return direct

    if ":" in raw:
        after = raw.split(":", 1)[1].strip().strip('"').strip("'")
        if after:
            found = find_voice(after, prefer_enhanced=prefer_enhanced)
            if found:
                return found
    return None


def is_voice_profile(value):
    return resolve_voice(value) is not None


def rename_voice(path, new_name):
    """Rename a saved voice file. Returns the new path, or None on failure."""
    source = os.path.abspath(path or "")
    if not os.path.isfile(source):
        return None
    ext = os.path.splitext(source)[1].lower()
    if ext not in VOICE_EXTENSIONS:
        return None
    clean = sanitize_voice_name(new_name)
    if not clean:
        return None

    _old_name, _kind, timestamp, _ext = _split_filename(source)
    if not timestamp:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
    kind_tag = "ttse" if ext == ".ttse" else "tts"
    destination = os.path.join(
        os.path.dirname(source), f"voder_{kind_tag}_{clean}_{timestamp}{ext}"
    )
    if os.path.normcase(destination) == os.path.normcase(source):
        return source
    if os.path.exists(destination):
        return None
    try:
        os.rename(source, destination)
    except OSError:
        return None
    return destination


def delete_voice(path):
    """Delete a saved voice file. Returns True when the file is gone."""
    target = os.path.abspath(path or "")
    if not os.path.isfile(target):
        return False
    try:
        os.remove(target)
    except OSError:
        return False
    return True


def open_voices_folder():
    folder = ensure_voices_dir()
    try:
        if os.name == "nt":
            os.startfile(folder)
        elif os.name == "posix":
            import subprocess
            opener = "open" if os.uname().sysname == "Darwin" else "xdg-open"  # noqa
            subprocess.Popen([opener, folder])
        return True
    except Exception:
        return False
