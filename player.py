# player.py
import threading
import subprocess
import yt_dlp
import time
import os
import socket
import json
from utils import get_socket_path

class PlayerState:
    def __init__(self):
        self.queue = []  # list of {"title","url","duration"}
        self.idx = -1
        self.playing = False
        self.paused = False
        self.loading = False
        self.duration = 0
        self.elapsed = 0
        self.repeat_song = False
        self.repeat_playlist = False
        self.shuffle = False
        self.volume = 80  # default
        self._mpv_proc = None
        self._ipc_path = get_socket_path()
        self._ipc_lock = threading.Lock()
        self._monitor_thread = None
        self._monitor_stop = threading.Event()

    # --- yt-dlp info fetch (non-blocking recommended to call from thread) ---
    def fetch_info(self, query, top_only=True, max_results=5):
        """
        If query is url -> returns list with single info dict.
        If not url -> returns list of up to max_results search results (title,url,duration).
        """
        try:
            ydl_opts = {"quiet": True, "skip_download": True, "format": "bestaudio/best"}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if query.startswith("http://") or query.startswith("https://"):
                    info = ydl.extract_info(query, download=False)
                    return [{"title": info.get("title","Unknown"), "url": info.get("webpage_url"), "duration": info.get("duration",0)}]
                else:
                    info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
                    entries = info.get("entries", [])
                    res = []
                    for e in entries:
                        res.append({"title": e.get("title","Unknown"), "url": e.get("webpage_url"), "duration": e.get("duration",0)})
                    return res
        except Exception as e:
            return []

    # --- queue operations ---
    def add_items(self, items):
        # items: list of {"title","url","duration"}
        self.queue.extend(items)

    def add_top(self, item):
        # add single top result
        self.queue.append(item)

    # --- mpv IPC helpers ---
    def _start_mpv(self, stream_url):
        # remove old socket if exists
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
        # start mpv process
        self._mpv_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # start monitor
        self._monitor_stop.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _send_ipc(self, data):
        # send JSON command to mpv socket; return response if any
        # data could be {"command":[...]} or {"request_id":...,"command":[...]}
        try:
            with self._ipc_lock:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(0.6)
                s.connect(self._ipc_path)
                s.send((json.dumps(data) + "\n").encode("utf-8"))
                # try read short response non-blocking
                try:
                    resp = s.recv(4096)
                    s.close()
                    if resp:
                        try:
                            return json.loads(resp.decode("utf-8"))
                        except Exception:
                            return None
                    return None
                except socket.timeout:
                    s.close()
                    return None
        except Exception:
            return None

    def _monitor_loop(self):
        # poll mpv for time-pos and detect exit
        while not self._monitor_stop.is_set():
            if self._mpv_proc is None:
                break
            # check if process ended
            ret = self._mpv_proc.poll()
            if ret is not None:
                # ended
                self.playing = False
                self.paused = False
                # next behavior handled by main after detecting playing False
                break
            # query mpv via IPC
            res = self._send_ipc({"command":["get_property", "time-pos"]})
            if isinstance(res, dict) and "data" in res and res["data"] is not None:
                try:
                    self.elapsed = int(res["data"])
                except Exception:
                    pass
            res2 = self._send_ipc({"command":["get_property","pause"]})
            if isinstance(res2, dict) and "data" in res2:
                self.paused = bool(res2["data"])
            time.sleep(0.5)
        # cleanup
        try:
            if self._mpv_proc:
                self._mpv_proc.wait(timeout=0.5)
        except Exception:
            pass
        self._mpv_proc = None
        try:
            if os.path.exists(self._ipc_path):
                os.remove(self._ipc_path)
        except Exception:
            pass

    # --- play control (non-blocking) ---
    def play_index(self, index):
        if index < 0 or index >= len(self.queue):
            return
        self.idx = index
        item = self.queue[self.idx]
        self.loading = True
        self.playing = False
        self.elapsed = 0
        self.duration = item.get("duration", 0)

        def worker():
            # fetch direct stream url by yt-dlp (so we pass stream to mpv)
            try:
                ydl_opts = {"quiet": True, "format": "bestaudio/best"}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(item["url"], download=False)
                    # mpv can accept "url" which sometimes is direct stream
                    stream_url = info.get("url") or item["url"]
                    # start mpv
                    self._start_mpv(stream_url)
                    self.playing = True
                    self.loading = False
                    # main monitor updates elapsed/pause; block until mpv ends
                    if self._mpv_proc:
                        self._mpv_proc.wait()
            except Exception:
                self.loading = False
                self.playing = False

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def stop(self):
        self.loading = False
        self.playing = False
        self.paused = False
        self.elapsed = 0
        # stop monitor and mpv
        self._monitor_stop.set()
        if self._mpv_proc:
            try:
                self._mpv_proc.terminate()
            except Exception:
                pass
            self._mpv_proc = None

    def toggle_pause(self):
        if not self._mpv_proc:
            return
        self._send_ipc({"command":["cycle", "pause"]})

    def set_volume(self, vol):
        # vol 0-100
        self.volume = max(0, min(100, int(vol)))
        # apply to mpv if running
        self._send_ipc({"command":["set_property","volume", self.volume]})

    def seek(self, seconds):
        self._send_ipc({"command":["seek", seconds, "relative"]})
