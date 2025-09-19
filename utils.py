# utils.py
import time
import os
import tempfile
import json

def format_time(seconds):
    if seconds is None:
        return "--:--"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"

def get_socket_path(appname="mpv_music_tui"):
    # choose a socket in tempdir that hopefully works in Termux
    fn = f"{appname}_{os.getuid()}.sock"
    return os.path.join(tempfile.gettempdir(), fn)

def safe_write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
