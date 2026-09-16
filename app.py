#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
   VIDDROP — POINT D'ENTRÉE CLOUD & WSGI (RENDER, GUNICORN, RAILWAY)
═══════════════════════════════════════════════════════════════════════════════
Compatible avec :
- Gunicorn : gunicorn app:app
- Python direct : python app.py
- Render Start Command par défaut
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import re
import json
import time
import threading
import shutil
import tempfile
import urllib.parse
import urllib.request
import mimetypes

PROGRESS_TASKS = {}

def fetch_oembed_info(url):
    """Extraction rapide et sans blocage des métadonnées (titre, miniature, créateur)."""
    try:
        req_url = f"https://www.youtube.com/oembed?url={urllib.parse.quote(url)}&format=json"
        req = urllib.request.Request(req_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "title": data.get("title") or "Vidéo YouTube",
                "uploader": data.get("author_name") or "YouTube",
                "thumbnail": data.get("thumbnail_url") or "",
                "duration_string": "HD",
                "quality": "🌟 Ultra HD 4K (2160p)"
            }
    except Exception:
        pass
    m = re.search(r'(?:v=|\/|youtu\.be\/|embed\/|shorts\/)([a-zA-Z0-9_-]{11})', url)
    if m:
        video_id = m.group(1)
        return {
            "title": "Vidéo YouTube",
            "uploader": "YouTube",
            "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            "duration_string": "HD",
            "quality": "🌟 Ultra HD 4K (2160p)"
        }
    return None

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT_DIR, "web")
STATIC_DIR = os.path.join(WEB_DIR, "static")
ANDROID_DIR = os.path.join(ROOT_DIR, "android")

PORT = int(os.environ.get("PORT", 8080))

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# Détection FFmpeg
FFMPEG_PATH = None
candidates = [
    shutil.which("ffmpeg"),
    os.path.join(ROOT_DIR, "ffmpeg.exe"),
    r"C:\Program Files\FFmpeg\bin\ffmpeg.exe",
    r"C:\ffmpeg\bin\ffmpeg.exe",
]
for c in candidates:
    if c and os.path.isfile(c):
        FFMPEG_PATH = c
        break

if not FFMPEG_PATH:
    try:
        import imageio_ffmpeg
        FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass


def get_mime_type(path):
    mime, _ = mimetypes.guess_type(path)
    if mime:
        return mime
    if path.endswith(".json"):
        return "application/json"
    if path.endswith(".js"):
        return "application/javascript"
    if path.endswith(".css"):
        return "text/css"
    if path.endswith(".png"):
        return "image/png"
    if path.endswith(".ico"):
        return "image/x-icon"
    return "text/html"


def handle_info(query):
    url = query.get("url", [""])[0].strip()
    if not url:
        return json.dumps({"error": "Lien manquant"}).encode("utf-8"), 400

    if not yt_dlp:
        return json.dumps({
            "title": "Vidéo prête à télécharger",
            "uploader": "Réseau Social",
            "duration_string": "HD",
            "thumbnail": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500",
            "quality": "Haute Qualité"
        }).encode("utf-8"), 200

    try:
        ydl_opts = {
            'skip_download': True,
            'no_warnings': True,
            'noplaylist': True,
            'socket_timeout': 15,
            'extractor_args': {
                'youtube': {
                    'player_client': ['visionos', 'android'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            }
        }
        if FFMPEG_PATH:
            ydl_opts['ffmpeg_location'] = FFMPEG_PATH

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        heights = [f.get('height') for f in info.get('formats', []) if f.get('height')]
        max_h = max(heights) if heights else 0
        if max_h >= 2160:
            quality_label = "🌟 Ultra HD 4K (2160p)"
        elif max_h >= 1440:
            quality_label = "✨ Quad HD 2K (1440p)"
        elif max_h >= 1080:
            quality_label = "💎 Full HD (1080p)"
        elif max_h >= 720:
            quality_label = "📺 HD (720p)"
        elif max_h > 0:
            quality_label = f"Standard ({max_h}p)"
        else:
            quality_label = "Qualité Maximale (HD / 4K)"

        data = {
            "title": info.get("title", "Vidéo"),
            "uploader": info.get("uploader") or info.get("channel") or "Réseau Social",
            "duration_string": str(info.get("duration_string") or "HD"),
            "thumbnail": info.get("thumbnail") or "",
            "quality": quality_label,
            "max_height": max_h
        }
        return json.dumps(data, ensure_ascii=False).encode("utf-8"), 200
    except Exception as e:
        fallback = fetch_oembed_info(url)
        if fallback:
            return json.dumps(fallback, ensure_ascii=False).encode("utf-8"), 200
        data = {
            "title": "Vidéo trouvée",
            "uploader": "Réseau Social",
            "duration_string": "HD",
            "thumbnail": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500",
            "quality": "Haute Définition",
            "warning": str(e)
        }
        return json.dumps(data, ensure_ascii=False).encode("utf-8"), 200


def handle_progress(query):
    task_id = query.get("id", [""])[0]
    data = PROGRESS_TASKS.get(task_id, {
        "status": "waiting",
        "percent": 5.0,
        "msg": "Connexion au flux en cours..."
    })
    return json.dumps(data, ensure_ascii=False).encode("utf-8"), 200


def app(environ, start_response):
    """Point d'entrée WSGI universel (appelé par Gunicorn)."""
    raw_path = environ.get("PATH_INFO", "/")
    path = raw_path if raw_path else "/"
    query_string = environ.get("QUERY_STRING", "")
    query = urllib.parse.parse_qs(query_string)

    # 1. API INFO
    if path == "/api/info":
        body, status = handle_info(query)
        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Access-Control-Allow-Origin", "*"),
        ]
        status_str = f"{status} OK" if status == 200 else f"{status} Error"
        start_response(status_str, headers)
        return [body]

    # 2. API PROGRESS
    if path == "/api/progress":
        body, status = handle_progress(query)
        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Access-Control-Allow-Origin", "*"),
        ]
        status_str = f"{status} OK" if status == 200 else f"{status} Error"
        start_response(status_str, headers)
        return [body]

    # 3. API DOWNLOAD
    if path == "/api/download":
        url = query.get("url", [""])[0].strip()
        fmt = query.get("format", ["MP4"])[0].upper()
        task_id = query.get("task_id", [""])[0]

        if not url:
            body = b"Lien requis"
            start_response("400 Bad Request", [("Content-Type", "text/plain"), ("Content-Length", str(len(body)))])
            return [body]

        if not yt_dlp:
            body = b"yt-dlp non installe sur le serveur"
            start_response("500 Server Error", [("Content-Type", "text/plain"), ("Content-Length", str(len(body)))])
            return [body]

        if task_id:
            PROGRESS_TASKS[task_id] = {
                "status": "downloading",
                "percent": 8.0,
                "msg": "⚡ Préparation du flux..."
            }

        temp_dir = tempfile.mkdtemp(prefix="viddrop_")
        try:
            def progress_hook(d):
                if not task_id:
                    return
                status = d.get('status')
                if status == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    downloaded = d.get('downloaded_bytes', 0)
                    if total > 0:
                        pct = round((downloaded / total) * 100.0, 1)
                    else:
                        raw_pct = d.get('_percent_str', '0%')
                        clean_pct = re.sub(r'[^\d\.]', '', raw_pct)
                        pct = float(clean_pct) if clean_pct else 8.0
                    speed = d.get('_speed_str', '')
                    clean_speed = re.sub(r'\x1b\[[0-9;]*m', '', speed).strip()
                    clamped = max(8.0, min(pct, 96.0))
                    msg = f"⚡ {clamped:.1f}% ({clean_speed})" if clean_speed else f"⚡ {clamped:.1f}%"
                    PROGRESS_TASKS[task_id] = {
                        'status': 'downloading',
                        'percent': clamped,
                        'speed': clean_speed,
                        'msg': msg
                    }
                elif status == 'finished':
                    PROGRESS_TASKS[task_id] = {
                        'status': 'processing',
                        'percent': 98.0,
                        'msg': "⚙ Finalisation et assemblage du fichier..."
                    }

            ydl_opts = {
                'outtmpl': os.path.join(temp_dir, '%(title).80s.%(ext)s'),
                'windowsfilenames': True,
                'trim_file_name': 80,
                'noplaylist': True,
                'no_warnings': True,
                'socket_timeout': 30,
                'retries': 5,
                'progress_hooks': [progress_hook],
                'extractor_args': {
                    'youtube': {
                        'player_client': ['visionos', 'android'],
                    }
                },
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                }
            }

            if FFMPEG_PATH:
                ydl_opts['ffmpeg_location'] = FFMPEG_PATH

            if fmt == "MP3":
                if FFMPEG_PATH:
                    ydl_opts.update({
                        'format': 'bestaudio/best',
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '320',
                        }],
                    })
                else:
                    ydl_opts.update({'format': 'bestaudio[ext=m4a]/bestaudio/best'})
            elif fmt == "WAV":
                if FFMPEG_PATH:
                    ydl_opts.update({
                        'format': 'bestaudio/best',
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'wav',
                        }],
                    })
                else:
                    ydl_opts.update({'format': 'bestaudio/best'})
            elif fmt == "MP4_1080":
                if FFMPEG_PATH:
                    ydl_opts.update({
                        'format': 'bestvideo[height<=1080]+bestaudio/best',
                        'merge_output_format': 'mp4',
                    })
                else:
                    ydl_opts.update({'format': 'best[height<=1080]/best'})
            elif fmt == "MP4_720":
                if FFMPEG_PATH:
                    ydl_opts.update({
                        'format': 'bestvideo[height<=720]+bestaudio/best',
                        'merge_output_format': 'mp4',
                    })
                else:
                    ydl_opts.update({'format': 'best[height<=720]/best'})
            elif fmt == "WEBM":
                ydl_opts.update({
                    'format': 'bestvideo+bestaudio/best',
                    'merge_output_format': 'webm'
                })
            else:  # MP4 (Qualité Maximale 4K / 2K / 1080p) ou MOV
                if FFMPEG_PATH:
                    ydl_opts.update({
                        'format': 'bestvideo+bestaudio/best',
                        'merge_output_format': 'mp4' if fmt == "MP4" else 'mov',
                    })
                else:
                    ydl_opts.update({'format': 'bestvideo+bestaudio/best'})

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            downloaded_files = [
                os.path.join(temp_dir, f) for f in os.listdir(temp_dir)
                if os.path.isfile(os.path.join(temp_dir, f)) and not f.endswith('.part') and not f.endswith('.ytdl')
            ]

            if not downloaded_files:
                shutil.rmtree(temp_dir, ignore_errors=True)
                body = b"Fichier introuvable"
                start_response("500 Error", [("Content-Type", "text/plain")])
                return [body]

            target_file = downloaded_files[0]
            filename = os.path.basename(target_file)
            file_size = os.path.getsize(target_file)
            clean_ascii = re.sub(r'[^\x20-\x7E]', '_', filename).replace('"', '')
            safe_name = urllib.parse.quote(filename, encoding='utf-8')
            mime_type = get_mime_type(target_file)

            if task_id:
                PROGRESS_TASKS[task_id] = {
                    'status': 'done',
                    'percent': 100.0,
                    'msg': "✅ Fichier prêt ! Téléchargement en cours..."
                }

            headers = [
                ("Content-Type", mime_type),
                ("Content-Length", str(file_size)),
                ("Content-Disposition", f'attachment; filename="{clean_ascii}"; filename*=UTF-8\'\'{safe_name}'),
                ("X-Content-Type-Options", "nosniff"),
                ("Access-Control-Allow-Origin", "*"),
            ]
            start_response("200 OK", headers)

            def file_stream():
                try:
                    with open(target_file, "rb") as f:
                        while True:
                            chunk = f.read(64 * 1024)
                            if not chunk:
                                break
                            yield chunk
                finally:
                    if task_id:
                        def _cleanup():
                            time.sleep(120)
                            PROGRESS_TASKS.pop(task_id, None)
                        threading.Thread(target=_cleanup, daemon=True).start()
                    shutil.rmtree(temp_dir, ignore_errors=True)

            return file_stream()

        except Exception as e:
            if task_id:
                PROGRESS_TASKS[task_id] = {
                    'status': 'error',
                    'percent': 0.0,
                    'msg': f"❌ Erreur : {str(e)[:50]}"
                }
            shutil.rmtree(temp_dir, ignore_errors=True)
            body = f"Erreur : {e}".encode("utf-8")
            start_response("500 Server Error", [("Content-Type", "text/plain")])
            return [body]

    # 3. FICHIERS STATIQUES & PAGES
    if path in ("/", "/index.html"):
        target_path = os.path.join(WEB_DIR, "index.html")
    elif path.startswith("/static/"):
        target_path = os.path.join(WEB_DIR, path.lstrip("/"))
    elif path.startswith("/android/"):
        target_path = os.path.join(ROOT_DIR, path.lstrip("/"))
    else:
        target_path = os.path.join(WEB_DIR, path.lstrip("/"))

    if os.path.isfile(target_path):
        mime_type = get_mime_type(target_path)
        with open(target_path, "rb") as f:
            content = f.read()
        headers = [
            ("Content-Type", mime_type),
            ("Content-Length", str(len(content))),
            ("Access-Control-Allow-Origin", "*"),
        ]
        start_response("200 OK", headers)
        return [content]

    # 404
    body = b"Fichier non trouve"
    start_response("404 Not Found", [("Content-Type", "text/plain"), ("Content-Length", str(len(body)))])
    return [body]


if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    print("=" * 68)
    print("🌐 VIDDROP — SERVEUR WSGI / CLOUD (RENDER / RAILWAY / LOCAL)")
    print(f"🚀 Serveur actif sur : http://localhost:{PORT}")
    print("=" * 68)
    httpd = make_server("", PORT, app)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
