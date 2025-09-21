import subprocess
import threading
import queue
from yt_dlp import YoutubeDL
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.widgets import Frame, Box, TextArea

search_results = []
audio_urls = {}
result_queue = queue.Queue()
selected_index = 0
stop_flag = False

def progressive_search(query):
    """Worker: ambil hasil search satu-satu (judul + id)"""
    ydl_opts = {
        "default_search": "ytsearch20",
        "extract_flat": "in_playlist",
        "quiet": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        for entry in info["entries"]:
            if stop_flag:
                break
            result_queue.put(entry)

def preload_url(video_id):
    """Worker: siapkan direct audio URL untuk minim delay"""
    if video_id in audio_urls:
        return
    ydl_opts = {"format": "bestaudio/best", "quiet": True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_id, download=False)
        audio_urls[video_id] = {
            "title": info["title"],
            "url": info["url"],
        }

def play(video_id):
    """Play audio pakai ffplay"""
    url = audio_urls[video_id]["url"]
    title = audio_urls[video_id]["title"]
    print(f"\n▶ Playing: {title}\n")
    subprocess.run(["ffplay", "-nodisp", "-autoexit", url])

def ui(query):
    global selected_index

    text_area = TextArea(text="Loading...\n", focusable=True, scrollbar=True)
    frame = Frame(title="YouTube Search", body=Box(text_area, padding=1))
    layout = Layout(frame)

    kb = KeyBindings()

    @kb.add("up")
    def _(event):
        nonlocal selected_index
        if selected_index > 0:
            selected_index -= 1
            refresh_text()

    @kb.add("down")
    def _(event):
        nonlocal selected_index
        if selected_index < len(search_results) - 1:
            selected_index += 1
            refresh_text()

    @kb.add("enter")
    def _(event):
        if search_results:
            video = search_results[selected_index]
            vid = video["id"]
            play(vid)

    def refresh_text():
        lines = []
        for i, r in enumerate(search_results):
            prefix = "➤ " if i == selected_index else "  "
            lines.append(f"{prefix}{r['title']} - {r.get('uploader','?')}")
        text_area.text = "\n".join(lines)

    def updater():
        while not stop_flag:
            try:
                entry = result_queue.get(timeout=0.2)
                search_results.append(entry)
                threading.Thread(target=preload_url, args=(entry["id"],), daemon=True).start()
                refresh_text()
            except queue.Empty:
                continue

    threading.Thread(target=updater, daemon=True).start()

    app = Application(layout=layout, key_bindings=kb, full_screen=True)
    app.run()

if __name__ == "__main__":
    q = input("Search YouTube: ")
    threading.Thread(target=progressive_search, args=(q,), daemon=True).start()
    ui(q)
