# resolver_server.py
import socket, json, threading, subprocess, shutil
from yt_dlp import YoutubeDL
from collections import OrderedDict

# cache
audio_cache = OrderedDict()
MAX_CACHE = 50

def play_stream(url):
    if not url:
        return
    if shutil.which("ffplay"):
        cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", url]
    elif shutil.which("vlc"):
        cmd = ["vlc", "--intf", "dummy", "--play-and-exit", url]
    elif shutil.which("mpv"):
        cmd = ["mpv", "--no-video", url]
    elif shutil.which("termux-media-player"):
        cmd = ["termux-media-player", "play", url]
    else:
        print("No player found")
        return
    subprocess.Popen(cmd)

def resolve_and_play(video_id):
    if video_id in audio_cache:
        play_stream(audio_cache[video_id])
        return
    url = None
    ydl_opts = {
        "format": "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
        "quiet": True,
        "no_warnings": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        url = info.get("url")
    if url:
        audio_cache[video_id] = url
        if len(audio_cache) > MAX_CACHE:
            audio_cache.popitem(last=False)
        play_stream(url)

def client_thread(conn, addr):
    data = conn.recv(4096).decode("utf-8")
    if not data:
        return
    msg = json.loads(data)
    vid = msg.get("id")
    if vid:
        threading.Thread(target=resolve_and_play, args=(vid,), daemon=True).start()

def server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 5050))
        s.listen()
        print("Resolver server ready on 127.0.0.1:5050")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=client_thread, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    server()

