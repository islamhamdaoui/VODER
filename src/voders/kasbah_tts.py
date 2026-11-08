"""Algerian Darija speech synthesis (KasbahTTS / F5-TTS).

The standard VODER TTS engine (Qwen) speaks ten languages and Arabic is not one
of them, so Algerian Dardja needed a separate model. KasbahTTS-V0 is an F5-TTS
fine-tune trained on real Algerian speech, released under the MIT licence at
https://huggingface.co/Voice213DZ/KasbahTTS-V0 (1.35 GB). It clones a voice
zero-shot from a short reference clip, exactly like the other engines.

The runtime is deliberately small: the inference part of ``f5-tts`` and
``habibi-tts`` plus five tiny pure-python packages (vocos, torchdiffeq,
pypinyin, rjieba, encodec). ``f5_tts.model.__init__`` imports the training
stack (wandb, datasets, gradio) which VODER never uses, so the helper below
registers the package namespace and imports only the submodules we need.
"""

import os
import re
import sys
import time
import types

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))          # app/src/voders
_SRC_DIR = os.path.dirname(_HERE)                           # app/src
APP_DIR = os.path.dirname(_SRC_DIR)                         # app
PROJECT_ROOT = os.environ.get("VODER_HOME") or os.path.dirname(APP_DIR)

MODELS_CHECKPOINTS_DIR = os.path.join(_SRC_DIR, "models", "checkpoints")
KASBAH_DIR = os.path.join(MODELS_CHECKPOINTS_DIR, "kasbah")
KASBAH_REPO = "Voice213DZ/KasbahTTS-V0"
KASBAH_CHECKPOINT = os.path.join(KASBAH_DIR, "ALGERIA.safetensors")
KASBAH_VOCAB = os.path.join(KASBAH_DIR, "vocab.txt")
KASBAH_SAMPLE_RATE = 24000
KASBAH_MAX_REF_SECONDS = 12.0
# F5-TTS picks the generation length from the reference, so text chunks must
# stay in the same league as the reference transcript (~200 bytes).
KASBAH_CHUNK_BYTES = 180

VOICE_EXTENSION = ".ttsdz"

_MODEL_CONFIG = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)

# Arabic letters, plus the punctuation the model was trained with.
_ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f]")
# Harakat, Quranic marks, superscript alef and tatweel: the model was trained
# on plain, unvocalised text and gets confused by them.
_DIACRITICS_RE = re.compile(r"[\u0640\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u08d3-\u08ff]")
_DIGITS_RE = re.compile(r"[0-9\u0660-\u0669\u06f0-\u06f9]")

_f5_cache = {}


def has_arabic(text):
    """True when the text contains at least one Arabic-script letter."""
    return bool(text) and bool(_ARABIC_RE.search(text))


def strip_diacritics(text):
    """Drop harakat/tatweel; KasbahTTS only understands unvocalised text."""
    return _DIACRITICS_RE.sub("", text or "")


def normalize_text(text):
    """Prepare text for KasbahTTS: unvocalised, no digits, single spaces."""
    text = strip_diacritics(text or "")
    # Newlines and tabs (pasted multi-line scripts) must become spaces; stray
    # control characters end up as unknown tokens in the model's vocabulary.
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def text_warnings(text):
    """Human-readable list of things KasbahTTS cannot pronounce."""
    warnings = []
    if _DIGITS_RE.search(text or ""):
        warnings.append("KasbahTTS cannot pronounce digits - write numbers as words.")
    if re.search(r"[A-Za-z]", text or ""):
        warnings.append("KasbahTTS speaks Arabic script only - French/Latin words will sound wrong.")
    if _DIACRITICS_RE.search(text or "") and text != strip_diacritics(text):
        warnings.append("Diacritics (harakat) are not supported - they were removed.")
    return warnings


def _load_f5_modules():
    """Import the F5-TTS inference pieces without its training stack."""
    if _f5_cache:
        return _f5_cache

    import f5_tts

    if "f5_tts.model" not in sys.modules:
        package = types.ModuleType("f5_tts.model")
        package.__path__ = [os.path.join(list(f5_tts.__path__)[0], "model")]
        sys.modules["f5_tts.model"] = package

        from f5_tts.model.backbones.dit import DiT
        from f5_tts.model.cfm import CFM

        package.CFM = CFM
        package.DiT = DiT

    from f5_tts.model import CFM, DiT
    from f5_tts.infer.utils_infer import (
        load_model,
        load_vocoder,
        preprocess_ref_audio_text,
    )
    from habibi_tts.infer.utils_infer import infer_process

    _f5_cache.update(
        DiT=DiT,
        CFM=CFM,
        load_model=load_model,
        load_vocoder=load_vocoder,
        preprocess_ref_audio_text=preprocess_ref_audio_text,
        infer_process=infer_process,
    )
    return _f5_cache


def ensure_model_files(verbose=True):
    """Download the KasbahTTS weights once (1.35 GB). Returns True on success."""
    if os.path.exists(KASBAH_CHECKPOINT) and os.path.exists(KASBAH_VOCAB):
        return True
    try:
        # The Xet transfer backend can hang on large files with no progress; the
        # classic HTTP downloader is slower but reliable.
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        from huggingface_hub import snapshot_download

        os.makedirs(KASBAH_DIR, exist_ok=True)
        if verbose:
            print("Downloading KasbahTTS-V0 (Algerian Darija, 1.35 GB) from HuggingFace...")
        snapshot_download(
            repo_id=KASBAH_REPO,
            local_dir=KASBAH_DIR,
            allow_patterns=["ALGERIA.safetensors", "vocab.txt", "README.md"],
        )
        return os.path.exists(KASBAH_CHECKPOINT) and os.path.exists(KASBAH_VOCAB)
    except Exception as exc:
        print(f"Error downloading KasbahTTS: {exc}")
        return False


class KasbahTTS:
    """Small wrapper around KasbahTTS (F5-TTS) for one voice at a time."""

    def __init__(self, model_dir=None):
        self.model_dir = model_dir or KASBAH_DIR
        self.checkpoint = os.path.join(self.model_dir, "ALGERIA.safetensors")
        self.vocab = os.path.join(self.model_dir, "vocab.txt")
        self.model = None
        self.vocoder = None
        self.device = None
        self.voice = None
        self._ref_path = None

    # -- model ------------------------------------------------------------
    def ensure_model(self):
        if self.model is not None:
            return True
        import torch

        if not (os.path.exists(self.checkpoint) and os.path.exists(self.vocab)):
            if not ensure_model_files():
                return False

        modules = _load_f5_modules()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        if self.vocoder is None:
            print("Loading the KasbahTTS vocoder...")
            self.vocoder = modules["load_vocoder"](
                vocoder_name="vocos", is_local=False, device=self.device
            )

        print("Loading KasbahTTS (Algerian Darija)...")
        self.model = modules["load_model"](
            modules["DiT"],
            dict(_MODEL_CONFIG),
            ckpt_path=self.checkpoint,
            vocab_file=self.vocab,
            use_ema=self._has_ema_weights(),
            device=self.device,
        )
        if self.device == "cuda" and self.model is not None:
            # f5-tts picks fp16 on any CUDA card, but Turing (sm75) overflows the
            # flow-matching ODE into a full-scale square wave. fp32 is correct
            # there and, without tensor cores, also faster.
            if torch.cuda.get_device_capability(0)[0] < 8:
                self.model = self.model.float()
        return self.model is not None

    def _has_ema_weights(self):
        try:
            from safetensors import safe_open

            with safe_open(self.checkpoint, framework="pt") as handle:
                return any("ema" in key.lower() for key in list(handle.keys())[:200])
        except Exception:
            return False

    # -- voice ------------------------------------------------------------
    def prepare_reference(self, audio_path):
        """Clip/normalise a recording to the 3-12s KasbahTTS expects.

        Returns the path of the prepared WAV, or None.  No model is loaded, so
        the caller can transcribe the *prepared* clip and get text that really
        matches it (a mismatch makes F5 truncate the generated speech).
        """
        modules = _load_f5_modules()
        try:
            prepared, _ignored = modules["preprocess_ref_audio_text"](
                audio_path, "clip", show_info=lambda *_: None
            )
            return prepared
        except Exception as exc:
            print(f"Error preparing the reference audio: {exc}")
            return None

    def extract_voice(self, audio_path, ref_text=""):
        """Store a reference clip + its transcript as the voice to clone."""
        if not normalize_text(ref_text):
            print("Error: no transcript for this reference recording.")
            print("KasbahTTS clones from a clip *and* its text, so the words must be known.")
            return False
        if not self.ensure_model():
            return False
        modules = _load_f5_modules()
        import soundfile as sf

        prepared, clean_text = modules["preprocess_ref_audio_text"](
            audio_path, normalize_text(ref_text), show_info=lambda *_: None
        )
        audio, sample_rate = sf.read(prepared, dtype="float32", always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sample_rate != KASBAH_SAMPLE_RATE:
            audio = _resample(audio, sample_rate, KASBAH_SAMPLE_RATE)
            sample_rate = KASBAH_SAMPLE_RATE

        seconds = len(audio) / float(sample_rate)
        if seconds < 3.0:
            print(f"Error: the reference is only {seconds:.1f}s; KasbahTTS needs 3-12s of speech.")
            return False

        if not strip_diacritics(clean_text).strip():
            print("Error: could not transcribe the reference recording.")
            print("Try a cleaner clip (one speaker, 3-12s), or run the same "
                  "command again with a manual transcript.")
            return False

        self._drop_reference_file()
        self.voice = {
            "audio": audio,
            "sample_rate": sample_rate,
            "text": strip_diacritics(clean_text).strip(),
        }
        print(f"KasbahTTS reference ready ({seconds:.1f}s).")
        return True

    def load_voice(self, profile):
        if not profile or profile.get("audio") is None:
            return False
        audio = profile["audio"]
        if hasattr(audio, "detach"):
            audio = audio.detach().cpu().numpy()
        self._drop_reference_file()
        self.voice = {
            "audio": np.asarray(audio, dtype=np.float32).reshape(-1),
            "sample_rate": int(profile.get("sample_rate") or KASBAH_SAMPLE_RATE),
            "text": profile.get("text", ""),
        }
        return True

    # -- speech -----------------------------------------------------------
    def synthesize(self, text, output_path):
        if not self.ensure_model():
            return False
        if not self.voice:
            print("Error: no KasbahTTS voice loaded")
            return False

        modules = _load_f5_modules()
        import soundfile as sf

        clean = normalize_text(text)
        if not clean:
            print("Error: nothing to say")
            return False
        for warning in text_warnings(text):
            print(f"Note: {warning}")

        pieces = []
        reference = self._reference_path()
        for chunk in _split_for_kasbah(clean):
            audio, sample_rate, _spec = modules["infer_process"](
                ref_audio=reference,
                ref_text=self.voice["text"],
                gen_text=chunk,
                model_obj=self.model,
                vocoder=self.vocoder,
                show_info=lambda *_: None,
                device=self.device,
            )
            pieces.append(np.asarray(audio, dtype=np.float32).reshape(-1))

        if not pieces:
            print("Error: synthesis produced no audio")
            return False

        final = _join(pieces, sample_rate, gap_seconds=0.06)
        # The vocoder targets an RMS level, so a few peaks can exceed 1.0 and
        # clip in the 16-bit WAV we write. Pull the whole clip down instead.
        peak = float(np.max(np.abs(final))) if final.size else 0.0
        if peak > 0.99:
            final = (final * (0.99 / peak)).astype(np.float32)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
        sf.write(output_path, final, sample_rate)
        return True

    def _reference_path(self):
        """Write the stored clip to a temporary WAV (infer_process reads paths)."""
        if self._ref_path and os.path.exists(self._ref_path):
            return self._ref_path
        import tempfile

        import soundfile as sf

        folder = tempfile.mkdtemp(prefix="voder_darija_")
        path = os.path.join(folder, "reference.wav")
        sf.write(path, self.voice["audio"], self.voice["sample_rate"])
        self._ref_path = path
        return path

    def _drop_reference_file(self):
        if not self._ref_path:
            return
        import shutil

        folder = os.path.dirname(self._ref_path)
        self._ref_path = None
        shutil.rmtree(folder, ignore_errors=True)

    def cleanup(self):
        import gc

        import torch

        self._drop_reference_file()
        self.model = None
        self.vocoder = None
        self.voice = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# -- profiles -------------------------------------------------------------

def save_voice_profile(voice, character_name, timestamp=None):
    """Write a self-contained ``.ttsdz`` profile (clip + transcript)."""
    import torch

    from .voice_library import ensure_voices_dir, sanitize_voice_name

    folder = ensure_voices_dir()
    name = sanitize_voice_name(character_name) or "voice"
    stamp = timestamp or time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(folder, f"voder_ttsdz_{name}_{stamp}.ttsdz")
    torch.save(
        {
            "kind": "darija",
            "audio": torch.from_numpy(np.ascontiguousarray(voice["audio"], dtype=np.float32)),
            "sample_rate": int(voice["sample_rate"]),
            "text": voice.get("text", ""),
            "character": name,
            "timestamp": stamp,
        },
        path,
    )
    return path


def load_voice_profile(path):
    import torch

    if not path or not os.path.exists(path):
        return None
    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except Exception as exc:
        print(f"Error reading Darija voice '{os.path.basename(path)}': {exc}")
        return None
    if not isinstance(payload, dict) or "audio" not in payload:
        return None
    return payload


def is_darija_profile(path):
    return bool(path) and str(path).lower().endswith(VOICE_EXTENSION)


# -- helpers --------------------------------------------------------------

def _resample(audio, source_rate, target_rate):
    if source_rate == target_rate:
        return audio
    try:
        import librosa

        return librosa.resample(audio, orig_sr=source_rate, target_sr=target_rate)
    except Exception:
        positions = np.linspace(0, len(audio) - 1, int(len(audio) * target_rate / source_rate))
        return np.interp(positions, np.arange(len(audio)), audio).astype(np.float32)


def _split_for_kasbah(text):
    """Split long text into chunks the model can actually handle.

    F5-TTS estimates how long the speech should be from the reference clip, so
    the reference (<= 12s, about 200 bytes of Arabic text) sets the scale.  A
    chunk much longer than that is out of distribution and the model starts to
    repeat or drift, so every chunk is kept under ~180 UTF-8 bytes.  Splitting
    happens at sentence/clause punctuation first, then at spaces.
    """
    text = (text or "").strip()
    if not text:
        return []
    if len(text.encode("utf-8")) <= KASBAH_CHUNK_BYTES:
        return [text]

    def fits(candidate):
        return len(candidate.encode("utf-8")) <= KASBAH_CHUNK_BYTES

    pieces, current = [], ""
    for unit in re.split(r"(?<=[.!?؟\u061f\u060c\u061b;:,])\s*", text):
        if not unit:
            continue
        joined = f"{current} {unit}".strip()
        if fits(joined):
            current = joined
            continue
        if current:
            pieces.append(current)
            current = ""
        if fits(unit):
            current = unit
            continue
        for word in unit.split():
            joined = f"{current} {word}".strip()
            if fits(joined):
                current = joined
            else:
                if current:
                    pieces.append(current)
                current = word
    if current:
        pieces.append(current)
    return pieces or [text]


def _join(pieces, sample_rate, gap_seconds=0.06):
    if len(pieces) == 1:
        return pieces[0]
    gap = np.zeros(int(sample_rate * gap_seconds), dtype=np.float32)
    out = [pieces[0]]
    for piece in pieces[1:]:
        out.extend([gap, piece])
    return np.concatenate(out)
