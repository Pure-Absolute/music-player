import yt_dlp

def search_youtube(query, max_results=5):
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
        "default_search": "ytsearch",
    }
    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            entries = info.get("entries", [])
            for e in entries[:max_results]:
                title = e.get("title", "Unknown Title")
                dur = e.get("duration")
                if dur is None:
                    dur_str = "??:??"
                else:
                    m, s = divmod(int(dur), 60)
                    dur_str = f"{m}:{s:02d}"
                url = f"https://www.youtube.com/watch?v={e.get('id')}"
                results.append((title, dur_str, url))
    except Exception as e:
        print(f"[search_youtube ERROR] {e}")
    return results


def get_audio_url(video_url):
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "skip_download": True,
        "extract_flat": False,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            # direct url
            if "url" in info:
                return info["url"]
            # playlist entry
            if "entries" in info and info["entries"]:
                return info["entries"][0].get("url")
            # fallback: first available format
            for f in info.get("formats", []):
                if f.get("url"):
                    return f["url"]
    except Exception as e:
        print(f"[get_audio_url ERROR] {e}")
    return None
