# ui_client.py
import curses, time, threading, queue, subprocess
from yt_dlp import YoutubeDL
import socket, json

result_queue = queue.Queue()
search_results = []
selected = 0
PAGE_SIZE = 10

# komunikasi ke resolver (script 2) pakai socket
SERVER_ADDR = ("127.0.0.1", 5050)

def send_to_resolver(video_id):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(SERVER_ADDR)
        s.sendall(json.dumps({"id": video_id}).encode("utf-8"))

def progressive_search(query, max_results=50):
    ydl_opts = {
        "default_search": f"ytsearch{max_results}:{query}",
        "extract_flat": "in_playlist",
        "quiet": True,
        "no_warnings": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        for e in info.get("entries", []):
            result_queue.put(e)
            time.sleep(0.02)

def curses_main(stdscr, query):
    global selected
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)

    top_line = 0

    while True:
        try:
            while True:
                e = result_queue.get_nowait()
                search_results.append(e)
        except queue.Empty:
            pass

        stdscr.erase()
        height, width = stdscr.getmaxyx()
        stdscr.addnstr(0, 0, f"Search: {query}  — results: {len(search_results)}", width - 1)
        stdscr.addnstr(1, 0, "(↑/↓ to scroll, Enter to play, q to quit)", width - 1)

        # paging
        if selected < top_line:
            top_line = selected
        elif selected >= top_line + PAGE_SIZE:
            top_line = selected - PAGE_SIZE + 1

        visible = range(top_line, min(len(search_results), top_line + PAGE_SIZE))
        for i, idx in enumerate(visible):
            item = search_results[idx]
            title = (item.get("title") or "(no title)").strip()
            uploader = item.get("uploader") or ""
            line = f"{'➤' if idx == selected else '  '} {idx+1}. {title} - {uploader}"
            stdscr.addnstr(3 + i, 0, line, width - 1)

        stdscr.refresh()

        # input
        try:
            key = stdscr.getch()
        except Exception:
            key = -1

        if key == curses.KEY_UP and selected > 0:
            selected -= 1
        elif key == curses.KEY_DOWN and selected < len(search_results) - 1:
            selected += 1
        elif key in (curses.KEY_ENTER, 10, 13):
            if 0 <= selected < len(search_results):
                vid = search_results[selected].get("id")
                # kirim ke resolver
                send_to_resolver(vid)
        elif key == ord("q"):
            break

        time.sleep(0.05)


if __name__ == "__main__":
    q = input("Search YouTube: ").strip()
    if not q:
        print("No query entered.")
    else:
        threading.Thread(target=progressive_search, args=(q, 50), daemon=True).start()
        curses.wrapper(curses_main, q)
        print("Bye.")

