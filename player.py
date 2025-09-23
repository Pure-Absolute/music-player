# player.py
import threading
import subprocess
import time
import os
import socket
import json
import random
from utils import get_socket_path
from miniytdlp import search_youtube, get_audio_url   # 🔥 pakai wrapper lu

class PlayerState:
    def __init__(self):
        self.queue = []
        self.idx = -1
        self.playing = False
        self.paused = False
        self.loading = False
        self.duration = 0
        self.elapsed = 0
        self.repeat_song = False
        self.repeat_playlist = False
        self.shuffle = False
        self.volume = 80
        self._mpv_proc = None
        self._ipc_path = get_socket_path()
        self._ipc_lock = threading.Lock()
        self._monitor_thread = None
        self._monitor_stop = threading.Event()

    # --- fetch info pakai wrapper ---
    def fetch_info(self, query, top_only=True, max_results=5):
        if query.startswith("http://") or query.startswith("https://"):
            # treat as URL
            return [("Direct URL", "??:??", query)]
        else:
            return search_youtube(query, max_results=max_results)

    def add_items(self, items):
        # items: list of (title, duration_str, url)
        for t, d, u in items:
            self.queue.append({"title": t, "duration_str": d, "url": u})

    def add_top(self, item):
        t, d, u = item
        self.queue.append({"title": t, "duration_str": d, "url": u})

    # --- play control ---
    def play_index(self, index):
        if index < 0 or index >= len(self.queue):
            return
        self.idx = index
        item = self.queue[self.idx]
        self.loading = True
        self.playing = False
        self.elapsed = 0
        self.duration = 0  # kita gak punya durasi numerik, cuma string

        def worker():
            stream_url = get_audio_url(item["url"])
            if not stream_url:
                self.loading = False
                self.playing = False
                return
            # panggil mpv langsung
            self._start_mpv(stream_url)
            self.playing = True
            self.loading = False
            if self._mpv_proc:
                self._mpv_proc.wait()

        threading.Thread(target=worker, daemon=True).start()

    def _start_mpv(self, stream_url):
        try:
            if os.path.exists(self._ipc_path):
                os.remove(self._ipc_path)
        except Exception:
            pass

        cmd = [
            "mpv", "--no-video", "--quiet",
            f"--input-ipc-server={self._ipc_path}",
            f"--volume={self.volume}", "--idle=no", stream_url
        ]
        self._mpv_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._monitor_stop.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    # (sisanya tetap sama: stop, toggle_pause, set_volume, dll)

