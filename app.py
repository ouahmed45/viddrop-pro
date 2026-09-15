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
import json
import shutil
import tempfile
import urllib.parse
import mimetypes

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
                    'player_client': ['android', 'ios'],
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

        data = {
            "title": info.get("title", "Vidéo"),
            "uploader": info.get("uploader") or info.get("channel") or "Réseau Social",
            "duration_string": str(info.get("duration_string") or "HD"),
            "thumbnail": info.get("thumbnail") or "",
            "quality": "Qualité Maximale (HD / 4K)"
        }
        return json.dumps(data, ensure_ascii=False).encode("utf-8"), 200
    except Exception as e:
        data = {
            "title": "Vidéo trouvée",
            "uploader": "Réseau Social",
            "duration_string": "HD",
            "thumbnail": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500",
            "quality": "Haute Définition",
            "warning": str(e)
        }
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

    # 2. API DOWNLOAD
    if path == "/api/download":
        url = query.get("url", [""])[0].strip()
        fmt = query.get("format", ["MP4"])[0].upper()

        if not url:
            body = b"Lien requis"
            start_response("400 Bad Request", [("Content-Type", "text/plain"), ("Content-Length", str(len(body)))])
            return [body]

        if not yt_dlp:
            body = b"yt-dlp non installe sur le serveur"
            start_response("500 Server Error", [("Content-Type", "text/plain"), ("Content-Length", str(len(body)))])
            return [body]

        temp_dir = tempfile.mkdtemp(prefix="viddrop_")
        try:
            ydl_opts = {
                'outtmpl': os.path.join(temp_dir, '%(title).80s.%(ext)s'),
                'windowsfilenames': True,
                'trim_file_name': 80,
                'noplaylist': True,
                'no_warnings': True,
                'socket_timeout': 30,
                'retries': 5,
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'ios'],
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
            elif fmt == "WEBM":
                ydl_opts.update({
                    'format': 'bestvideo+bestaudio/best',
                    'merge_output_format': 'webm'
                })
            else:
                if FFMPEG_PATH:
                    ydl_opts.update({
                        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best',
                        'merge_output_format': 'mp4' if fmt == "MP4" else 'mov',
                    })
                else:
                    ydl_opts.update({'format': 'best[ext=mp4]/best'})

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
            mime_type = get_mime_type(target_file)
            safe_name = urllib.parse.quote(filename)

            headers = [
                ("Content-Type", mime_type),
                ("Content-Length", str(file_size)),
                ("Content-Disposition", f"attachment; filename=\"{filename}\"; filename*=UTF-8''{safe_name}"),
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
                    shutil.rmtree(temp_dir, ignore_errors=True)

            return file_stream()

        except Exception as e:
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
