# yt_wrapper.py
import yt_dlp

def search_youtube(query: str, max_results: int = 20):
    """Search YouTube and return list of (title, duration, url)."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "format": "bestaudio/best",
        "default_search": "ytsearch",
    }
    results = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
        for e in info.get("entries", []):
            title = e.get("title", "Unknown")
            duration = e.get("duration")

            # fallback handling
            try:
                minutes = int(duration) // 60
                seconds = int(duration) % 60
                dur_str = f"{minutes}:{seconds:02d}"
            except Exception:
                dur_str = "??:??"

            url = f"https://www.youtube.com/watch?v={e.get('id')}"
            results.append((title, dur_str, url))
    return results

def get_audio_url(video_url: str):
    """Return direct audio stream URL for a YouTube video."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "bestaudio/best",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(video_url, download=False)
            return info.get("url")
        except Exception:
            return None

