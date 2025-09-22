#!/usr/bin/env python3
import threading
import queue
import subprocess
import time
import curses
from yt_dlp import YoutubeDL
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import shutil

# Shared
result_queue = queue.Queue()
search_results = []      # hasil search (title + id)
stop_event = threading.Event()

# cache dengan batasan
MAX_CACHE = 50
audio_cache = OrderedDict()  # video_id -> {"title":..., "url":...}

PAGE_SIZE = 10
MAX_RESULTS = 200  # max search result disimpan di RAM

# preload pool (lebih agresif = 4 worker)
preload_executor = ThreadPoolExecutor(max_workers=4)


def progressive_search(query, max_results=50):
    """Ambil hasil search cepat (judul+id)"""
    ydl_opts = {
        "default_search": f"ytsearch{max_results}:{query}",
        "extract_flat": "in_playlist",
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            for e in info.get("entries", []):
                if stop_event.is_set():
                    break
                result_queue.put(e)
                time.sleep(0.02)  # kasih waktu ke UI
    except Exception as ex:
        result_queue.put({"title": f"[Search error: {ex}]", "id": None})


def build_video_url(video_id):
    if not video_id:
        return None
    if video_id.startswith("http"):
        return video_id
    return f"https://www.youtube.com/watch?v={video_id}"


def preload_audio(video_id):
    """Resolve audio URL (progressive per item)"""
    if not video_id or video_id in audio_cache:
        return
    video_url = build_video_url(video_id)
    # format filter: ambil audio ringan lebih cepat
    ydl_opts = {
        "format": "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            url = info.get("url")
            if not url and info.get("formats"):
                for f in reversed(info["formats"]):
                    if f.get("acodec") and f.get("acodec") != "none":
                        url = f.get("url")
                        break
            title = info.get("title", video_id)
            # masukin cache dengan batasan
            audio_cache[video_id] = {"title": title, "url": url}
            if len(audio_cache) > MAX_CACHE:
                audio_cache.popitem(last=False)
    except Exception as e:
        audio_cache[video_id] = {"title": f"[preload error: {e}]", "url": None}


def preload_async(video_id):
    preload_executor.submit(preload_audio, video_id)


def play_stream(stream_url):
    if not stream_url:
        return

    # cek player yang tersedia
    if shutil.which("ffplay"):
        cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", stream_url]
    elif shutil.which("vlc"):
        cmd = ["vlc", "--intf", "dummy", "--play-and-exit", stream_url]
    elif shutil.which("mpv"):
        cmd = ["mpv", "--no-video", stream_url]
    elif shutil.which("termux-media-player"):
        cmd = ["termux-media-player", "play", stream_url]
    else:
        print("No supported player found (need ffplay, vlc, mpv, or termux-media-player)")
        return

    subprocess.Popen(cmd)


def curses_main(stdscr, query):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)

    selected = 0
    top_line = 0
    needs_redraw = True

    while not stop_event.is_set():
        updated = False
        # ambil hasil search baru
        try:
            while True:
                e = result_queue.get_nowait()
                search_results.append(e)
                if len(search_results) > MAX_RESULTS:
                    del search_results[0:len(search_results) - MAX_RESULTS]
                updated = True
        except queue.Empty:
            pass

        if updated or needs_redraw:
            stdscr.erase()
            height, width = stdscr.getmaxyx()
            stdscr.addnstr(0, 0, f"Search: {query}  —  results: {len(search_results)}", width - 1)
            stdscr.addnstr(1, 0, "(↑/↓ to scroll, Enter to play, q to quit)", width - 1)

            # paging
            if selected < top_line:
                top_line = selected
            elif selected >= top_line + PAGE_SIZE:
                top_line = selected - PAGE_SIZE + 1

            # preload buffer: 1 page + 3 item ekstra
            buffer_end = min(len(search_results), top_line + PAGE_SIZE + 3)
            visible = range(top_line, buffer_end)

            # preload untuk visible + buffer
            for idx in visible:
                vid = search_results[idx].get("id")
                if vid and vid not in audio_cache:
                    preload_async(vid)

            # render page
            for i, idx in enumerate(visible):
                item = search_results[idx]
                title = (item.get("title") or "(no title)").strip()
                uploader = item.get("uploader") or ""
                vid = item.get("id")
                ready = vid in audio_cache and audio_cache[vid].get("url")

                pref = "➤" if idx == selected else "  "
                mark = "*" if ready else " "
                line = f"{pref}{mark} {idx+1}. {title} - {uploader}"

                if ready:
                    stdscr.addnstr(3 + i, 0, line, width - 1, curses.color_pair(1))
                else:
                    stdscr.addnstr(3 + i, 0, line, width - 1)

            stdscr.refresh()
            needs_redraw = False

        # input
        try:
            key = stdscr.getch()
        except Exception:
            key = -1

        if key == curses.KEY_UP and selected > 0:
            selected -= 1
            needs_redraw = True
        elif key == curses.KEY_DOWN and selected < len(search_results) - 1:
            selected += 1
            needs_redraw = True
        elif key in (curses.KEY_ENTER, 10, 13):
            if 0 <= selected < len(search_results):
                vid = search_results[selected].get("id")

                def resolve_and_play():
                    if vid not in audio_cache:
                        preload_audio(vid)
                    stream = audio_cache.get(vid, {}).get("url")
                    if stream:
                        play_stream(stream)

                threading.Thread(target=resolve_and_play, daemon=True).start()
                needs_redraw = True
        elif key == ord("q"):
            stop_event.set()
            break

        time.sleep(0.1)  # loop lebih santai

    stdscr.erase()
    stdscr.addnstr(0, 0, "Exiting...", stdscr.getmaxyx()[1] - 1)
    stdscr.refresh()
    time.sleep(0.3)


if __name__ == "__main__":
    q = input("Search YouTube: ").strip()
    if not q:
        print("No query entered.")
    else:
        threading.Thread(target=progressive_search, args=(q, 50), daemon=True).start()
        curses.wrapper(curses_main, q)
        print("Bye.")

