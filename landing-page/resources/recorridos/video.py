"""Videos de los recorridos, uno por idioma.

Lee `guion.json` y los fotogramas de
`public/media/recorridos/<recorrido>/<idioma>/`. La voz es la de macOS
(`say`): Paulina en español y Samantha en inglés. Cada escena dura lo que
dura su audio, así que los subtítulos salen de esas mismas duraciones.

Desde landing-page/:

  python3 resources/recorridos/video.py

Escribe `<recorrido>.mp4`, `.webm` y `.vtt` dentro de la carpeta de cada idioma.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "public" / "media" / "recorridos"
FADE = 0.5
LEAD = 0.7
TAIL = 0.9
MAX_CUE = 84


def run(args: list[str]) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise SystemExit(f"Falló {args[0]}: {proc.stderr[-1500:]}")
    return proc.stdout


def duration(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


def stamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def chunks(text: str) -> list[str]:
    """Frases de un subtítulo. Las largas se parten por comas o dos puntos."""
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        if len(sentence) <= MAX_CUE:
            out.append(sentence)
            continue
        current = ""
        for part in re.split(r"(?<=[,:;])\s+", sentence):
            if current and len(current) + len(part) + 1 > MAX_CUE:
                out.append(current)
                current = part
            else:
                current = f"{current} {part}".strip()
        if current:
            out.append(current)
    return out


def cues(text: str, start: float, length: float) -> list[tuple[float, float, str]]:
    parts = chunks(text)
    total = sum(len(part) for part in parts) or 1
    rows, at = [], start
    for part in parts:
        span = length * len(part) / total
        rows.append((at, at + span, part))
        at += span
    return rows


def vtt(rows: list[tuple[float, float, str]]) -> str:
    body = "\n\n".join(f"{index}\n{stamp(a)} --> {stamp(b)}\n{text}" for index, (a, b, text) in enumerate(rows, start=1))
    return f"WEBVTT\n\n{body}\n"


def build(tour: dict, lang: str, voice: str, rate: int, work: Path) -> None:
    tour_id = tour["id"]
    frames = OUT / tour_id / lang
    images = sorted(frames.glob("*.webp"))
    scenes = tour["escenas"]
    if len(images) != len(scenes):
        raise SystemExit(f"{tour_id}/{lang}: {len(images)} fotogramas y {len(scenes)} escenas en el guion.")
    audio_dir = work / "audio" / lang / tour_id
    audio_dir.mkdir(parents=True, exist_ok=True)

    lengths, speech, segments = [], [], []
    for number, scene in enumerate(scenes, start=1):
        aiff = audio_dir / f"{number:02d}.aiff"
        run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), scene[lang]])
        spoken = duration(aiff)
        last = number == len(scenes)
        length = LEAD + spoken + TAIL + (0 if last else FADE)
        lengths.append(length)
        speech.append(spoken)
        segments.append(length if last else length - FADE)

    # Audio: cada escena empieza con LEAD de silencio y se rellena hasta su tramo.
    audio_inputs, audio_filters = [], []
    for index, segment in enumerate(segments):
        audio_inputs += ["-i", str(audio_dir / f"{index + 1:02d}.aiff")]
        audio_filters.append(
            f"[{index}:a]aformat=sample_rates=48000:channel_layouts=mono,"
            f"adelay=delays={int(LEAD * 1000)}:all=1,apad,atrim=0:{segment:.3f}[a{index}]"
        )
    concat = "".join(f"[a{i}]" for i in range(len(segments)))
    audio_filters.append(f"{concat}concat=n={len(segments)}:v=0:a=1,loudnorm=I=-16:TP=-1.5[aout]")
    narration = work / f"{tour_id}-{lang}.m4a"
    run(["ffmpeg", "-y", *audio_inputs, "-filter_complex", ";".join(audio_filters), "-map", "[aout]", "-c:a", "aac", "-b:a", "160k", str(narration)])

    # Video: fotogramas fijos con fundido entre escenas.
    video_inputs, video_filters = [], []
    for index, (image, length) in enumerate(zip(images, lengths)):
        video_inputs += ["-loop", "1", "-framerate", "30", "-t", f"{length:.3f}", "-i", str(image)]
        video_filters.append(f"[{index}:v]format=yuv420p,setsar=1[v{index}]")
    previous, elapsed = "v0", lengths[0]
    for index in range(1, len(images)):
        offset = elapsed - FADE
        label = f"x{index}"
        video_filters.append(f"[{previous}][v{index}]xfade=transition=fade:duration={FADE}:offset={offset:.3f}[{label}]")
        previous = label
        elapsed = elapsed + lengths[index] - FADE
    silent = work / f"{tour_id}-{lang}-imagen.mp4"
    run([
        "ffmpeg", "-y", *video_inputs, "-filter_complex", ";".join(video_filters), "-map", f"[{previous}]",
        "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-tune", "stillimage", "-r", "30", "-pix_fmt", "yuv420p", str(silent),
    ])

    frames.mkdir(parents=True, exist_ok=True)
    mp4 = frames / f"{tour_id}.mp4"
    webm = frames / f"{tour_id}.webm"
    run(["ffmpeg", "-y", "-i", str(silent), "-i", str(narration), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(mp4)])
    run([
        "ffmpeg", "-y", "-i", str(silent), "-i", str(narration), "-map", "0:v", "-map", "1:a",
        "-c:v", "libvpx-vp9", "-crf", "36", "-b:v", "0", "-deadline", "good", "-cpu-used", "4", "-row-mt", "1",
        "-c:a", "libopus", "-b:a", "96k", "-shortest", str(webm),
    ])

    rows, start = [], 0.0
    for scene, spoken, segment in zip(scenes, speech, segments):
        rows += cues(scene[lang], start + LEAD, spoken)
        start += segment
    (frames / f"{tour_id}.vtt").write_text(vtt(rows), encoding="utf-8")
    print(f"{tour_id}/{lang}: {start:.1f} s, {mp4.stat().st_size // 1024} KB mp4, {webm.stat().st_size // 1024} KB webm")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=Path("/tmp/kicad-ia-recorrido"))
    parser.add_argument("--solo", help="id de un recorrido")
    parser.add_argument("--idioma", choices=("es", "en"))
    args = parser.parse_args()
    script = json.loads((HERE / "guion.json").read_text(encoding="utf-8"))
    voices = script.get("voces") or {"es": {"voz": script["voz"], "velocidad": script["velocidad"]}}
    for tour in script["recorridos"]:
        if args.solo and tour["id"] != args.solo:
            continue
        for lang, voice in voices.items():
            if args.idioma and lang != args.idioma:
                continue
            build(tour, lang, voice["voz"], voice["velocidad"], args.dir / "video")


if __name__ == "__main__":
    main()
