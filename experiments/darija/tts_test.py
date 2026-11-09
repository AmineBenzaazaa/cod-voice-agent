"""Synthesize agent lines in Darija with HADRA (F5-TTS fine-tune) and time it."""

import sys
import time

import soundfile as sf
import torch
import torchaudio


def _sf_load(path, *args, **kwargs):  # torchaudio's default loader needs FFmpeg libs we don't have
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    return torch.from_numpy(data.T.copy()), sr


torchaudio.load = _sf_load
from f5_tts.infer.utils_infer import infer_process, load_model, load_vocoder, preprocess_ref_audio_text
from f5_tts.model import DiT
from huggingface_hub import hf_hub_download

REPO = "Jip7e/habibi-tts-doda-darija"
spk = sys.argv[1] if len(sys.argv) > 1 else "M1"
nfe = int(sys.argv[2]) if len(sys.argv) > 2 else 16
device = "mps" if torch.backends.mps.is_available() else "cpu"

ckpt = hf_hub_download(REPO, "model_ema.safetensors")
vocab = hf_hub_download(REPO, "vocab.txt")
cfg = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
model = load_model(DiT, cfg, ckpt, vocab_file=vocab, device=device)
vocoder = load_vocoder("vocos", device=device)
ra, rt = preprocess_ref_audio_text(f"ref_{spk}.wav", open(f"ref_{spk}.txt").read())

LINES = [
    "السلام عليكم، معاك سارة من المتجر. عيطت ليك على الطلبية ديالك، واش عندك دقيقة؟",
    "طلبتي جوج علب ديال زيت أركان، والمجموع هو تلاتمية وستين درهم، كتخلصهم ملي توصلك السلعة.",
    "واش العنوان ديالك باقي هو لوطيسمان المسيرة واحد، الفيلا مية وطناش؟",
    "مزيان، غادي توصلك نهار الخميس إن شاء الله. شكرا بزاف وبسلامة.",
]

for i, text in enumerate(LINES):
    t = time.time()
    wav, sr, _ = infer_process(ra, rt, text, model, vocoder, speed=0.95, nfe_step=nfe,
                               cfg_strength=2.0, sway_sampling_coef=-1.0, device=device)
    took = time.time() - t
    sf.write(f"out_{spk}_{i}.wav", wav, sr)
    print(f"line {i}: {took:.1f}s to make {len(wav) / sr:.1f}s of audio on {device}")
