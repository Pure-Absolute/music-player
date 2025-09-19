# ui.py
import curses
import threading
import time
import os
from utils import format_time
import random
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
        self.screen = "home"  # home, queue, add, search
        self.cursor = 0
        self.scroll = 0
        self.running = True
        self.marquee_offsets = {}
        self.search_results = []
        self.search_selected = set()
        self.search_query = ""
        self.message = ""
        self.input_lock = threading.Lock()
        self.playlist_save_path = None

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

    def draw_home(self, h, w):
        # center ASCII art
        y = 2
        for line in ASCII_ART:
            self.stdscr.addstr(y, max(0,(w - len(line))//2), line, curses.color_pair(5))
            y += 1
        self.stdscr.addstr(y+1, max(0,(w-30)//2), "Press L for Queue, A Add, / Search, Q Quit", curses.color_pair(1))

    def _marquee(self, key, text, width):
        # returns substring starting at offset
        if len(text) <= width:
            return text
        off = self.marquee_offsets.get(key, 0)
        view = text[off:off+width]
        # advance
        off = (off + 1) % (len(text))
        self.marquee_offsets[key] = off
        return view

    def draw_queue(self, h, w):
        self.stdscr.addstr(1, 0, "Queue (arrow up/down to navigate, Enter to play, R repeat, S shuffle, P pause)".ljust(w), curses.color_pair(1))
        visible = h - 6
        q = self.player.queue
        if self.player.shuffle:
            shuffle_note = " (shuffle ON)"
        else:
            shuffle_note = ""
        self.stdscr.addstr(2, 0, f"RepeatSong: {self.player.repeat_song}  RepeatPlaylist: {self.player.repeat_playlist}  Shuffle:{self.player.shuffle}{shuffle_note}".ljust(w), curses.color_pair(2))
        start = max(0, self.cursor - visible//2)
        for i in range(start, min(len(q), start + visible)):
            t = q[i]["title"]
            marker = "➤ " if i == self.cursor else "  "
            line_w = w - 6
            key = f"q{i}"
            display = self._marquee(key, t, line_w) if i == self.cursor else (t[:line_w])
            color = curses.color_pair(3) if i == self.player.idx else curses.color_pair(2)
            self.stdscr.addstr(4 + i - start, 0, (marker + display).ljust(w-1), color)

    def draw_playing_bar(self, h, w):
        if 0 <= self.player.idx < len(self.player.queue):
            cur = self.player.queue[self.player.idx]
            title = cur["title"]
            s = f"Now: {title}"
            s_trunc = s if len(s) < w-2 else self._marquee("now", s, w-10)
            self.stdscr.addstr(h-4, 0, s_trunc.ljust(w-1), curses.color_pair(3))
            # progress
            dur = self.player.duration
            elapsed = self.player.elapsed
            if dur:
                barlen = max(10, w-30)
                filled = int(barlen * (elapsed / dur)) if dur else 0
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

    def loop(self):
        last_check = 0
        while self.running:
            self.stdscr.erase()
            h, w = self.stdscr.getmaxyx()
            # header
            self.stdscr.addstr(0, 0, "🎵 Termux Music Player (Home L:Queue A:Add /:Search)".ljust(w), curses.color_pair(1))

            # screen specific
            if self.screen == "home":
                self.draw_home(h, w)
            elif self.screen == "queue":
                self.draw_queue(h, w)
            elif self.screen == "add":
                self.stdscr.addstr(2, 0, "Add mode (A). Enter URL or Title (top result will be auto-added). Press ESC to cancel.".ljust(w), curses.color_pair(1))
            elif self.screen == "search":
                self.stdscr.addstr(2, 0, f"Search results for '{self.search_query}' (press numbers to toggle select, A to add selected)".ljust(w), curses.color_pair(1))
                for i, item in enumerate(self.search_results):
                    mark = "[x]" if i in self.search_selected else "[ ]"
                    t = item["title"]
                    line = f"{i+1}. {mark} {t}"
                    self.stdscr.addstr(4+i, 0, line[:w-1], curses.color_pair(2))

            # playing bar & footer
            self.draw_playing_bar(h,w)
            controls = "Controls: L Queue  A Add  / Search  Space Pause  Enter Play  N Next  B Prev  R RepeatSong  T RepeatPlaylist  H Shuffle  V Volume  S Save  O Load  Q Quit"
            self.stdscr.addstr(h-1, 0, controls[:w-1], curses.color_pair(5))
            self.draw_message(h,w)
            self.stdscr.refresh()

            # every 0.4s update marquee and check if song ended to auto-play next
            now = time.time()
            if now - last_check > 0.4:
                last_check = now
                # if playing ended (mpv process ended but player.playing false)
                if not self.player.playing and not self.player.loading and self.player.idx != -1:
                    # attempt auto-next
                    if self.player._mpv_proc is None:
                        # ended
                        if self.player.repeat_song:
                            self.player.play_index(self.player.idx)
                        else:
                            # next or repeat playlist
                            if self.player.idx + 1 < len(self.player.queue):
                                self.player.play_index(self.player.idx + 1)
                            else:
                                if self.player.repeat_playlist and len(self.player.queue)>0:
                                    self.player.play_index(0)
                # update marquee offsets (advance)
                for k in list(self.marquee_offsets.keys()):
                    self.marquee_offsets[k] = (self.marquee_offsets.get(k,0)+1) % 200

            # handle input
            try:
                ch = self.stdscr.getch()
            except Exception:
                ch = -1

            if ch == -1:
                time.sleep(0.04)
                continue

            # KEY HANDLERS
            if ch in (ord('q'), ord('Q')):
                self.player.stop()
                self.running = False
                break
            if ch in (ord('l'), ord('L')):
                self.screen = "queue"
            elif ch in (ord('h'), ord('H')):
                # toggle shuffle
                self.player.shuffle = not self.player.shuffle
                if self.player.shuffle:
                    random.shuffle(self.player.queue)
                self.message = f"Shuffle set to {self.player.shuffle}"
            elif ch in (ord('a'), ord('A')):
                # go into add mode, blocking input for query
                self.screen = "add"
                curses.echo()
                self.stdscr.nodelay(False)
                self.stdscr.addstr(4,0,"Enter URL or Title (top result will be added): ")
                q = self.stdscr.getstr(4, 42).decode("utf-8").strip()
                self.stdscr.nodelay(True)
                curses.noecho()
                if q:
                    # fetch top result in background
                    self.message = "Searching..."
                    def add_worker():
                        items = self.player.fetch_info(q, max_results=1)
                        if items:
                            self.player.add_top(items[0])
                            self.message = f"Added: {items[0]['title']}"
                        else:
                            self.message = "Not found."
                    threading.Thread(target=add_worker, daemon=True).start()
                self.screen = "home"
            elif ch == ord('/'):
                # search mode: allow multi-select
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
                # add selected to queue
                sel = sorted(list(self.search_selected))
                if not sel and self.search_results:
                    # if none selected, add the first by default
                    sel = [0]
                items = [self.search_results[i] for i in sel if i < len(self.search_results)]
                self.player.add_items(items)
                self.message = f"Added {len(items)} items to queue"
                # reset
                self.search_selected = set()
                self.screen = "home"
            elif self.screen == "search" and ch in (ord('1'),ord('2'),ord('3'),ord('4'),ord('5'),ord('6'),ord('7'),ord('8')):
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
                elif ch in (10, 13):  # Enter
                    self.player.play_index(self.cursor)
                elif ch in (ord('n'), ord('N')):
                    # next
                    self.player.next()
                elif ch in (ord('b'), ord('B')):
                    self.player.prev()
                elif ch in (ord(' '),):
                    # pause toggle
                    self.player.toggle_pause()
                elif ch in (ord('r'), ord('R')):
                    self.player.repeat_song = not self.player.repeat_song
                    self.message = f"RepeatSong = {self.player.repeat_song}"
                elif ch in (ord('t'), ord('T')):
                    self.player.repeat_playlist = not self.player.repeat_playlist
                    self.message = f"RepeatPlaylist = {self.player.repeat_playlist}"
                elif ch in (ord('v'), ord('V')):
                    # volume adjust: mini prompt
                    curses.echo()
                    self.stdscr.nodelay(False)
                    self.stdscr.addstr(h-6,0,"Set volume 0-100: ")
                    v = self.stdscr.getstr(h-6, 18).decode("utf-8").strip()
                    self.stdscr.nodelay(True)
                    curses.noecho()
                    try:
                        vol = int(v)
                        self.player.set_volume(vol)
                        self.message = f"Volume set to {vol}"
                    except:
                        self.message = "Invalid volume"
                elif ch in (ord('s'), ord('S')):
                    # save playlist: ask path
                    curses.echo()
                    self.stdscr.nodelay(False)
                    self.stdscr.addstr(h-6,0,"Save playlist path (full path or ./name): ")
                    pth = self.stdscr.getstr(h-6, 38).decode("utf-8").strip()
                    self.stdscr.nodelay(True)
                    curses.noecho()
                    if pth:
                        try:
                            save_playlist_to(pth, self.player.queue)
                            self.message = f"Saved to {pth if pth.endswith('.json') else pth+'.json'}"
                        except Exception as e:
                            self.message = f"Save failed: {e}"
                elif ch in (ord('o'), ord('O')):
                    # load playlist
                    curses.echo()
                    self.stdscr.nodelay(False)
                    self.stdscr.addstr(h-6,0,"Load playlist path: ")
                    pth = self.stdscr.getstr(h-6, 20).decode("utf-8").strip()
                    self.stdscr.nodelay(True)
                    curses.noecho()
                    if pth:
                        loaded = load_playlist_from(pth)
                        if loaded:
                            self.player.queue = loaded
                            self.message = f"Loaded {len(loaded)} items"
                        else:
                            self.message = "Load failed / empty"
                elif ch in (ord('h'), ord('H')):
                    # go home
                    self.screen = "home"
            else:
                # global shortcuts
                if ch in (ord('p'), ord('P')):
                    # play current or first
                    if self.player.idx == -1 and self.player.queue:
                        self.player.play_index(0)
                    elif self.player.idx >= 0:
                        self.player.play_index(self.player.idx)
                elif ch in (ord('n'), ord('N')):
                    self.player.next()
                elif ch in (ord('b'), ord('B')):
                    self.player.prev()

            # small sleep to avoid hogging CPU
            time.sleep(0.02)
