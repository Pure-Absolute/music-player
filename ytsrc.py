#!/usr/bin/env python3
import curses, time, subprocess, json, re, requests, shutil

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ------------------ SEARCH ------------------
def yt_search(query, limit=20):
    url = f"https://www.youtube.com/results?search_query={query}"
    r = requests.get(url, headers=HEADERS)
    m = re.search(r"var ytInitialData = ({.*?});", r.text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        print("Parse error:", e)
        return []
    results = []
    contents = (
        data.get("contents", {})
        .get("twoColumnSearchResultsRenderer", {})
        .get("primaryContents", {})
        .get("sectionListRenderer", {})
        .get("contents", [])
    )
    for section in contents:
        items = section.get("itemSectionRenderer", {}).get("contents", [])
        for item in items:
            v = item.get("videoRenderer")
            if not v:
                continue
            vid = v.get("videoId")
            title = "".join([t.get("text", "") for t in v.get("title", {}).get("runs", [])])
            chan = v.get("ownerText", {}).get("runs", [{}])[0].get("text", "")
            results.append({"id": vid, "title": title, "channel": chan})
            if len(results) >= limit:
                return results
    return results

# ------------------ RESOLVE ------------------
def yt_get_audio_url(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    r = requests.get(url, headers=HEADERS)
    m = re.search(r"var ytInitialPlayerResponse = ({.*?});", r.text, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        print("Player parse error:", e)
        return None
    fmts = data.get("streamingData", {}).get("adaptiveFormats", [])
    for f in fmts:
        mime = f.get("mimeType", "")
        if mime.startswith("audio/"):
            return f.get("url")
    return None

# ------------------ PLAYER ------------------
def play_stream(stream_url):
    if not stream_url:
        return
    if shutil.which("ffplay"):
        cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", stream_url]
    elif shutil.which("mpv"):
        cmd = ["mpv", "--no-video", stream_url]
    elif shutil.which("vlc"):
        cmd = ["vlc", "--intf", "dummy", "--play-and-exit", stream_url]
    elif shutil.which("termux-media-player"):
        cmd = ["termux-media-player", "play", stream_url]
    else:
        print("No player found")
        return
    subprocess.Popen(cmd)

# ------------------ UI ------------------
def curses_main(stdscr, query):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)

    results = yt_search(query, limit=30)
    selected = 0
    top = 0
    PAGE = 10

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        stdscr.addnstr(0, 0, f"Search: {query} — results: {len(results)}", w - 1)
        stdscr.addnstr(1, 0, "(↑/↓ scroll, Enter play, q quit)", w - 1)

        if selected < top:
            top = selected
        elif selected >= top + PAGE:
            top = selected - PAGE + 1

        visible = range(top, min(len(results), top + PAGE))
        for i, idx in enumerate(visible):
            r = results[idx]
            pref = "➤" if idx == selected else "  "
            line = f"{pref}{idx+1}. {r['title']} - {r['channel']}"
            stdscr.addnstr(3 + i, 0, line, w - 1)

        stdscr.refresh()

        try:
            key = stdscr.getch()
        except Exception:
            key = -1

        if key == curses.KEY_UP and selected > 0:
            selected -= 1
        elif key == curses.KEY_DOWN and selected < len(results) - 1:
            selected += 1
        elif key in (curses.KEY_ENTER, 10, 13):
            vid = results[selected]["id"]
            url = yt_get_audio_url(vid)
            if url:
                play_stream(url)
        elif key == ord("q"):
            break

        time.sleep(0.05)

# ------------------ MAIN ------------------
if __name__ == "__main__":
    q = input("Search YouTube: ").strip()
    if not q:
        print("No query.")
    else:
        curses.wrapper(curses_main, q)
