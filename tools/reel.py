#!/usr/bin/env python3
"""آية لمست قلبي — reel renderer.
usage: reel.py spec.json   (spec: surah, from, to, reciter, bg, hook, out, [clip_words])
"""
import json, re, subprocess, sys, os, math, tempfile
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
FONTS = f"{ROOT}/fonts"
W, H = 1080, 1920
QURAN = json.load(open(f"{ROOT}/quran_flat.json"))  # [surah, name, ayah, text]
IDX = {(s, a): (n, t) for s, n, a, t in QURAN}
RECITERS = {
    "dosari": ("Yasser_Ad-Dussary_128kbps", "ياسر الدوسري"),
    "minshawi": ("Minshawy_Murattal_128kbps", "محمد صديق المنشاوي"),
    "muaiqly": ("Maher_AlMuaiqly_64kbps", "ماهر المعيقلي"),
    "qatami": ("Nasser_Alqatami_128kbps", "ناصر القطامي"),
    "abdulbasit": ("Abdul_Basit_Murattal_192kbps", "عبد الباسط عبد الصمد"),
    "alafasy": ("Alafasy_128kbps", "مشاري العفاسي"),
    "minshawi_m": ("Minshawy_Mujawwad_192kbps", "محمد صديق المنشاوي (مجوّد)"),
    "abdulbasit_m": ("Abdul_Basit_Mujawwad_128kbps", "عبد الباسط عبد الصمد (مجوّد)"),
    "abdulbasit": ("Abdul_Basit_Murattal_192kbps", "عبد الباسط عبد الصمد"),
}
AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
FIX = str.maketrans({"ٗ": "ࣰ", "ٞ": "ࣱ", "ٖ": "ࣲ"})
WAQF = "ۖۗۘۙۚۛۜ"


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)


def fetch_audio(rid, s, a, d):
    p = f"{ROOT}/audio/{rid}/{s:03d}{a:03d}.mp3"
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        sh(f"curl -sf -m 60 -o {p} https://everyayah.com/data/{rid}/{s:03d}{a:03d}.mp3")
    return p


def segments(text, maxw=7):
    words = text.split()
    segs, cur = [], []
    for w in words:
        cur.append(w)
        if any(c in w for c in WAQF) and len(cur) >= 2:
            segs.append(cur); cur = []
    if cur:
        if segs and len(cur) <= 1: segs[-1] += cur
        else: segs.append(cur)
    out = []
    for s in segs:
        n = math.ceil(len(s) / maxw)
        k = math.ceil(len(s) / n)
        out += [s[i:i + k] for i in range(0, len(s), k)]
    return [" ".join(s) for s in out]


def silences(audio):
    r = subprocess.run(f"ffmpeg -i {audio} -af silencedetect=noise=-32dB:d=0.18 -f null -", shell=True, capture_output=True, text=True)
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return [((a + b) / 2) for a, b in zip(st, en)]


def letters(s):
    return len(re.sub(r"[^ء-ي]", "", s)) or 1


def font(name, size):
    return ImageFont.truetype(f"{FONTS}/{name}", size, layout_engine=ImageFont.Layout.RAQM)


def wrap(draw, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f, direction="rtl") <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w
    lines.append(cur)
    return lines


def balanced(d, text, f, maxw):
    lines = wrap(d, text, f, maxw); n = len(lines); w = maxw
    while n > 1 and w > 200:
        t = wrap(d, text, f, w - 20)
        if len(t) > n: break
        lines, w = t, w - 20
    return lines


def draw_block(img, text, f, cy, maxw, fill=(255, 255, 255, 255), lh=1.0, shadow=10, box=None):
    d = ImageDraw.Draw(img)
    lines = balanced(d, text, f, maxw)
    asc, desc = f.getmetrics(); lineh = int((asc + desc) * lh)
    top = cy - lineh * len(lines) // 2
    if box:
        ws = [d.textlength(l, font=f, direction="rtl") for l in lines]
        bw = max(ws) + 2 * box[0]; bh = lineh * len(lines) + 2 * box[1]
        b = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(b).rounded_rectangle([(W - bw) / 2, top - box[1], (W + bw) / 2, top - box[1] + bh], radius=28, fill=box[2])
        img.alpha_composite(b)
    sh_ = Image.new("RGBA", img.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(sh_)
    for i, l in enumerate(lines):
        sd.text((W / 2, top + i * lineh + lineh / 2), l, font=f, fill=(0, 0, 0, 200), anchor="mm", direction="rtl")
    if shadow: img.alpha_composite(sh_.filter(ImageFilter.GaussianBlur(shadow)))
    d = ImageDraw.Draw(img)
    for i, l in enumerate(lines):
        d.text((W / 2, top + i * lineh + lineh / 2), l, font=f, fill=fill, anchor="mm", direction="rtl")


def main(spec):
    S = json.load(open(spec))
    s, a0, a1 = S["surah"], S["from"], S.get("to", S["from"])
    rid, rname = RECITERS[S["reciter"]]
    tmp = tempfile.mkdtemp()
    # audio: concat ayahs
    files = [fetch_audio(rid, s, a, tmp) for a in range(a0, a1 + 1)]
    with open(f"{tmp}/l.txt", "w") as fh:
        for p in files: fh.write(f"file '{p}'\n")
    sh(f"ffmpeg -y -f concat -safe 0 -i {tmp}/l.txt -af 'silenceremove=start_periods=1:start_threshold=-40dB,adelay=150|150,apad=pad_dur=0.8,aresample=44100' -ac 2 {tmp}/a.wav")
    T = float(sh(f"ffprobe -v error -show_entries format=duration -of csv=p=0 {tmp}/a.wav").stdout)
    # text segments with ayah markers
    segs = []
    for a in range(a0, a1 + 1):
        txt = IDX[(s, a)][1].translate(FIX).replace("\u06DE", "").strip()
        sp = S.get("splits", {}).get(str(a))
        if sp:
            w = txt.split(); ss = []; i = 0
            for n in sp: ss.append(" ".join(w[i:i + n])); i += n
            if i < len(w): ss[-1] += " " + " ".join(w[i:])
        else:
            ss = segments(txt, S.get("maxw", 7))
        ss[-1] += f" ﴿{str(a).translate(AR)}﴾"
        segs += ss
    # timing: proportional to letters, snapped to silences
    sil = silences(f"{tmp}/a.wav")
    speech_end = T - 0.8
    L = [letters(x) for x in segs]; tot = sum(L)
    bounds, acc = [0.0], 0
    for l in L[:-1]:
        acc += l; b = 0.15 + (speech_end - 0.15) * acc / tot
        near = [x for x in sil if abs(x - b) < 1.5 and x > bounds[-1] + 0.8]
        bounds.append(min(near, key=lambda x: abs(x - b)) if near else b)
    bounds.append(T)
    surah_name = IDX[(s, a0)][0]
    ref = f"سورة {surah_name} · {str(a0).translate(AR)}" + ((f" و{str(a1).translate(AR)}" if a1 == a0 + 1 else f" إلى {str(a1).translate(AR)}") if a1 != a0 else "")
    # base overlay: grade gradient + hook + footer
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = Image.new("L", (1, H))
    for y in range(H):
        v = 0.40 + 0.25 * max(0, (y - H * 0.6) / (H * 0.4)) + 0.2 * max(0, (H * 0.3 - y) / (H * 0.3))
        g.putpixel((0, y), int(255 * min(v, 0.75)))
    base.alpha_composite(Image.merge("RGBA", [Image.new("L", (W, H), 0)] * 3 + [g.resize((W, H))]))
    draw_block(base, S["hook"], font("IBMPlexSansArabic_700Bold.ttf", 64), 470, 860, lh=1.25, shadow=0,
               box=(44, 30, (255, 255, 255, 38)))
    draw_block(base, f"{ref}  |  {rname}", font("IBMPlexSansArabic_500Medium.ttf", 32), 1500, 900, fill=(255, 255, 255, 230), shadow=6)
    draw_block(base, "@آية لمست قلبي", font("IBMPlexSansArabic_700Bold.ttf", 30), 1560, 900, fill=(255, 255, 255, 200), shadow=6)
    base.save(f"{tmp}/base.png")
    fq = font("AmiriQuran.ttf", S.get("ayah_size", 84))
    for i, t in enumerate(segs):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_block(im, t, fq, 960, 880, lh=1.55, shadow=14)
        im.save(f"{tmp}/s{i}.png")
    # ffmpeg
    bg = S.get("bg")
    if "scenes" in S:
        BGD = f"{ROOT}/bg"
        cuts = []  # (clip, dur)
        for i, clips in enumerate(S["scenes"]):
            a, b = bounds[i], bounds[i + 1]
            n = len(clips)
            for j, c in enumerate(clips):
                cuts.append((f"{BGD}/{c}.mp4", (b - a) / n))
        X = 0.35
        ins, fcb = "", ""
        for k, (c, d) in enumerate(cuts):
            L = d + (X if k < len(cuts) - 1 else 0.05)
            ins += f"-stream_loop -1 -t {L:.3f} -i '{c}' "
            fcb += (f"[{k}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,"
                    f"setsar=1,format=yuv420p[c{k}];")
        last, acc = "c0", 0.0
        for k in range(1, len(cuts)):
            acc += cuts[k - 1][1]
            fcb += f"[{last}][c{k}]xfade=transition=fade:duration={X}:offset={acc:.3f}[x{k}];"
            last = f"x{k}"
        fcb = fcb.rstrip(";")
        sh(f"ffmpeg -y {ins} -filter_complex \"{fcb}\" -map [{last}] -an -c:v libx264 -preset veryfast -crf 17 -t {T:.2f} {tmp}/bgtrack.mp4")
        bg = f"{tmp}/bgtrack.mp4"
        S["zoom"] = 0
    inputs = f"-stream_loop -1 -i '{bg}' -i {tmp}/a.wav -loop 1 -t {T:.2f} -i {tmp}/base.png "
    fc = (f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,"
          
          f"colorchannelmixer=rr=0.93:gg=0.85:bb=0.76,eq=saturation=0.9:contrast=1.04,setsar=1,format=yuva420p[bg];[bg][2:v]overlay=0:0[v0];")
    last = "v0"
    for i in range(len(segs)):
        a, b = bounds[i], bounds[i + 1]; d = b - a
        inputs += f"-loop 1 -t {d:.2f} -i {tmp}/s{i}.png "
        k = i + 3
        fo = f",fade=out:st={d-0.25:.2f}:d=0.25:alpha=1" if i < len(segs) - 1 else ""
        fc += (f"[{k}:v]format=rgba,fade=in:st=0:d=0.3:alpha=1{fo},setpts=PTS+{a:.2f}/TB[o{i}];"
               f"[{last}][o{i}]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[v{i+1}];")
        last = f"v{i+1}"
    fc += f"[{last}]fade=in:st=0:d=0.25,format=yuv420p[vo]"
    out = S["out"]
    sh(f"ffmpeg -y {inputs} -filter_complex \"{fc}\" -map [vo] -map 1:a -t {T:.2f} "
       f"-c:v libx264 -preset veryfast -crf 19 -r 30 -c:a aac -b:a 160k -movflags +faststart '{out}'")
    print(json.dumps({"out": out, "dur": round(T, 2), "segs": segs, "bounds": [round(x, 2) for x in bounds]}, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
