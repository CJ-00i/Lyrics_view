import sounddevice as sd
import soundfile as sf
import numpy as np
import sys
import shutil
import re

filename = "sanc.wav"
lyricsfile = "sanc.lrc" 


start_time = 0   #start time

data, samplerate = sf.read(filename, dtype="float32")
if data.ndim > 1: 
    data = np.mean(data, axis=1)
data = data / np.max(np.abs(data))

def parse_lrc(path):
    timeline = []
    pattern = re.compile(r"\[(\d+):(\d+\.\d+)\](.*)")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            m = pattern.match(line.strip())
            if m:
                minutes, seconds, text = m.groups()
                t = int(minutes) * 60 + float(seconds)
                timeline.append((t, text.strip()))
    return sorted(timeline)

lyrics = parse_lrc(lyricsfile)
lyric_index = 0
typed_text = ""

term_columns, rows = shutil.get_terminal_size((200, 84))
columns = min(60, term_columns)   
center = 6                        


start = int(start_time * samplerate)
for i, (t, _) in enumerate(lyrics):
    if t >= start_time:
        lyric_index = max(0, i - 1)
        break


def smooth(values, window=5):
    if len(values) < window:
        return values
    kernel = np.ones(window) / window
    return np.convolve(values, kernel, mode="same")


def typing_effect(curr_line, play_time, start_t, end_t):
    global typed_text
    if not curr_line:
        return ""

    if abs(play_time - start_t) < 0.05:
        typed_text = ""

    duration = max(0.05, (end_t - start_t) * 0.8)
    progress = min(1.0, max(0.0, (play_time - start_t) / duration))
    cutoff = int(len(curr_line) * progress)

    return curr_line[:cutoff]


def hsv_to_rgb(h, s, v):
    i = int(h * 6)
    f = h * 6 - i
    p = int(255 * v * (1 - s))
    q = int(255 * v * (1 - f * s))
    t = int(255 * v * (1 - (1 - f * s)))
    v = int(255 * v)
    i = i % 6
    if i == 0: return v, t, p
    if i == 1: return q, v, p
    if i == 2: return p, v, t
    if i == 3: return p, q, v
    if i == 4: return t, p, v
    if i == 5: return v, p, q

def colorize(text, r, g, b):
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"


def callback(outdata, frames, time_info, status):
    global start, lyric_index
    if status:
        print(status, file=sys.stderr)

    chunk = data[start:start + frames]
    if len(chunk) < frames:
        outdata[:len(chunk), 0] = chunk
        outdata[len(chunk):] = 0
        raise sd.CallbackStop
    else:
        outdata[:, 0] = chunk

    play_time = start / samplerate

    while lyric_index + 1 < len(lyrics) and play_time >= lyrics[lyric_index + 1][0]:
        lyric_index += 1


    step = max(1, len(chunk) // columns)
    levels = np.abs(chunk[::step])
    levels = smooth(levels, window=6)
    levels = np.interp(levels, [0, 1], [0, center - 1]).astype(int)

    hue = (play_time * 0.05) % 1.0
    saturation = 0.5  
    value = 0.9        
    r, g, b = hsv_to_rgb(hue, saturation, value)

    screen = []
    for row in range(center * 2):
        line = []
        for lvl in levels:
            if row == center:
                line.append(colorize("─", r, g, b))
            elif row < center and (center - row) <= lvl:
                line.append(colorize("█", r, g, b))
            elif row > center and (row - center) <= lvl:
                line.append(colorize("█", r, g, b))
            else:
                line.append(" ")
        screen.append("".join(line))

    curr_line = lyrics[lyric_index][1] if lyric_index < len(lyrics) else ""
    curr_start = lyrics[lyric_index][0] if lyric_index < len(lyrics) else 0
    curr_end = lyrics[lyric_index + 1][0] if lyric_index + 1 < len(lyrics) else curr_start + 5

    typed = typing_effect(curr_line, play_time, curr_start, curr_end)
    screen.append("")
    screen.append(colorize(typed, r, g, b))

    sys.stdout.write("\033[H\033[J")
    sys.stdout.write("\n".join(screen))
    sys.stdout.flush()

    start += frames


with sd.OutputStream(channels=1, callback=callback, samplerate=samplerate, blocksize=1024):
    sd.sleep(int((len(data) - start) / samplerate * 1000))
