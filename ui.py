# ui.py
import curses
import threading
import time
import random
from utils import format_time
from playlists import save_playlist_to, load_playlist_from

ASCII_ART = [
r"  __   __  ___  __  __  ___  ",
r" / _| / _|/ _ \|  \/  |/ _ \ ",
r"| |_ | |_ | | | | |\/| | | | |",
r"|  _||  _|| |_| | |  | | |_| |",
r"|_|  |_|   \___/|_|  |_|\___/ "
]

class TUI:
    def __init__(self, stdscr, player):
        self.stdscr = stdscr
        self.player = player
        self.screen = "home"
        self.cursor = 0
        self.scroll = 0
        self.running = True
        self.marquee_offsets = {}
        self.search_results = []
        self.search_selected = set()
        self.search_query = ""
        self.message = ""

    def start(self):
        curses.curs_set(0)
        curses.use_default_colors()
        curses.start_color()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        curses.init_pair(3, curses.COLOR_GREEN, -1)
        curses.init_pair(4, curses.COLOR_RED, -1)
        curses.init_pair(5, curses.COLOR_MAGENTA, -1)
        self.stdscr.nodelay(True)
        self.loop()

    def _marquee(self, key, text, width):
        if len(text) <= width:
            return text
        off = self.marquee_offsets.get(key, 0)
        view = text[off:off+width]
        off = (off + 1) % (len(text))
        self.marquee_offsets[key] = off
        return view

    def draw_home(self, h, w):
        y = 2
        for line in ASCII_ART:
            self.stdscr.addstr(y, max(0,(w - len(line))//2), line, curses.color_pair(5))
            y += 1
        self.stdscr.addstr(y+1, max(0,(w-30)//2), "Press L for Queue, A Add, / Search, Q Quit", curses.color_pair(1))

    def draw_queue(self, h, w):
        self.stdscr.addstr(1, 0, "Queue (↑↓ navigate, Enter play, R repeat, T repeat playlist, H shuffle, Space pause)".ljust(w), curses.color_pair(1))
        q = self.player.queue
        start = max(0, self.cursor - (h-10)//2)
        for i in range(start, min(len(q), start + (h-10))):
            t = q[i]["title"]
            d = q[i].get("duration_str", "")
            key = f"q{i}"
            marker = "➤ " if i == self.cursor else "  "
            display = self._marquee(key, t, w-20) if i == self.cursor else t[:w-20]
            color = curses.color_pair(3) if i == self.player.idx else curses.color_pair(2)
            line = f"{marker}{display} ({d})"
            self.stdscr.addstr(3 + i - start, 0, line[:w-1], color)

    def draw_playing_bar(self, h, w):
        if 0 <= self.player.idx < len(self.player.queue):
            cur = self.player.queue[self.player.idx]
            title = cur["title"]
            s = f"Now: {title}"
            s_trunc = s if len(s) < w-2 else self._marquee("now", s, w-10)
            self.stdscr.addstr(h-4, 0, s_trunc.ljust(w-1), curses.color_pair(3))
            if self.player.duration:
                dur = self.player.duration
                elapsed = self.player.elapsed
                barlen = max(10, w-30)
                filled = int(barlen * (elapsed / dur))
                bar = "█"*filled + "-"*(barlen-filled)
                times = f"{format_time(elapsed)}/{format_time(dur)}"
                self.stdscr.addstr(h-3, 0, f"[{bar}] {times}".ljust(w-1))
            else:
                if self.player.loading:
                    self.stdscr.addstr(h-3, 0, "[Loading...]".ljust(w-1), curses.color_pair(2))
                else:
                    self.stdscr.addstr(h-3, 0, "[--:--/--:--]".ljust(w-1))

    def draw_message(self, h, w):
        if self.message:
            self.stdscr.addstr(h-2, 0, self.message[:w-1], curses.color_pair(4))

    def draw_search(self, h, w):
        self.stdscr.addstr(2, 0, f"Search results for '{self.search_query}' (press numbers to toggle select, A to add)".ljust(w), curses.color_pair(1))
        for i, item in enumerate(self.search_results):
            mark = "[x]" if i in self.search_selected else "[ ]"
            t, d, u = item  # tuple
            line = f"{i+1}. {mark} {t} ({d})"
            self.stdscr.addstr(4+i, 0, line[:w-1], curses.color_pair(2))

    def loop(self):
        last_check = 0
        while self.running:
            self.stdscr.erase()
            h, w = self.stdscr.getmaxyx()
            self.stdscr.addstr(0, 0, "🎵 Termux Music Player (Home L:Queue A:Add /:Search Q:Quit)".ljust(w), curses.color_pair(1))

            if self.screen == "home":
                self.draw_home(h, w)
            elif self.screen == "queue":
                self.draw_queue(h, w)
            elif self.screen == "search":
                self.draw_search(h, w)

            self.draw_playing_bar(h, w)
            controls = "Controls: L Queue | A Add | / Search | Space Pause | Enter Play | N Next | B Prev | R RepeatSong | T RepeatPlaylist | H Shuffle | V Volume | S Save | O Load | Q Quit"
            self.stdscr.addstr(h-1, 0, controls[:w-1], curses.color_pair(5))
            self.draw_message(h, w)
            self.stdscr.refresh()

            now = time.time()
            if now - last_check > 0.4:
                last_check = now
                if not self.player.playing and not self.player.loading and self.player.idx != -1:
                    if self.player.repeat_song:
                        self.player.play_index(self.player.idx)
                    elif self.player.idx + 1 < len(self.player.queue):
                        self.player.play_index(self.player.idx + 1)
                    elif self.player.repeat_playlist and self.player.queue:
                        self.player.play_index(0)
                for k in list(self.marquee_offsets.keys()):
                    self.marquee_offsets[k] = (self.marquee_offsets.get(k,0)+1) % 200

            try:
                ch = self.stdscr.getch()
            except Exception:
                ch = -1
            if ch == -1:
                time.sleep(0.05)
                continue

            if ch in (ord('q'), ord('Q')):
                self.player.stop()
                self.running = False
                break
            elif ch in (ord('l'), ord('L')):
                self.screen = "queue"
            elif ch in (ord('h'), ord('H')):
                self.player.shuffle = not self.player.shuffle
                if self.player.shuffle:
                    random.shuffle(self.player.queue)
                self.message = f"Shuffle = {self.player.shuffle}"
            elif ch in (ord('a'), ord('A')):
                self.screen = "home"
                curses.echo()
                self.stdscr.nodelay(False)
                self.stdscr.addstr(4,0,"Enter URL or Title: ")
                q = self.stdscr.getstr(4, 22).decode("utf-8").strip()
                self.stdscr.nodelay(True)
                curses.noecho()
                if q:
                    self.message = "Searching..."
                    def add_worker():
                        items = self.player.fetch_info(q, max_results=1)
                        if items:
                            self.player.add_top(items[0])
                            self.message = f"Added: {items[0][0]}"
                        else:
                            self.message = "Not found."
                    threading.Thread(target=add_worker, daemon=True).start()
            elif ch == ord('/'):
                self.screen = "search"
                curses.echo()
                self.stdscr.nodelay(False)
                self.stdscr.addstr(4,0,"Enter search query: ")
                sq = self.stdscr.getstr(4, 20).decode("utf-8").strip()
                curses.noecho()
                self.stdscr.nodelay(True)
                self.search_query = sq
                self.search_results = []
                self.search_selected = set()
                self.message = "Searching..."
                def search_worker():
                    res = self.player.fetch_info(sq, max_results=8)
                    self.search_results = res
                    self.message = f"Found {len(res)} results"
                threading.Thread(target=search_worker, daemon=True).start()
            elif self.screen == "search" and ch in (ord('a'), ord('A')):
                sel = sorted(list(self.search_selected))
                if not sel and self.search_results:
                    sel = [0]
                items = [self.search_results[i] for i in sel if i < len(self.search_results)]
                self.player.add_items(items)
                self.message = f"Added {len(items)} items"
                self.search_selected = set()
                self.screen = "home"
            elif self.screen == "search" and ord('1') <= ch <= ord('8'):
                idx = ch - ord('1')
                if 0 <= idx < len(self.search_results):
                    if idx in self.search_selected:
                        self.search_selected.remove(idx)
                    else:
                        self.search_selected.add(idx)
            elif self.screen == "queue":
                if ch in (curses.KEY_DOWN, ord('j')):
                    if self.cursor + 1 < len(self.player.queue):
                        self.cursor += 1
                elif ch in (curses.KEY_UP, ord('k')):
                    if self.cursor > 0:
                        self.cursor -= 1
                elif ch in (10, 13):
                    self.player.play_index(self.cursor)
                elif ch in (ord('n'), ord('N')):
                    self.player.next()
                elif ch in (ord('b'), ord('B')):
                    self.player.prev()
                elif ch == ord(' '):
                    self.player.toggle_pause()
                elif ch in (ord('r'), ord('R')):
                    self.player.repeat_song = not self.player.repeat_song
                    self.message = f"RepeatSong = {self.player.repeat_song}"
                elif ch in (ord('t'), ord('T')):
                    self.player.repeat_playlist = not self.player.repeat_playlist
                    self.message = f"RepeatPlaylist = {self.player.repeat_playlist}"
                elif ch in (ord('v'), ord('V')):
                    curses.echo()
                    self.stdscr.nodelay(False)
                    self.stdscr.addstr(h-6,0,"Set volume 0-100: ")
                    v = self.stdscr.getstr(h-6, 18).decode("utf-8").strip()
                    self.stdscr.nodelay(True)
                    curses.noecho()
                    try:
                        vol = int(v)
                        self.player.set_volume(vol)
                        self.message = f"Volume set {vol}"
                    except:
                        self.message = "Invalid volume"
                elif ch in (ord('s'), ord('S')):
                    curses.echo()
                    self.stdscr.nodelay(False)
                    self.stdscr.addstr(h-6,0,"Save playlist path: ")
                    pth = self.stdscr.getstr(h-6, 25).decode("utf-8").strip()
                    self.stdscr.nodelay(True)
                    curses.noecho()
                    if pth:
                        save_playlist_to(pth, self.player.queue)
                        self.message = f"Saved {pth}"
                elif ch in (ord('o'), ord('O')):
                    curses.echo()
                    self.stdscr.nodelay(False)
                    self.stdscr.addstr(h-6,0,"Load playlist path: ")
                    pth = self.stdscr.getstr(h-6, 25).decode("utf-8").strip()
                    self.stdscr.nodelay(True)
                    curses.noecho()
                    if pth:
                        loaded = load_playlist_from(pth)
                        if loaded:
                            self.player.queue = loaded
                            self.message = f"Loaded {len(loaded)} items"
                        else:
                            self.message = "Load failed/empty"
