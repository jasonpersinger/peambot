#!/usr/bin/env python3
"""
Train a wake word classifier for "Hey Peambot" using openWakeWord embeddings.

Architecture:
  1. openWakeWord's AudioFeatures preprocessor extracts embeddings (96-dim per frame)
     from raw 16kHz audio via melspectrogram + Google speech_embedding ONNX model.
  2. A sklearn LogisticRegression classifier (wrapped in Pipeline with StandardScaler)
     is trained on flattened embedding sequences (16 frames × 96 dims = 1536 features).
  3. The pipeline is exported to ONNX via skl2onnx.
"""

import os
import sys
import glob
import warnings
import numpy as np
import soundfile as sf
from pathlib import Path

# Suppress CUDA warnings from onnxruntime
warnings.filterwarnings("ignore", category=UserWarning)
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

from openwakeword.model import Model
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

# ─── Paths ───────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
POSITIVE_DIR = REPO_ROOT / "wake-word-training" / "positive"
OUTPUT_ONNX = REPO_ROOT / "wake-word-training" / "hey_peambot.onnx"

# Number of embedding frames to use per sample (each frame = 80ms, 16 frames ~ 1.3s)
N_FRAMES = 16
EMBED_DIM = 96
N_FEATURES = N_FRAMES * EMBED_DIM  # 1536

# ─── Embedding extraction ─────────────────────────────────────────────────────

def load_wav_as_int16(path: str) -> np.ndarray:
    """Load a WAV file and return as int16 mono 16kHz array."""
    data, sr = sf.read(path, dtype="int16", always_2d=False)
    if data.ndim > 1:
        data = data[:, 0]
    if sr != 16000:
        raise ValueError(f"Expected 16kHz audio, got {sr}Hz in {path}")
    return data


def extract_embedding_for_wav(wav_path: str, model: Model) -> np.ndarray | None:
    """
    Run a WAV file through the openWakeWord feature extractor and return
    a flat feature vector of shape (N_FRAMES * EMBED_DIM,).

    After calling model.predict() with audio chunks, the embeddings are
    stored in model.preprocessor.feature_buffer (shape: [n, 96]).
    We take the last N_FRAMES rows and flatten them.
    """
    try:
        audio = load_wav_as_int16(wav_path)
    except Exception as e:
        print(f"  [SKIP] {wav_path}: {e}")
        return None

    if len(audio) < 1280:
        # Pad to minimum chunk size
        audio = np.pad(audio, (0, 1280 - len(audio)))

    # Record initial feature buffer size so we know what's new
    initial_buf_len = model.preprocessor.feature_buffer.shape[0]

    # Feed in 1280-sample chunks (80ms each)
    chunk_size = 1280
    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i + chunk_size]
        if len(chunk) < chunk_size:
            chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
        model.predict(chunk)

    # Grab last N_FRAMES from the feature buffer
    buf = model.preprocessor.feature_buffer
    if buf.shape[0] < N_FRAMES:
        # Not enough frames generated — pad with zeros
        pad = np.zeros((N_FRAMES - buf.shape[0], EMBED_DIM), dtype=np.float32)
        frames = np.vstack([pad, buf])
    else:
        frames = buf[-N_FRAMES:, :]

    return frames.flatten().astype(np.float32)


def reset_model_state(model: Model):
    """Reset the model's feature buffer and prediction buffer between samples."""
    model.reset()
    # Re-initialize feature buffer with blank embeddings
    model.preprocessor.feature_buffer = model.preprocessor._get_embeddings(
        np.zeros(160000, dtype=np.int16)
    )
    model.preprocessor.accumulated_samples = 0
    model.preprocessor.melspectrogram_buffer = np.ones((76, 32))


# ─── Background noise generation ─────────────────────────────────────────────

def generate_noise_wav(duration_sec: float = 3.0, sr: int = 16000,
                       noise_type: str = "white") -> np.ndarray:
    """Generate synthetic background noise as int16 array."""
    n = int(duration_sec * sr)
    if noise_type == "white":
        samples = np.random.randn(n)
    elif noise_type == "pink":
        # Simple pink noise via 1/f approximation
        f = np.fft.rfftfreq(n)
        f[0] = 1.0
        power = 1.0 / np.sqrt(f)
        spectrum = power * np.exp(2j * np.pi * np.random.rand(len(f)))
        samples = np.fft.irfft(spectrum, n=n)
    elif noise_type == "brown":
        white = np.random.randn(n)
        samples = np.cumsum(white)
    else:
        samples = np.zeros(n)

    # Normalize to moderate amplitude
    if np.max(np.abs(samples)) > 0:
        samples = samples / np.max(np.abs(samples)) * 0.3

    return (samples * 32767).astype(np.int16)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=== Hey Peambot Wake Word Training ===\n")

    # 1. Load openWakeWord model (base, no custom models needed)
    print("[1] Loading openWakeWord feature extractor...")
    model = Model()
    print(f"    Feature buffer dim: {EMBED_DIM}, using {N_FRAMES} frames → {N_FEATURES} features\n")

    # 2. Extract positive embeddings
    print("[2] Extracting embeddings from positive samples...")
    positive_wavs = sorted(glob.glob(str(POSITIVE_DIR / "*.wav")))
    if not positive_wavs:
        print(f"ERROR: No WAV files found in {POSITIVE_DIR}")
        sys.exit(1)
    print(f"    Found {len(positive_wavs)} positive samples")

    positive_embeddings = []
    for i, wav_path in enumerate(positive_wavs):
        reset_model_state(model)
        emb = extract_embedding_for_wav(wav_path, model)
        if emb is not None:
            positive_embeddings.append(emb)
        if (i + 1) % 50 == 0:
            print(f"    Processed {i + 1}/{len(positive_wavs)}")

    print(f"    Extracted {len(positive_embeddings)} positive embeddings\n")

    # 3. Extract negative embeddings from background noise
    print("[3] Generating background noise samples...")
    noise_types = ["white", "pink", "brown", "silence"]
    negative_embeddings = []
    # Generate 500 noise samples (matching positive count)
    target_negatives = min(500, len(positive_embeddings))
    per_type = target_negatives // len(noise_types) + 1

    noise_idx = 0
    for ntype in noise_types:
        for _ in range(per_type):
            if noise_idx >= target_negatives:
                break
            reset_model_state(model)
            # Vary duration to get diverse samples
            duration = np.random.choice([1.0, 2.0, 3.0, 5.0])
            audio = generate_noise_wav(duration_sec=duration, noise_type=ntype)
            # Feed chunks to the model
            chunk_size = 1280
            for i in range(0, len(audio), chunk_size):
                chunk = audio[i:i + chunk_size]
                if len(chunk) < chunk_size:
                    chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
                model.predict(chunk)

            buf = model.preprocessor.feature_buffer
            if buf.shape[0] < N_FRAMES:
                pad = np.zeros((N_FRAMES - buf.shape[0], EMBED_DIM), dtype=np.float32)
                frames = np.vstack([pad, buf])
            else:
                frames = buf[-N_FRAMES:, :]

            negative_embeddings.append(frames.flatten().astype(np.float32))
            noise_idx += 1

    print(f"    Generated {len(negative_embeddings)} negative (background noise) embeddings\n")

    # 4. Build dataset
    print("[4] Building training dataset...")
    X_pos = np.array(positive_embeddings)
    X_neg = np.array(negative_embeddings)
    X = np.vstack([X_pos, X_neg])
    y = np.hstack([
        np.ones(len(positive_embeddings), dtype=int),
        np.zeros(len(negative_embeddings), dtype=int)
    ])
    print(f"    Total samples: {len(X)} ({len(positive_embeddings)} positive, {len(negative_embeddings)} negative)")
    print(f"    Feature shape: {X.shape}\n")

    # 5. Train classifier
    print("[5] Training LogisticRegression pipeline...")
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced"))
    ])
    pipeline.fit(X, y)

    train_acc = pipeline.score(X, y)
    print(f"    Training accuracy: {train_acc:.4f} ({train_acc * 100:.1f}%)")

    # Cross-validation score
    cv_scores = cross_val_score(pipeline, X, y, cv=5, scoring="accuracy")
    print(f"    5-fold CV accuracy: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}\n")

    # 6. Export to ONNX
    print("[6] Exporting pipeline to ONNX...")
    initial_type = [("input", FloatTensorType([None, N_FEATURES]))]
    onnx_model = convert_sklearn(
        pipeline,
        initial_types=initial_type,
        target_opset=12,
    )
    OUTPUT_ONNX.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_ONNX, "wb") as f:
        f.write(onnx_model.SerializeToString())

    print(f"    Saved: {OUTPUT_ONNX}")
    print(f"    File size: {OUTPUT_ONNX.stat().st_size / 1024:.1f} KB\n")

    # 7. Verify ONNX
    print("[7] Verifying ONNX model...")
    import onnxruntime as ort
    sess = ort.InferenceSession(str(OUTPUT_ONNX))
    inputs = [i.name for i in sess.get_inputs()]
    outputs = [o.name for o in sess.get_outputs()]
    print(f"    Inputs:  {inputs}")
    print(f"    Outputs: {outputs}")

    # Test inference
    test_input = np.zeros((1, N_FEATURES), dtype=np.float32)
    pred = sess.run(None, {"input": test_input})
    print(f"    Test inference output shapes: {[getattr(p, 'shape', type(p).__name__) for p in pred]}")
    print("\n=== Training complete ===")
    print(f"Training accuracy: {train_acc:.4f}")
    if train_acc < 0.75:
        print("WARNING: Training accuracy below 0.75 threshold!")
        sys.exit(2)


if __name__ == "__main__":
    main()
