"""
Speaker embeddings for offline diarisation.

Backends, in preference order. All return L2-normalised vectors so a plain dot
product is the cosine similarity used by the clustering stage.

* ``ecapa``    — ECAPA-TDNN from ``speechbrain/spkrec-ecapa-voxceleb``. This is the
  embedding model pyannote's offline diarisation pipeline uses; small (21M params),
  fast on CPU and strongly speaker-discriminative.
* ``xvector``  — WavLM base+ speaker-verification head via ``transformers``.
  Self-supervised alternative, useful when speechbrain is unavailable.
* ``mfcc``     — statistical MFCC signature (mean/std of MFCC and its delta).
  Last resort so diarisation degrades in accuracy instead of failing outright.

Embeddings are averaged over sliding windows rather than computed on the whole
region at once: it keeps memory bounded for long regions and matches the
multi-frame embedding aggregation used by standard diarisation pipelines.
"""
import logging
import os
import tempfile
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

WINDOW_SEC = 1.5
WINDOW_HOP_SEC = 0.5
MAX_EMBEDDING_SEC = 30.0

ECAPA_MODEL_ID = "speechbrain/spkrec-ecapa-voxceleb"
XVECTOR_MODEL_ID = "microsoft/wavlm-base-plus-sv"


class SpeakerEmbedder:
    """Lazily-loaded speaker embedding extractor with graceful degradation."""

    def __init__(self, model_id: str = ECAPA_MODEL_ID):
        self.model_id = model_id
        self.backend: Optional[str] = None
        self._model = None
        self._feature_extractor = None
        self._tried: set = set()

    # ── loading ──────────────────────────────────────────────────────────
    def load(self) -> Optional[str]:
        """Loads the best available backend. Returns its name, or None."""
        if self.backend is not None:
            return self.backend
        if "ecapa" not in self._tried:
            self._tried.add("ecapa")
            if self._load_ecapa():
                self.backend = "ecapa"
                logger.info("Speaker embedder ready: ECAPA-TDNN (%s)", self.model_id)
                return self.backend
        if "xvector" not in self._tried:
            self._tried.add("xvector")
            if self._load_xvector():
                self.backend = "xvector"
                logger.info("Speaker embedder ready: WavLM x-vector (%s)", XVECTOR_MODEL_ID)
                return self.backend
        return None

    def _load_ecapa(self) -> bool:
        try:
            from speechbrain.inference.speaker import EncoderClassifier
            from speechbrain.utils.fetching import LocalStrategy

            savedir = os.path.join(
                tempfile.gettempdir(), "diarizestudio", os.path.basename(self.model_id)
            )
            kwargs = {"source": self.model_id, "run_opts": {"device": "cpu"}}
            try:
                # Windows without Developer Mode cannot create symlinks.
                self._model = EncoderClassifier.from_hparams(
                    savedir=savedir, local_strategy=LocalStrategy.COPY_SKIP_CACHE, **kwargs
                )
            except Exception:  # noqa: BLE001 - older/newer speechbrain signatures
                self._model = EncoderClassifier.from_hparams(
                    savedir=savedir, local_strategy=LocalStrategy.COPY, **kwargs
                )
            self._model.eval()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.info("ECAPA-TDNN unavailable (%s); trying WavLM x-vector", exc)
            return False

    def _load_xvector(self) -> bool:
        if self.model_id != ECAPA_MODEL_ID:
            # A specific non-ECAPA model was requested: honour it directly.
            model_id = self.model_id
        else:
            model_id = XVECTOR_MODEL_ID
        try:
            from transformers import AutoFeatureExtractor, WavLMForXVector

            offline = os.environ.get("DIARIZATION_OFFLINE", "1") == "1"
            self._feature_extractor = AutoFeatureExtractor.from_pretrained(model_id, local_files_only=offline)
            self._model = WavLMForXVector.from_pretrained(model_id, local_files_only=offline)
            self._model.eval()
            self.model_id = model_id
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Neural speaker embedder unavailable (%s); using MFCC signatures", exc)
            return False

    # ── embedding ────────────────────────────────────────────────────────
    def embed_windows(self, y: np.ndarray, sr: int) -> np.ndarray:
        """Returns an (n_windows, dim) matrix of L2-normalised window embeddings."""
        backend = self.load()
        if backend == "ecapa":
            try:
                return self._embed_ecapa(y, sr)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ECAPA extraction failed (%s); falling back", exc)
        if backend == "xvector":
            try:
                return self._embed_xvector(y, sr)
            except Exception as exc:  # noqa: BLE001
                logger.warning("x-vector extraction failed (%s); falling back to MFCC", exc)
        return self._embed_mfcc(y, sr)

    def embed(self, y: np.ndarray, sr: int) -> np.ndarray:
        """Single L2-normalised embedding for one region (mean of its windows)."""
        vecs = self.embed_windows(y, sr)
        if vecs.shape[0] == 0:
            return np.zeros(1, dtype=np.float32)
        mean = vecs.mean(axis=0)
        norm = float(np.linalg.norm(mean))
        return (mean / norm).astype(np.float32) if norm > 1e-8 else mean.astype(np.float32)

    # ── backends ─────────────────────────────────────────────────────────
    def _embed_ecapa(self, y: np.ndarray, sr: int) -> np.ndarray:
        import torch

        windows = _sliding_windows(y, sr)
        if not windows:
            return np.zeros((0, 1), dtype=np.float32)
        out: List[np.ndarray] = []
        with torch.inference_mode():
            for batch in _batched(windows, 8):
                wav_lens = torch.tensor([w.shape[0] for w in batch], dtype=torch.float32)
                stacked = torch.nn.utils.rnn.pad_sequence(
                    [torch.from_numpy(w.astype(np.float32)) for w in batch], batch_first=True
                )
                vecs = self._model.encode_batch(stacked, wav_lens=wav_lens)
                vecs = torch.nn.functional.normalize(vecs.reshape(len(batch), -1), dim=-1)
                out.append(vecs.cpu().numpy())
        return np.concatenate(out, axis=0).astype(np.float32)

    def _embed_xvector(self, y: np.ndarray, sr: int) -> np.ndarray:
        import torch

        windows = _sliding_windows(y, sr)
        if not windows:
            return np.zeros((0, 1), dtype=np.float32)
        out: List[np.ndarray] = []
        with torch.inference_mode():
            for batch in _batched(windows, 8):
                inputs = self._feature_extractor(
                    [w.astype(np.float32) for w in batch],
                    sampling_rate=sr,
                    return_tensors="pt",
                    padding=True,
                )
                emb = self._model(**inputs).embeddings
                emb = torch.nn.functional.normalize(emb, dim=-1)
                out.append(emb.cpu().numpy())
        return np.concatenate(out, axis=0).astype(np.float32)

    def _embed_mfcc(self, y: np.ndarray, sr: int) -> np.ndarray:
        import librosa

        windows = _sliding_windows(y, sr)
        if not windows:
            return np.zeros((0, 1), dtype=np.float32)
        out: List[np.ndarray] = []
        for w in windows:
            mfcc = librosa.feature.mfcc(y=w.astype(np.float32), sr=sr, n_mfcc=24)
            delta = librosa.feature.delta(mfcc)
            out.append(
                np.concatenate([mfcc.mean(axis=1), mfcc.std(axis=1), delta.mean(axis=1)]).astype(np.float32)
            )
        mat = np.stack(out, axis=0)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms < 1e-8] = 1.0
        return (mat / norms).astype(np.float32)


def _sliding_windows(y: np.ndarray, sr: int) -> List[np.ndarray]:
    """1.5 s windows every 0.5 s, clipped to at most MAX_EMBEDDING_SEC of audio."""
    if y is None or len(y) < int(0.25 * sr):
        return []
    y = y[: int(MAX_EMBEDDING_SEC * sr)]
    win = int(WINDOW_SEC * sr)
    hop = int(WINDOW_HOP_SEC * sr)
    if len(y) <= win:
        return [y]
    windows = [y[i : i + win] for i in range(0, len(y) - win + 1, hop)]
    return windows or [y[:win]]


def _batched(items: List[np.ndarray], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]
