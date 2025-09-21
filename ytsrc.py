import subprocess
from yt_dlp import YoutubeDL

def search_youtube(query, max_results=5):
    ydl_opts = {
        'quiet': True,
        'default_search': f'ytsearch{max_results}',
        'extract_flat': 'in_playlist',  # lebih cepat, ambil metadata saja
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        return info['entries']

def resolve_and_play(video_url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        url = info['url']
        print(f"Playing: {info.get('title','Unknown')}")
        subprocess.run(["ffplay", "-nodisp", "-autoexit", url])

if __name__ == "__main__":
    q = input("Search YouTube: ")
    results = search_youtube(q)

    print("\nSearch Results:")
    for i, video in enumerate(results, start=1):
        title = video.get("title", "Unknown Title")
        channel = video.get("uploader", "Unknown Channel")
        print(f"{i}. {title} - {channel}")

    choice = int(input("\nPilih nomor video: ")) - 1
    chosen = results[choice]
    resolve_and_play(chosen['url'])
