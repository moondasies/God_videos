"""Free, offline vocal isolation with the UVR MDX-Net model Kim_Vocal_2 (ONNX).

Removes music beds / background ambience under a voice recording. Runs on CPU.

    python -m anime.separate in.mp3 out_vocals.wav

Model: https://github.com/TRvlvr/model_repo/releases (all_public_uvr_models/Kim_Vocal_2.onnx)
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import onnxruntime as ort
import soundfile as sf
import torch

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "models" / "sep" / "Kim_Vocal_2.onnx"
SR = 44100
N_FFT, HOP, DIM_F, DIM_T = 7680, 1024, 3072, 256
COMPENSATE = 1.009


def load_stereo(path):
    with tempfile.TemporaryDirectory() as td:
        w = Path(td) / "a.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path), "-ac", "2", "-ar", str(SR), str(w)], check=True)
        x, _ = sf.read(w, dtype="float32")
    return x.T  # (2, n)


def separate_vocals(path, model=MODEL):
    mix = load_stereo(path)
    n = mix.shape[1]
    chunk = HOP * (DIM_T - 1)
    trim = N_FFT // 2
    gen = chunk - 2 * trim
    pad = gen - n % gen
    mix_p = np.concatenate([np.zeros((2, trim), np.float32), mix, np.zeros((2, pad + trim), np.float32)], 1)
    window = torch.hann_window(N_FFT, periodic=True)
    sess = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    out = []
    for i in range(0, n + pad, gen):
        w = torch.from_numpy(mix_p[:, i:i + chunk].copy())
        spec = torch.stft(w, N_FFT, HOP, window=window, center=True, return_complex=True)  # (2, bins, t)
        x = torch.view_as_real(spec).permute(0, 3, 1, 2).reshape(1, 4, -1, DIM_T)[:, :, :DIM_F]
        y = torch.from_numpy(sess.run(None, {"input": x.numpy()})[0])
        y = torch.cat([y, torch.zeros(1, 4, N_FFT // 2 + 1 - DIM_F, DIM_T)], 2)
        y = y.reshape(2, 2, -1, DIM_T).permute(0, 2, 3, 1).contiguous()
        wav = torch.istft(torch.view_as_complex(y), N_FFT, HOP, window=window, center=True, length=chunk)
        out.append(wav[:, trim:-trim].numpy())
    voc = np.concatenate(out, 1)[:, :n] * COMPENSATE
    return voc, SR


def main(argv=None):
    a = argv or sys.argv[1:]
    voc, sr = separate_vocals(a[0])
    sf.write(a[1], voc.T, sr)
    print("vocals ->", a[1])


if __name__ == "__main__":
    main()
