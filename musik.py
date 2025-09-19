import curses
import threading
import time
import subprocess
import yt_dlp
import re

class MusicPlayer:
    def __init__(self):
        self.queue = []
        self.current_index = -1
        self.playing = False
        self.process = None
        self.start_time = None
        self.duration = 0
        self.loading = False
        self.search_results = []
        self.search_mode = False
        self.search_index = 0

    def is_url(self, text):
        return text.startswith("http://") or text.startswith("https://")

    def add_to_queue(self, query):
        self.loading = True
        if self.is_url(query):
            url = query
        else:
            # search mode
            with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                info = ydl.extract_info(f"ytsearch5:{query}", download=False)["entries"]
                self.search_results = [(e["title"], e["webpage_url"]) for e in info]
                self.search_mode = True
                self.loading = False
                return
        self.queue.append({"title": query, "url": url})
        self.loading = False

    def choose_search_result(self, idx):
        if 0 <= idx < len(self.search_results):
            title, url = self.search_results[idx]
            self.queue.append({"title": title, "url": url})
            self.search_mode = False
            self.search_results = []

    def play(self, index):
        if index < 0 or index >= len(self.queue):
            return
        self.stop()
        self.current_index = index
        self.playing = True
        self.loading = True
        url = self.queue[self.current_index]["url"]

        def run():
            with yt_dlp.YoutubeDL({"quiet": True, "format": "bestaudio"}) as ydl:
                info = ydl.extract_info(url, download=False)
                self.duration = info.get("duration", 0)
                stream_url = info["url"]
            self.start_time = None
            self.process = subprocess.Popen(["mpv", "--no-video", stream_url],
                                            stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL)
            self.start_time = time.time()
            self.loading = False

        threading.Thread(target=run, daemon=True).start()

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process = None
        self.playing = False
        self.start_time = None
        self.duration = 0

    def next(self):
        if self.current_index + 1 < len(self.queue):
            self.play(self.current_index + 1)

    def prev(self):
        if self.current_index > 0:
            self.play(self.current_index - 1)

    def progress(self):
        if not self.start_time:
            return 0
        elapsed = int(time.time() - self.start_time)
        return min(elapsed, self.duration)

    def format_time(self, seconds):
        m, s = divmod(seconds, 60)
        return f"{m:02}:{s:02}"

def tui(stdscr, player):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    curses.init_pair(3, curses.COLOR_GREEN, -1)
    curses.init_pair(4, curses.COLOR_RED, -1)

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        # Title
        stdscr.addstr(0, 0, "🎵 Termux Music Player", curses.color_pair(1))

        # Loading indicator
        if player.loading:
            stdscr.addstr(1, 0, "[Loading...]", curses.color_pair(2))

        # Search mode
        if player.search_mode:
            stdscr.addstr(2, 0, "Select search result (press 1-5):", curses.color_pair(3))
            for i, (title, url) in enumerate(player.search_results):
                stdscr.addstr(3 + i, 2, f"{i+1}. {title}", curses.color_pair(3))
            stdscr.refresh()
            ch = stdscr.getch()
            if ord("1") <= ch <= ord("5"):
                idx = ch - ord("1")
                player.choose_search_result(idx)
            continue

        # Current song
        if 0 <= player.current_index < len(player.queue):
            song = player.queue[player.current_index]
            stdscr.addstr(2, 0, f"▶ {song['title']}", curses.color_pair(3))

            # Progress bar
            if player.duration > 0:
                prog = player.progress()
                bar_len = w - 20
                filled = int(bar_len * (prog / player.duration))
                bar = "█" * filled + "-" * (bar_len - filled)
                stdscr.addstr(3, 0, f"[{bar}] {player.format_time(prog)}/{player.format_time(player.duration)}")

        # Queue
        stdscr.addstr(5, 0, "Queue:", curses.color_pair(1))
        for i, song in enumerate(player.queue[:h - 10]):
            marker = ">>" if i == player.current_index else "  "
            stdscr.addstr(6 + i, 0, f"{marker} {song['title']}", curses.color_pair(2 if i == player.current_index else 0))

        # Controls
        controls = "Controls: [a] Add  [p] Play  [s] Stop  [n] Next  [b] Prev  [q] Quit"
        stdscr.addstr(h - 2, 0, controls, curses.color_pair(4))

        stdscr.refresh()
        ch = stdscr.getch()
        if ch == ord("q"):
            player.stop()
            break
        elif ch == ord("a"):
            curses.echo()
            stdscr.move(h-1, 0)
            stdscr.clrtoeol()
            stdscr.addstr(h-1, 0, "Enter URL or Title: ")
            stdscr.refresh()
            query = stdscr.getstr(h-1, len("Enter URL or Title: ")).decode("utf-8")
            curses.noecho()
            if query:
                player.add_to_queue(query)
        elif ch == ord("p"):
            if player.current_index == -1 and player.queue:
                player.play(0)
            elif player.current_index >= 0:
                player.play(player.current_index)
        elif ch == ord("s"):
            player.stop()
        elif ch == ord("n"):
            player.next()
        elif ch == ord("b"):
            player.prev()

if __name__ == "__main__":
    player = MusicPlayer()
    curses.wrapper(tui, player)
