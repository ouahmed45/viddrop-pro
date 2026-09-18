#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
   VIDDROP WEB — SERVEUR API ET APPLICATION WEB (ÉDITION GRAND PUBLIC)
═══════════════════════════════════════════════════════════════════════════════
Fonctionnalités :
- Distribution de l'interface Glassmorphism (HTML5, CSS3, JS)
- Endpoints API :
  * /api/info?url=...     -> Analyse de la vidéo et métadonnées (titre, miniature, durée)
  * /api/download?url=... -> Téléchargement et conversion directe
- Support natif PWA et Share Target pour Android
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys

# Support universel UTF-8 sur terminal Windows pour éviter UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import re
import json
import time
import threading
import shutil
import tempfile
import urllib.parse
import urllib.request
import mimetypes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Mémoire partagée de progression des tâches en temps réel
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

# Port dynamique pour hébergement Cloud (Render, Railway, Heroku, etc.)
PORT = int(os.environ.get("PORT", 8080))

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# Détection automatique de FFmpeg
FFMPEG_PATH = None
candidates = [
    shutil.which("ffmpeg"),
    os.path.join(ROOT_DIR, "ffmpeg.exe"),
    r"C:\Program Files\FFmpeg\bin\ffmpeg.exe",
    r"C:\ffmpeg\bin\ffmpeg.exe"
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


def setup_oauth2_cache():
    """
    Restaure le cache OAuth2 yt-dlp depuis la variable YOUTUBE_OAUTH_TOKEN.
    Retourne le chemin du cache si succès, None sinon.
    """
    import base64
    token_b64 = os.environ.get("YOUTUBE_OAUTH_TOKEN", "").strip()
    if not token_b64:
        return None
    try:
        cache_data = json.loads(base64.b64decode(token_b64).decode("utf-8"))
        cache_dir = os.path.join(tempfile.gettempdir(), "viddrop_yt_cache")
        os.makedirs(cache_dir, exist_ok=True)
        for rel_path, file_b64 in cache_data.items():
            full_path = os.path.join(cache_dir, rel_path.replace("\\", os.sep).replace("/", os.sep))
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "wb") as fh:
                fh.write(base64.b64decode(file_b64))
        print(f"[OAuth2] Token restaure dans : {cache_dir}")
        return cache_dir
    except Exception as e:
        print(f"[OAuth2] Erreur token : {e}")
        return None

# Restaure le cache OAuth2 au démarrage du serveur (une seule fois)
OAUTH2_CACHE_DIR = setup_oauth2_cache()

def get_cookie_file():
    """Détecte ou extrait le fichier cookies.txt pour contourner le bot-check YouTube."""
    env_cookies = os.environ.get("YOUTUBE_COOKIES")
    if env_cookies and len(env_cookies.strip()) > 20:
        target = os.path.join(tempfile.gettempdir(), "render_yt_cookies.txt")
        try:
            with open(target, "w", encoding="utf-8") as f:
                f.write(env_cookies.strip())
            return target
        except Exception:
            pass

    candidates = [
        "/etc/secrets/cookies.txt",
        os.path.join(ROOT_DIR, "cookies.txt"),
        os.path.join(BASE_DIR, "cookies.txt"),
        os.path.join(os.getcwd(), "cookies.txt"),
    ]
    for c in candidates:
        if os.path.isfile(c) and os.path.getsize(c) > 10:
            return c
    return None


class ViddRopWebHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        sys.stdout.write(f"[{self.log_date_time_string()}] {format % args}\n")
        sys.stdout.flush()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/info":
            self.handle_api_info(query)
            return

        if path == "/api/progress":
            self.handle_api_progress(query)
            return

        if path == "/api/download":
            self.handle_api_download(query)
            return

        if path == "/api/debug":
            self.handle_api_debug(query)
            return

        if path == "/" or path == "/index.html":
            file_path = os.path.join(BASE_DIR, "index.html")
        elif path.startswith("/static/"):
            file_path = os.path.join(BASE_DIR, path.lstrip("/"))
        elif path.startswith("/android/"):
            file_path = os.path.join(ROOT_DIR, path.lstrip("/"))
        else:
            file_path = os.path.join(BASE_DIR, path.lstrip("/"))

        if os.path.isfile(file_path):
            self.serve_file(file_path)
        else:
            self.send_error(404, "Fichier non trouvé")

    def serve_file(self, file_path):
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            if file_path.endswith(".json"): mime_type = "application/json"
            elif file_path.endswith(".js"): mime_type = "application/javascript"
            elif file_path.endswith(".css"): mime_type = "text/css"
            elif file_path.endswith(".png"): mime_type = "image/png"
            elif file_path.endswith(".ico"): mime_type = "image/x-icon"
            else: mime_type = "text/html"

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Erreur lecture fichier : {e}")

    def handle_api_debug(self, query):
        """Route de diagnostic en direct pour inspecter YouTube, yt-dlp et FFmpeg sur Render."""
        test_url = query.get("url", ["https://www.youtube.com/watch?v=5E2DiKzX21w"])[0].strip()
        cfile = get_cookie_file()
        diag = {
            "ytdlp_version": getattr(yt_dlp, "__version__", "Non installé") if yt_dlp else "Non installé",
            "ffmpeg_path": FFMPEG_PATH,
            "ffmpeg_exists": bool(FFMPEG_PATH and os.path.exists(FFMPEG_PATH)),
            "cookie_detected": bool(cfile),
            "cookie_path": cfile if cfile else None,
            "cookie_env_len": len(os.environ.get("YOUTUBE_COOKIES", "")),
            "test_url": test_url,
            "formats": [],
            "error": None
        }

        if not yt_dlp:
            diag["error"] = "yt-dlp non installé sur le serveur"
            self.send_json(diag)
            return

        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 15,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'default'],
                }
            }
        }
        if cfile:
            ydl_opts['cookiefile'] = cfile
        if FFMPEG_PATH:
            ydl_opts['ffmpeg_location'] = FFMPEG_PATH

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(test_url, download=False)
                for f in info.get("formats", []):
                    diag["formats"].append({
                        "id": f.get("format_id"),
                        "ext": f.get("ext"),
                        "height": f.get("height"),
                        "vcodec": f.get("vcodec"),
                        "acodec": f.get("acodec"),
                        "tbr": f.get("tbr"),
                        "has_url": bool(f.get("url"))
                    })
                diag["video_title"] = info.get("title")
        except Exception as e:
            diag["error"] = str(e)

        self.send_json(diag)

    def handle_api_info(self, query):
        url = query.get("url", [""])[0].strip()
        if not url:
            self.send_json({"error": "Lien manquant"}, status=400)
            return

        if not yt_dlp:
            self.send_json({
                "title": "Vidéo prête à télécharger",
                "uploader": "Réseau Social",
                "duration_string": "HD",
                "thumbnail": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500",
                "quality": "Haute Qualité"
            })
            return

        try:
            ydl_opts = {
                'skip_download': True,
                'no_warnings': True,
                'noplaylist': True,
                'socket_timeout': 15,
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'default'],
                    }
                },
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                }
            }
            if FFMPEG_PATH:
                ydl_opts['ffmpeg_location'] = FFMPEG_PATH

            cfile = get_cookie_file()
            if cfile:
                ydl_opts['cookiefile'] = cfile

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
            self.send_json(data)
        except Exception as e:
            fallback = fetch_oembed_info(url)
            if fallback:
                self.send_json(fallback)
            else:
                self.send_json({
                    "title": "Vidéo trouvée",
                    "uploader": "Réseau Social",
                    "duration_string": "HD",
                    "thumbnail": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500",
                    "quality": "Haute Définition",
                    "warning": str(e)
                })

    def handle_api_progress(self, query):
        task_id = query.get("id", [""])[0]
        data = PROGRESS_TASKS.get(task_id, {
            "status": "waiting",
            "percent": 5.0,
            "msg": "Connexion au flux en cours..."
        })
        self.send_json(data)

    def handle_api_download(self, query):
        url = query.get("url", [""])[0].strip()
        fmt = query.get("format", ["MP4"])[0].upper()
        task_id = query.get("task_id", [""])[0]

        if not url:
            self.send_error(400, "Lien requis")
            return

        if not yt_dlp:
            self.send_error(500, "yt-dlp n'est pas installé sur le serveur.")
            return

        if task_id:
            PROGRESS_TASKS[task_id] = {
                "status": "downloading",
                "percent": 8.0,
                "msg": "⚡ Préparation du flux..."
            }

        # Dossier temporaire isolé pour ce téléchargement
        temp_dir = tempfile.mkdtemp(prefix="viddrop_")
        try:
            def progress_hook(d):
                if not task_id: return
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
                        'player_client': ['android', 'default'],
                    }
                },
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                }
            }

            if FFMPEG_PATH:
                ydl_opts['ffmpeg_location'] = FFMPEG_PATH

            cfile = get_cookie_file()
            if cfile:
                ydl_opts['cookiefile'] = cfile

            if fmt == "MP3":
                if FFMPEG_PATH:
                    ydl_opts.update({
                        'format': 'ba/b',
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '320',
                        }],
                    })
                else:
                    ydl_opts.update({'format': 'ba/b'})
            elif fmt == "WAV":
                if FFMPEG_PATH:
                    ydl_opts.update({
                        'format': 'ba/b',
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'wav',
                        }],
                    })
                else:
                    ydl_opts.update({'format': 'ba/b'})
            elif fmt == "MP4_1080":
                ydl_opts.update({
                    'format': 'bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b',
                    'merge_output_format': 'mp4',
                })
            elif fmt == "MP4_720":
                ydl_opts.update({
                    'format': 'bv*[height<=720]+ba/b[height<=720]/bv*+ba/b',
                    'merge_output_format': 'mp4',
                })
            elif fmt == "WEBM":
                ydl_opts.update({
                    'format': 'bv*+ba/b',
                    'merge_output_format': 'webm'
                })
            else:  # MP4 (Qualite Maximale 4K / 2K / 1080p) ou MOV
                ydl_opts.update({
                    'format': 'bv*+ba/b',
                    'merge_output_format': 'mp4' if fmt == "MP4" else 'mov',
                })

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as dl_primary_err:
                print(f"[ViddRop] Echec format primaire ({dl_primary_err}), repli 1 sur bv*+ba/b...")
                try:
                    ydl_opts['format'] = 'bv*+ba/b'
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl_fallback:
                        ydl_fallback.download([url])
                except Exception as dl_sec_err:
                    print(f"[ViddRop] Echec repli 1 ({dl_sec_err}), repli ultime sur b/best...")
                    ydl_opts['format'] = 'b/best'
                    ydl_opts.pop('postprocessors', None)
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl_ultimate:
                        ydl_ultimate.download([url])

            # Recherche du fichier généré
            downloaded_files = [
                os.path.join(temp_dir, f) for f in os.listdir(temp_dir)
                if os.path.isfile(os.path.join(temp_dir, f)) and not f.endswith('.part') and not f.endswith('.ytdl')
            ]

            if not downloaded_files:
                self.send_error(500, "Le fichier n'a pas pu être extrait.")
                return

            target_file = downloaded_files[0]
            filename = os.path.basename(target_file)
            file_size = os.path.getsize(target_file)

            mime_type, _ = mimetypes.guess_type(target_file)
            if not mime_type:
                mime_type = "application/octet-stream"

            # Envoi du fichier en streaming direct vers le navigateur
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(file_size))
            clean_ascii = re.sub(r'[^\x20-\x7E]', '_', filename).replace('"', '')
            safe_name = urllib.parse.quote(filename, encoding='utf-8')
            self.send_header("Content-Disposition", f'attachment; filename="{clean_ascii}"; filename*=UTF-8\'\'{safe_name}')
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            if task_id:
                PROGRESS_TASKS[task_id] = {
                    'status': 'done',
                    'percent': 100.0,
                    'msg': "✅ Fichier prêt ! Téléchargement en cours..."
                }

            with open(target_file, "rb") as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

        except Exception as e:
            if task_id:
                PROGRESS_TASKS[task_id] = {
                    'status': 'error',
                    'percent': 0.0,
                    'msg': f"❌ Erreur : {str(e)[:50]}"
                }
            err_html = f"""
            <!DOCTYPE html>
            <html lang="fr">
            <head><meta charset="utf-8"><title>Erreur de Téléchargement</title><link rel="stylesheet" href="/static/style.css"></head>
            <body style="display:flex;align-items:center;justify-content:center;height:100vh;text-align:center;">
                <div class="glass-card" style="padding:2.5rem;border-radius:18px;max-width:550px;">
                    <h2 style="color:#FF2D55;margin-bottom:1rem;">⚠️ Erreur de Téléchargement</h2>
                    <p style="color:#949CB5;margin-bottom:1.5rem;font-size:0.95rem;">{str(e)}</p>
                    <a href="/" class="btn-action-glow" style="display:inline-block;text-decoration:none;padding:12px 24px;">⬅ Réessayer avec un autre lien</a>
                </div>
            </body>
            </html>
            """
            self.send_response(500)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(err_html.encode("utf-8"))
        finally:
            if task_id:
                def _cleanup():
                    time.sleep(120)
                    PROGRESS_TASKS.pop(task_id, None)
                threading.Thread(target=_cleanup, daemon=True).start()
            shutil.rmtree(temp_dir, ignore_errors=True)

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def run():
    server_address = ("", PORT)
    httpd = ThreadingHTTPServer(server_address, ViddRopWebHandler)
    print("=" * 68)
    print("🌐 VIDDROP — SITE WEB & TÉLÉCHARGEUR EN LIGNE (GRAND PUBLIC)")
    print(f"🚀 Serveur actif sur : http://localhost:{PORT}")
    print(f"⚡ Moteur FFmpeg : {'Détecté (' + FFMPEG_PATH + ')' if FFMPEG_PATH else 'Mode Fallback sans FFmpeg'}")
    print("=" * 68)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur.")
        httpd.server_close()


if __name__ == "__main__":
    run()
