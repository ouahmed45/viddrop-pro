#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
   VIDDROP — TÉLÉCHARGEUR VIDÉO & MUSIQUE UNIVERSEL (ÉDITION GRAND PUBLIC)
═══════════════════════════════════════════════════════════════════════════════
Design  : Glassmorphism Moderne (Verre Dépoli, Lueur Néon, Simple & Intuitif)
Moteur  : Téléchargement Ultra-Rapide, Qualité HD & 4K, Conversion MP4/MP3,
          Suppression des filigranes TikTok, Compatible Tous Écrans.
═══════════════════════════════════════════════════════════════════════════════
"""

import sys
import io
import multiprocessing
import os
import shutil
import threading
import subprocess
import platform
import re
import uuid
import time
from datetime import datetime

# ── Fix encodage console Windows (anti-crash cp1252) ─────────────────────────
if sys.stdout is not None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr is not None:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog

# ── Résolution des chemins PyInstaller / Standalone ──────────────────────────
if getattr(sys, 'frozen', False):
    CURRENT_DIR = sys._MEIPASS
    BASE_DIR = os.path.dirname(sys.executable)
else:
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = CURRENT_DIR

DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")

# ── Détection de FFmpeg ───────────────────────────────────────────────────────
def find_ffmpeg_path():
    exe = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    candidates = [
        os.path.join(CURRENT_DIR, exe),
        os.path.join(BASE_DIR, exe),
        os.path.join(CURRENT_DIR, "bin", exe),
        os.path.join(BASE_DIR, "bin", exe),
    ]
    if platform.system() == "Windows":
        candidates.extend([
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg\bin\ffmpeg.exe"),
        ])
    for path in candidates:
        if os.path.isfile(path):
            return path
    sys_path = shutil.which("ffmpeg")
    return sys_path if sys_path else None

FFMPEG_PATH = find_ffmpeg_path()


# ── Intégration Windows 11 DWM Acrylic / Mica ────────────────────────────────
def enable_windows_acrylic(window):
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            hwnd = window.winfo_id()
        dark_val = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark_val), ctypes.sizeof(dark_val))
        backdrop_val = ctypes.c_int(3)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(backdrop_val), ctypes.sizeof(backdrop_val))
    except Exception:
        pass


# ── Post-processeur FFmpeg Multi-Formats Grand Public ────────────────────────
try:
    import yt_dlp
    from yt_dlp.postprocessor.common import PostProcessor
except ImportError:
    yt_dlp = None
    PostProcessor = object


class UniversalRecodePP(PostProcessor):
    def __init__(self, downloader=None, ffmpeg_path=None, status_cb=None,
                 export_format="MP4", quality="ultrafast", resolution="source",
                 fps_target="Auto", ratio_target="Source", normalize_loudness=False,
                 delete_source=False, abort_event=None):
        super().__init__(downloader)
        self.ffmpeg_path = ffmpeg_path or "ffmpeg"
        self.status_cb = status_cb
        self.export_format = export_format
        self.quality = quality
        self.resolution = resolution
        self.fps_target = fps_target
        self.ratio_target = ratio_target
        self.normalize_loudness = normalize_loudness
        self.delete_source = delete_source
        self.abort_event = abort_event or threading.Event()
        self.active_proc = None

    def run(self, info):
        filepath = info.get('filepath') or info.get('_filename')
        if not filepath or not os.path.exists(filepath) or self.abort_event.is_set():
            return [], info

        source_fps = info.get('fps') or 30
        fps_map = {"24 fps (Cinéma)": 24, "30 fps (Standard)": 30, "60 fps (Ultra Fluide)": 60}
        target_fps = fps_map.get(self.fps_target, int(source_fps))

        if self.status_cb:
            self.status_cb(f"⚡ Préparation de votre vidéo ({self.export_format})...")

        base, _ = os.path.splitext(filepath)
        temp_id = str(uuid.uuid4())[:8]
        dir_path = os.path.dirname(filepath)

        ext_map = {"MP4": ".mp4", "MOV": ".mov", "MKV": ".mkv", "GIF": ".gif", "WEBM": ".webm"}
        out_ext = ext_map.get(self.export_format, ".mp4")
        final_path = f"{base}_viddrop{out_ext}"
        temp_output = os.path.join(dir_path, f"tmp_{temp_id}{out_ext}")

        try:
            ffmpeg_input = filepath
            if platform.system() == "Windows" and not filepath.startswith("\\\\?\\"):
                ffmpeg_input = "\\\\?\\" + os.path.abspath(filepath)

            vf_filters = []

            # Redimensionnement / Ratio
            if self.ratio_target == "16:9 (Écran Large)":
                vf_filters.append("scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1")
            elif self.ratio_target == "9:16 (Format Téléphone)":
                vf_filters.append("scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1")
            elif self.ratio_target == "1:1 (Format Carré)":
                vf_filters.append("scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1")
            else:
                res_dims = {"1080p": (1920, 1080), "720p": (1280, 720), "480p": (854, 480)}
                if self.resolution in res_dims:
                    tw, th = res_dims[self.resolution]
                    vf_filters.append(f"scale='min({tw},iw)':-2:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:black,setsar=1")
                else:
                    vf_filters.append("scale='trunc(iw/2)*2':'trunc(ih/2)*2'")

            af_filters = []
            if self.normalize_loudness:
                af_filters.append("loudnorm=I=-14:LRA=11:TP=-1.5")

            if self.export_format == "GIF":
                cmd = [
                    self.ffmpeg_path, "-y", "-i", ffmpeg_input,
                    "-vf", f"fps={min(target_fps, 20)},scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                    "-hide_banner", "-loglevel", "error", temp_output
                ]
            else:
                # MP4 universel par défaut (compatible PC, Mac, Téléviseurs, Smartphones)
                cmd = [
                    self.ffmpeg_path, "-y", "-rtbufsize", "512M", "-i", ffmpeg_input,
                    "-c:v", "libx264", "-preset", self.quality, "-pix_fmt", "yuv420p",
                    "-fps_mode", "cfr", "-r", str(target_fps),
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart",
                    "-hide_banner", "-loglevel", "error"
                ]
                if vf_filters: cmd.extend(["-vf", ",".join(vf_filters)])
                if af_filters: cmd.extend(["-af", ",".join(af_filters)])
                cmd.append(temp_output)

            self.active_proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )

            while self.active_proc.poll() is None:
                if self.abort_event.is_set():
                    self.active_proc.terminate()
                    try: self.active_proc.wait(timeout=2)
                    except subprocess.TimeoutExpired: self.active_proc.kill()
                    if os.path.exists(temp_output):
                        try: os.remove(temp_output)
                        except Exception: pass
                    raise Exception("Téléchargement annulé.")
                time.sleep(0.2)

            stderr = self.active_proc.stderr.read().decode('utf-8', errors='ignore')
            if self.active_proc.returncode != 0:
                raise Exception(f"Erreur d'enregistrement : {stderr}")

            target_dest = filepath if (self.delete_source and out_ext == os.path.splitext(filepath)[1]) else final_path

            if os.path.exists(temp_output):
                if self.delete_source and os.path.exists(filepath):
                    try: os.remove(filepath)
                    except Exception: pass
                if os.path.exists(target_dest):
                    try: os.remove(target_dest)
                    except Exception: pass
                os.rename(temp_output, target_dest)

            info['filepath'] = target_dest

        except Exception as e:
            if os.path.exists(temp_output):
                try: os.remove(temp_output)
                except Exception: pass
            if self.status_cb and not self.abort_event.is_set():
                err_clean = str(e)[:90] + "..." if len(str(e)) > 90 else str(e)
                self.status_cb(f"❌ {err_clean}")
            raise
        finally:
            self.active_proc = None

        return [], info


# ── Thème Graphique Glassmorphism Moderne ────────────────────────────────────
ctk.set_default_color_theme("blue")

GLASS_THEMES = {
    "dark": {
        "BG_BACKDROP": "#090A10",
        "GLASS_PANEL": "#11131F",
        "GLASS_CARD": "#16192A",
        "GLASS_CARD_HOVER": "#1E2238",
        "GLASS_INPUT": "#121424",
        "BORDER_SUBTLE": "#242940",
        "BORDER_GLOW": "#3B4368",
        "ACCENT": "#FF2D55",
        "ACCENT_HOVER": "#FF476E",
        "ACCENT_DARK": "#D6153B",
        "ACCENT_TRANSLUCENT": "#2C121E",
        "ACCENT_BORDER": "#FF3366",
        "CYAN": "#00F0FF",
        "CYAN_TRANSLUCENT": "#0C2332",
        "CYAN_BORDER": "#00C2D1",
        "SUCCESS": "#00E676",
        "SUCCESS_TRANSLUCENT": "#0E2A1F",
        "SUCCESS_BORDER": "#00B860",
        "WARNING": "#FFB300",
        "DANGER": "#FF334B",
        "TEXT_MAIN": "#FFFFFF",
        "TEXT_MUTED": "#929AB8",
        "TEXT_SUBTLE": "#575F7E",
        "SWITCH_LABEL": "☀ Mode Clair"
    },
    "light": {
        "BG_BACKDROP": "#F2F4FA",
        "GLASS_PANEL": "#FFFFFF",
        "GLASS_CARD": "#F8F9FE",
        "GLASS_CARD_HOVER": "#EFF2FB",
        "GLASS_INPUT": "#FFFFFF",
        "BORDER_SUBTLE": "#DCE1EF",
        "BORDER_GLOW": "#BAC3DE",
        "ACCENT": "#E60039",
        "ACCENT_HOVER": "#FF1A53",
        "ACCENT_DARK": "#BF002F",
        "ACCENT_TRANSLUCENT": "#FCE9EE",
        "ACCENT_BORDER": "#E60039",
        "CYAN": "#0284C7",
        "CYAN_TRANSLUCENT": "#E0F2FE",
        "CYAN_BORDER": "#38BDF8",
        "SUCCESS": "#059669",
        "SUCCESS_TRANSLUCENT": "#ECFDF5",
        "SUCCESS_BORDER": "#10B981",
        "WARNING": "#D97706",
        "DANGER": "#DC2626",
        "TEXT_MAIN": "#0F172A",
        "TEXT_MUTED": "#505A75",
        "TEXT_SUBTLE": "#8F9BB3",
        "SWITCH_LABEL": "🌙 Mode Sombre"
    }
}


# ── Application Principale ViddRop Grand Public ──────────────────────────────
class ViddRopApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ViddRop — Téléchargeur Vidéo & Musique Universel (HD & 4K)")
        self.root.geometry("1340x780")
        self.root.minsize(1080, 680)
        self.root.resizable(True, True)

        self.current_theme = "dark"
        self.t = GLASS_THEMES[self.current_theme]
        self.root.configure(fg_color=self.t["BG_BACKDROP"])

        enable_windows_acrylic(self.root)

        for ico_name in ("viddRop.ico", "vidddrop.ico", "viddrop.ico", "logo.ico"):
            icon_path = os.path.join(CURRENT_DIR, ico_name)
            if not os.path.exists(icon_path):
                icon_path = os.path.join(BASE_DIR, ico_name)
            if os.path.exists(icon_path):
                try: self.root.iconbitmap(icon_path)
                except Exception: pass
                break

        # Contrôles d'état
        self.abort_event = threading.Event()
        self.is_processing = False
        self.active_downloads = 0
        self.queue_running = False
        self.queue_lock = threading.Lock()
        self.last_clipboard_url = ""

        self.history = []
        self.queue = []
        self.current_postprocessor = None
        self.ytdlp_version_str = "Vérification..."

        # Variables de sélection
        self.format_category = tk.StringVar(value="VIDEO")
        self.format_var = tk.StringVar(value="MP4")

        # Options simples et intuitives
        self.parallel_var = tk.IntVar(value=2)
        self.quality_var = tk.StringVar(value="ultrafast")
        self.resolution_var = tk.StringVar(value="source")
        self.fps_var = tk.StringVar(value="Auto")
        self.ratio_var = tk.StringVar(value="Source")
        self.normalize_loudness_var = tk.BooleanVar(value=True) # Activé par défaut pour le grand public (son équilibré)
        self.save_thumbnail_var = tk.BooleanVar(value=False)
        self.clipboard_monitor_var = tk.BooleanVar(value=False)
        self.delete_source_var = tk.BooleanVar(value=False)
        self.auto_subtitles_var = tk.BooleanVar(value=False)

        # Construction de l'interface
        self.create_glass_widgets()

        # Threads d'arrière-plan
        threading.Thread(target=self.async_environment_check, daemon=True).start()
        threading.Thread(target=self.clipboard_monitor_loop, daemon=True).start()

    def create_glass_widgets(self):
        t = self.t

        # ── 1. EN-TÊTE ÉLÉGANT ──
        self.header = ctk.CTkFrame(
            self.root, fg_color=t["GLASS_PANEL"], height=70, corner_radius=0,
            border_width=1, border_color=t["BORDER_SUBTLE"]
        )
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)

        logo_zone = ctk.CTkFrame(self.header, fg_color="transparent")
        logo_zone.pack(side="left", padx=20, pady=12)

        # Logo officiel ViddRop
        logo_capsule = ctk.CTkFrame(
            logo_zone, width=46, height=46, fg_color=t["ACCENT_TRANSLUCENT"],
            corner_radius=12, border_width=1.5, border_color=t["ACCENT_BORDER"]
        )
        logo_capsule.pack(side="left", padx=(0, 12))
        logo_capsule.pack_propagate(False)

        logo_loaded = False
        for p in [os.path.join(CURRENT_DIR, "logo.png"), os.path.join(BASE_DIR, "logo.png"), os.path.join(CURRENT_DIR, "web", "static", "logo.png")]:
            if os.path.isfile(p):
                try:
                    self.logo_tk_img = tk.PhotoImage(file=p).subsample(6, 6)
                    img_label = tk.Label(logo_capsule, image=self.logo_tk_img, bg=t["BG_PANEL"], bd=0)
                    img_label.place(relx=0.5, rely=0.5, anchor="center")
                    logo_loaded = True
                    break
                except Exception:
                    pass

        if not logo_loaded:
            ctk.CTkLabel(logo_capsule, text="⚡", font=ctk.CTkFont(size=18, weight="bold"), text_color=t["ACCENT"]).place(relx=0.5, rely=0.5, anchor="center")

        brand_col = ctk.CTkFrame(logo_zone, fg_color="transparent")
        brand_col.pack(side="left")

        brand_row = ctk.CTkFrame(brand_col, fg_color="transparent")
        brand_row.pack(anchor="w")
        ctk.CTkLabel(brand_row, text="VIDD", font=ctk.CTkFont(size=22, weight="bold"), text_color=t["TEXT_MAIN"]).pack(side="left")
        ctk.CTkLabel(brand_row, text="ROP", font=ctk.CTkFont(size=22, weight="bold"), text_color=t["ACCENT"]).pack(side="left")

        ctk.CTkLabel(brand_col, text="✦ TÉLÉCHARGEUR VIDÉO & MUSIQUE UNIVERSEL", font=ctk.CTkFont(size=9, weight="bold"), text_color=t["CYAN"], anchor="w").pack(fill="x")

        # Badges Grand Public
        badges_container = ctk.CTkFrame(self.header, fg_color="transparent")
        badges_container.pack(side="left", padx=14)

        self._glass_pill_badge(badges_container, "⚡ Ultra Rapide", t["ACCENT"], t["ACCENT_TRANSLUCENT"], t["ACCENT_BORDER"])
        self._glass_pill_badge(badges_container, "💎 Qualité HD & 4K", t["SUCCESS"], t["SUCCESS_TRANSLUCENT"], t["SUCCESS_BORDER"])
        self._glass_pill_badge(badges_container, "🚫 Sans Filigrane TikTok / Insta", t["CYAN"], t["CYAN_TRANSLUCENT"], t["CYAN_BORDER"])

        top_right = ctk.CTkFrame(self.header, fg_color="transparent")
        top_right.pack(side="right", padx=20)

        self.engine_pill = ctk.CTkFrame(top_right, fg_color=t["GLASS_CARD"], corner_radius=16, border_width=1, border_color=t["BORDER_SUBTLE"])
        self.engine_pill.pack(side="left", padx=(0, 14), pady=18)

        self.status_engine_lbl = ctk.CTkLabel(
            self.engine_pill, text="● Prêt", font=ctk.CTkFont(size=10, weight="bold"),
            text_color=t["SUCCESS"], padx=12, pady=4
        )
        self.status_engine_lbl.pack()

        self.theme_switch = ctk.CTkSwitch(
            top_right, text=t["SWITCH_LABEL"], width=42, font=ctk.CTkFont(size=11),
            text_color=t["TEXT_MUTED"], progress_color=t["ACCENT"], button_color="#FFFFFF", command=self.toggle_theme
        )
        self.theme_switch.pack(side="right")
        if self.current_theme == "dark": self.theme_switch.select()

        # ── 2. LAYOUT PRINCIPAL ──
        self.main_container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=16)

        self.left_deck = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.left_deck.pack(side="left", fill="both", expand=True, padx=(0, 12))

        self.right_hub = ctk.CTkFrame(self.main_container, fg_color="transparent", width=490)
        self.right_hub.pack(side="right", fill="both", expand=False, padx=(12, 0))
        self.right_hub.pack_propagate(False)

        # ══════════════════════════════════════════════════════════════════════
        # COLONNE GAUCHE : SAISIE & TÉLÉCHARGEMENT FACILE
        # ══════════════════════════════════════════════════════════════════════
        self._section_header(self.left_deck, "LIEN DE VOTRE VIDÉO OU MUSIQUE", "TikTok, YouTube, Instagram, Facebook...")

        url_card = ctk.CTkFrame(self.left_deck, fg_color=t["GLASS_CARD"], corner_radius=14, border_width=1, border_color=t["BORDER_SUBTLE"])
        url_card.pack(fill="x", pady=(0, 14))

        url_inner = ctk.CTkFrame(url_card, fg_color="transparent")
        url_inner.pack(fill="x", padx=12, pady=12)

        self.url_input = ctk.CTkEntry(
            url_inner, placeholder_text="Collez le lien de votre vidéo ici...",
            font=ctk.CTkFont(size=12), height=46, fg_color=t["GLASS_INPUT"],
            border_color=t["BORDER_SUBTLE"], border_width=1, corner_radius=10, text_color=t["TEXT_MAIN"]
        )
        self.url_input.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            url_inner, text="📋 Coller", width=85, height=46, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=t["GLASS_PANEL"], hover_color=t["GLASS_CARD_HOVER"], border_color=t["BORDER_SUBTLE"], border_width=1,
            corner_radius=10, text_color=t["TEXT_MAIN"], command=self.paste_url
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            url_inner, text="＋ File", width=75, height=46, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=t["ACCENT_TRANSLUCENT"], hover_color=t["ACCENT_DARK"], border_width=1.5,
            border_color=t["ACCENT_BORDER"], corner_radius=10, text_color=t["ACCENT"], command=self.add_to_queue
        ).pack(side="left")

        # Dossier de sauvegarde
        self._section_header(self.left_deck, "DOSSIER D'ENREGISTREMENT", "Où enregistrer vos téléchargements")
        path_card = ctk.CTkFrame(self.left_deck, fg_color=t["GLASS_CARD"], corner_radius=14, border_width=1, border_color=t["BORDER_SUBTLE"])
        path_card.pack(fill="x", pady=(0, 14))

        path_inner = ctk.CTkFrame(path_card, fg_color="transparent")
        path_inner.pack(fill="x", padx=12, pady=10)

        self.path_input = ctk.CTkEntry(
            path_inner, font=ctk.CTkFont(size=12), height=40, fg_color=t["GLASS_INPUT"],
            border_color=t["BORDER_SUBTLE"], border_width=1, corner_radius=10, text_color=t["TEXT_MAIN"]
        )
        self.path_input.insert(0, DEFAULT_DOWNLOAD_DIR)
        self.path_input.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            path_inner, text="Changer...", width=100, height=40, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=t["GLASS_PANEL"], hover_color=t["GLASS_CARD_HOVER"], border_color=t["BORDER_SUBTLE"], border_width=1,
            corner_radius=10, text_color=t["TEXT_MAIN"], command=self.browse_path
        ).pack(side="left")

        # ── SÉLECTEUR DE FORMATS CLAIR & INTUITIF ──
        fmt_header = ctk.CTkFrame(self.left_deck, fg_color="transparent")
        fmt_header.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(fmt_header, text="CHOISIR LE FORMAT", font=ctk.CTkFont(size=10, weight="bold"), text_color=t["TEXT_MAIN"]).pack(side="left")

        cat_box = ctk.CTkFrame(fmt_header, fg_color="transparent")
        cat_box.pack(side="right")
        self.btn_cat_video = ctk.CTkButton(
            cat_box, text="🎬 Vidéo", width=90, height=22, font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=t["ACCENT"], text_color="#FFFFFF", corner_radius=6, command=lambda: self.switch_category("VIDEO")
        )
        self.btn_cat_video.pack(side="left", padx=2)

        self.btn_cat_audio = ctk.CTkButton(
            cat_box, text="🎵 Audio / Musique", width=120, height=22, font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=t["GLASS_CARD"], text_color=t["TEXT_MUTED"], corner_radius=6, command=lambda: self.switch_category("AUDIO")
        )
        self.btn_cat_audio.pack(side="left", padx=2)

        self.fmt_container = ctk.CTkFrame(self.left_deck, fg_color=t["GLASS_CARD"], corner_radius=14, border_width=1, border_color=t["BORDER_SUBTLE"])
        self.fmt_container.pack(fill="x", pady=(0, 14))

        self.fmt_inner = ctk.CTkFrame(self.fmt_container, fg_color="transparent")
        self.fmt_inner.pack(fill="x", padx=10, pady=10)

        self.fmt_buttons = {}
        self.build_format_tiles()

        # Suivi de Téléchargement
        self._section_header(self.left_deck, "PROGRESSION DU TÉLÉCHARGEMENT", "Vitesse et état en temps réel")
        prog_card = ctk.CTkFrame(self.left_deck, fg_color=t["GLASS_CARD"], corner_radius=14, border_width=1, border_color=t["BORDER_SUBTLE"])
        prog_card.pack(fill="x", pady=(0, 14))

        top_prog = ctk.CTkFrame(prog_card, fg_color="transparent")
        top_prog.pack(fill="x", padx=14, pady=(12, 6))

        self.status_label = ctk.CTkLabel(top_prog, text="● Prêt pour le téléchargement", font=ctk.CTkFont(size=12, weight="bold"), text_color=t["SUCCESS"], anchor="w")
        self.status_label.pack(side="left")

        self.pct_label = ctk.CTkLabel(top_prog, text="0.0%", font=ctk.CTkFont(size=14, weight="bold"), text_color=t["ACCENT"])
        self.pct_label.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(prog_card, height=10, corner_radius=5, fg_color=t["GLASS_INPUT"], progress_color=t["ACCENT"])
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=14, pady=(0, 14))

        # Grand Bouton d'Action
        action_row = ctk.CTkFrame(self.left_deck, fg_color="transparent")
        action_row.pack(fill="x", pady=(0, 10))

        self.btn_download = ctk.CTkButton(
            action_row, text="⚡ TÉLÉCHARGER MAINTENANT", font=ctk.CTkFont(size=13, weight="bold"), height=52,
            fg_color=t["ACCENT"], hover_color=t["ACCENT_HOVER"], corner_radius=12, border_width=1, border_color=t["ACCENT_BORDER"],
            text_color="#FFFFFF", command=self.start_download_wrapper
        )
        self.btn_download.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.btn_cancel = ctk.CTkButton(
            action_row, text="✕ Annuler", font=ctk.CTkFont(size=12, weight="bold"), height=52, width=85,
            fg_color=t["GLASS_PANEL"], hover_color=t["DANGER"], border_color=t["BORDER_SUBTLE"], border_width=1,
            corner_radius=12, text_color=t["TEXT_MAIN"], state="disabled", command=self.cancel_download
        )
        self.btn_cancel.pack(side="left", padx=(0, 8))

        self.btn_open_folder = ctk.CTkButton(
            action_row, text="📁 Ouvrir", font=ctk.CTkFont(size=12, weight="bold"), height=52, width=90,
            fg_color=t["GLASS_PANEL"], hover_color=t["GLASS_CARD_HOVER"], border_color=t["BORDER_SUBTLE"], border_width=1,
            corner_radius=12, text_color=t["TEXT_MAIN"], command=self.open_folder
        )
        self.btn_open_folder.pack(side="left")

        # ══════════════════════════════════════════════════════════════════════
        # COLONNE DROITE : RÉGLAGES FACILES & HISTORIQUE
        # ══════════════════════════════════════════════════════════════════════
        self._section_header(self.right_hub, "RÉGLAGES & PRÉFÉRENCES", "Personnalisez vos téléchargements")

        opts_card = ctk.CTkFrame(self.right_hub, fg_color=t["GLASS_CARD"], corner_radius=14, border_width=1, border_color=t["BORDER_SUBTLE"])
        opts_card.pack(fill="x", pady=(0, 12))

        # Ligne 1 : Qualité & Format d'écran
        r1 = ctk.CTkFrame(opts_card, fg_color="transparent")
        r1.pack(fill="x", padx=12, pady=(10, 6))

        ctk.CTkLabel(r1, text="Qualité :", font=ctk.CTkFont(size=10, weight="bold"), text_color=t["TEXT_MUTED"]).pack(side="left", padx=(0, 4))
        ctk.CTkComboBox(r1, values=["source", "1080p", "720p", "480p"], variable=self.resolution_var, width=80, height=26, font=ctk.CTkFont(size=10), fg_color=t["GLASS_INPUT"], border_color=t["BORDER_SUBTLE"], text_color=t["TEXT_MAIN"]).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(r1, text="Format d'écran :", font=ctk.CTkFont(size=10, weight="bold"), text_color=t["TEXT_MUTED"]).pack(side="left", padx=(0, 4))
        ctk.CTkComboBox(r1, values=["Source", "16:9 (Écran Large)", "9:16 (Format Téléphone)", "1:1 (Format Carré)"], variable=self.ratio_var, width=150, height=26, font=ctk.CTkFont(size=9), fg_color=t["GLASS_INPUT"], border_color=t["BORDER_SUBTLE"], text_color=t["TEXT_MAIN"]).pack(side="left")

        # Ligne 2 : Options pratiques
        r2 = ctk.CTkFrame(opts_card, fg_color="transparent")
        r2.pack(fill="x", padx=12, pady=(4, 10))

        ctk.CTkCheckBox(r2, text="Son Équilibré", variable=self.normalize_loudness_var, text_color=t["TEXT_MUTED"], checkmark_color=t["ACCENT"], fg_color=t["GLASS_INPUT"], border_color=t["BORDER_SUBTLE"], font=ctk.CTkFont(size=9)).pack(side="left", padx=(0, 8))
        ctk.CTkCheckBox(r2, text="Sauvegarder Image", variable=self.save_thumbnail_var, text_color=t["TEXT_MUTED"], checkmark_color=t["ACCENT"], fg_color=t["GLASS_INPUT"], border_color=t["BORDER_SUBTLE"], font=ctk.CTkFont(size=9)).pack(side="left", padx=(0, 8))
        ctk.CTkCheckBox(r2, text="Coller Automatique", variable=self.clipboard_monitor_var, text_color=t["TEXT_MUTED"], checkmark_color=t["ACCENT"], fg_color=t["GLASS_INPUT"], border_color=t["BORDER_SUBTLE"], font=ctk.CTkFont(size=9)).pack(side="left")

        # File d'attente
        queue_bar = ctk.CTkFrame(self.right_hub, fg_color="transparent")
        queue_bar.pack(fill="x", pady=(0, 4))

        self.queue_count_label = ctk.CTkLabel(queue_bar, text="TÉLÉCHARGEMENTS EN ATTENTE (0)", font=ctk.CTkFont(size=11, weight="bold"), text_color=t["TEXT_MUTED"], anchor="w")
        self.queue_count_label.pack(side="left")

        queue_actions = ctk.CTkFrame(queue_bar, fg_color="transparent")
        queue_actions.pack(side="right")

        ctk.CTkButton(queue_actions, text="Vider", width=55, height=24, font=ctk.CTkFont(size=10), fg_color="transparent", hover_color=t["GLASS_CARD"], text_color=t["TEXT_MUTED"], command=self.clear_queue).pack(side="left", padx=(0, 4))
        self.btn_start_queue = ctk.CTkButton(queue_actions, text="▶ Tout Télécharger", width=115, height=24, font=ctk.CTkFont(size=10, weight="bold"), fg_color=t["ACCENT"], hover_color=t["ACCENT_HOVER"], corner_radius=8, text_color="#FFFFFF", command=self.start_queue_wrapper)
        self.btn_start_queue.pack(side="left")

        self.queue_frame = ctk.CTkScrollableFrame(self.right_hub, fg_color=t["GLASS_CARD"], corner_radius=14, border_width=1, border_color=t["BORDER_SUBTLE"], height=160)
        self.queue_frame.pack(fill="both", expand=True, pady=(0, 10))
        self.refresh_queue_ui()

        # Historique
        hist_bar = ctk.CTkFrame(self.right_hub, fg_color="transparent")
        hist_bar.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(hist_bar, text="FICHIERS RÉCENTS", font=ctk.CTkFont(size=11, weight="bold"), text_color=t["TEXT_MUTED"], anchor="w").pack(side="left")
        ctk.CTkButton(hist_bar, text="Effacer", width=55, height=20, font=ctk.CTkFont(size=10), fg_color="transparent", hover_color=t["GLASS_CARD"], text_color=t["TEXT_MUTED"], command=self.clear_history).pack(side="right")

        self.history_frame = ctk.CTkScrollableFrame(self.right_hub, fg_color=t["GLASS_CARD"], corner_radius=14, border_width=1, border_color=t["BORDER_SUBTLE"], height=140)
        self.history_frame.pack(fill="both", expand=True)
        self.refresh_history_ui()

    def switch_category(self, cat):
        self.format_category.set(cat)
        t = self.t
        if cat == "VIDEO":
            self.btn_cat_video.configure(fg_color=t["ACCENT"], text_color="#FFFFFF")
            self.btn_cat_audio.configure(fg_color=t["GLASS_CARD"], text_color=t["TEXT_MUTED"])
            if self.format_var.get() not in ["MP4", "MOV", "WEBM", "GIF"]:
                self.format_var.set("MP4")
        else:
            self.btn_cat_audio.configure(fg_color=t["ACCENT"], text_color="#FFFFFF")
            self.btn_cat_video.configure(fg_color=t["GLASS_CARD"], text_color=t["TEXT_MUTED"])
            if self.format_var.get() not in ["MP3", "WAV"]:
                self.format_var.set("MP3")
        self.build_format_tiles()

    def build_format_tiles(self):
        t = self.t
        for w in self.fmt_inner.winfo_children(): w.destroy()
        self.fmt_buttons.clear()

        cat = self.format_category.get()
        if cat == "VIDEO":
            formats = [
                ("MP4", "Format Universel", "Compatible Tous Écrans"),
                ("MOV", "Format Vidéo Apple", "Haute Qualité"),
                ("WEBM", "Format Web Rapide", "Léger & Fluide"),
                ("GIF", "Animation GIF", "Mini Vidéo Animée")
            ]
        else:
            formats = [
                ("MP3", "Musique MP3", "Qualité Maximale 320k"),
                ("WAV", "Qualité Pure WAV", "Son Non Compressé")
            ]

        cur_fmt = self.format_var.get()
        for fmt, l1, l2 in formats:
            is_act = (fmt == cur_fmt)
            btn = ctk.CTkButton(
                self.fmt_inner,
                text=f"{fmt}\n{l1}\n{l2}",
                font=ctk.CTkFont(size=10, weight="bold"),
                height=56,
                fg_color=t["ACCENT_TRANSLUCENT"] if is_act else t["GLASS_INPUT"],
                hover_color=t["ACCENT_DARK"] if is_act else t["GLASS_CARD_HOVER"],
                border_width=1.5 if is_act else 1,
                border_color=t["ACCENT_BORDER"] if is_act else t["BORDER_SUBTLE"],
                corner_radius=10,
                text_color="#FFFFFF" if is_act else t["TEXT_MAIN"],
                command=lambda f=fmt: self.select_format(f)
            )
            btn.pack(side="left", expand=True, fill="x", padx=3)
            self.fmt_buttons[fmt] = btn

    def select_format(self, fmt):
        self.format_var.set(fmt)
        self.build_format_tiles()

    def _section_header(self, parent, title, subtitle):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(row, text=title, font=ctk.CTkFont(size=10, weight="bold"), text_color=self.t["TEXT_MAIN"], anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=f"— {subtitle}", font=ctk.CTkFont(size=10), text_color=self.t["TEXT_SUBTLE"], anchor="w").pack(side="left", padx=(6, 0))

    def _glass_pill_badge(self, parent, text, fg_color, bg_color, border_color):
        badge = ctk.CTkFrame(parent, fg_color=bg_color, corner_radius=14, border_width=1, border_color=border_color)
        badge.pack(side="left", padx=3)
        ctk.CTkLabel(badge, text=text, font=ctk.CTkFont(size=10, weight="bold"), text_color=fg_color, padx=9, pady=3).pack()

    def clipboard_monitor_loop(self):
        while True:
            try:
                if self.clipboard_monitor_var.get():
                    raw = self.root.clipboard_get().strip()
                    if raw and raw != self.last_clipboard_url:
                        if raw.startswith(("http://", "https://")) and any(p in raw.lower() for p in ["youtube", "youtu.be", "tiktok", "instagram", "facebook", "twitter", "x.com"]):
                            self.last_clipboard_url = raw
                            self.root.after(0, self._on_clipboard_detected, raw)
            except Exception:
                pass
            time.sleep(1.2)

    def _on_clipboard_detected(self, detected_url):
        cur_text = self.url_input.get().strip()
        if not cur_text:
            self.url_input.delete(0, "end")
            self.url_input.insert(0, detected_url)
            self.status_label.configure(text="📋 Lien inséré automatiquement !", text_color=self.t["CYAN"])

    def async_environment_check(self):
        ffmpeg_ok = bool(FFMPEG_PATH and os.path.isfile(FFMPEG_PATH))
        ytdlp_ver = "OK"
        try:
            res = subprocess.run([sys.executable, "-m", "yt_dlp", "--version"], capture_output=True, text=True, timeout=6)
            if res.returncode == 0 and res.stdout.strip():
                ytdlp_ver = res.stdout.strip()
            else:
                self.root.after(0, lambda: self.status_engine_lbl.configure(text="📦 Mise à jour...", text_color=self.t["WARNING"]))
                subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], capture_output=True, timeout=120)
                res = subprocess.run([sys.executable, "-m", "yt_dlp", "--version"], capture_output=True, text=True, timeout=6)
                if res.returncode == 0: ytdlp_ver = res.stdout.strip()
        except Exception:
            ytdlp_ver = "OK"

        self.ytdlp_version_str = ytdlp_ver

        def update_ui():
            self.status_engine_lbl.configure(text="● Prêt", text_color=self.t["SUCCESS"])
            self.engine_pill.configure(fg_color=self.t["SUCCESS_TRANSLUCENT"], border_color=self.t["SUCCESS_BORDER"])

        self.root.after(0, update_ui)

    def toggle_theme(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self.t = GLASS_THEMES[self.current_theme]
        ctk.set_appearance_mode(self.current_theme)

        self.root.configure(fg_color=self.t["BG_BACKDROP"])
        self.header.configure(fg_color=self.t["GLASS_PANEL"], border_color=self.t["BORDER_SUBTLE"])
        self.theme_switch.configure(text=self.t["SWITCH_LABEL"])

        self.build_format_tiles()
        self.refresh_queue_ui()
        self.refresh_history_ui()

    def paste_url(self):
        try:
            txt = self.root.clipboard_get().strip()
            if txt:
                self.url_input.delete(0, "end")
                self.url_input.insert(0, txt)
        except Exception:
            pass

    def browse_path(self):
        p = filedialog.askdirectory(initialdir=self.path_input.get().strip())
        if p:
            self.path_input.delete(0, "end")
            self.path_input.insert(0, p)

    def open_folder(self, target_filepath=None):
        p = target_filepath if target_filepath and os.path.exists(target_filepath) else self.path_input.get().strip()
        if not os.path.exists(p): return
        if platform.system() == "Windows":
            if os.path.isfile(p): subprocess.Popen(f'explorer /select,"{os.path.abspath(p)}"')
            else: os.startfile(p)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-R", p] if os.path.isfile(p) else ["open", p])
        else:
            folder = os.path.dirname(p) if os.path.isfile(p) else p
            subprocess.Popen(["xdg-open", folder])

    def play_media(self, filepath):
        if filepath and os.path.isfile(filepath):
            if platform.system() == "Windows": os.startfile(filepath)
            elif platform.system() == "Darwin": subprocess.Popen(["open", filepath])
            else: subprocess.Popen(["xdg-open", filepath])

    def add_to_queue(self):
        raw_text = self.url_input.get().strip()
        if not raw_text: return
        urls = [u.strip() for u in re.split(r'[\r\n\s]+', raw_text) if u.strip().startswith(("http://", "https://"))]
        if not urls: urls = [raw_text]

        with self.queue_lock:
            for u in urls:
                self.queue.append({
                    "id": str(uuid.uuid4())[:8],
                    "url": u,
                    "status": "attente",
                    "progress": 0.0,
                    "title": "",
                    "filepath": "",
                    "error": None,
                    "rating": None
                })

        self.url_input.delete(0, "end")
        self.refresh_queue_ui()

    def clear_queue(self):
        with self.queue_lock:
            if not self.queue_running: self.queue.clear()
            else: self.queue = [item for item in self.queue if item["status"] == "en cours"]
        self.refresh_queue_ui()

    def remove_queue_item(self, item_id):
        with self.queue_lock:
            self.queue = [item for item in self.queue if item["id"] != item_id]
        self.refresh_queue_ui()

    def move_queue_item(self, item_id, direction):
        with self.queue_lock:
            idx = next((i for i, item in enumerate(self.queue) if item["id"] == item_id), None)
            if idx is not None:
                new_idx = idx + direction
                if 0 <= new_idx < len(self.queue):
                    self.queue[idx], self.queue[new_idx] = self.queue[new_idx], self.queue[idx]
        self.refresh_queue_ui()

    def rate_queue_item(self, item_id, rating_type):
        with self.queue_lock:
            for item in self.queue:
                if item["id"] == item_id:
                    item["rating"] = None if item["rating"] == rating_type else rating_type
                    break
        self.refresh_queue_ui()

    def refresh_queue_ui(self):
        t = self.t
        for widget in self.queue_frame.winfo_children(): widget.destroy()

        with self.queue_lock:
            count = len(self.queue)
            queue_snapshot = list(self.queue)

        self.queue_count_label.configure(text=f"TÉLÉCHARGEMENTS EN ATTENTE ({count})")
        if not queue_snapshot:
            ctk.CTkLabel(self.queue_frame, text="Aucun élément dans la file d'attente", font=ctk.CTkFont(size=11), text_color=t["TEXT_SUBTLE"]).pack(pady=35)
            return

        for item in queue_snapshot:
            item_id = item["id"]
            card = ctk.CTkFrame(self.queue_frame, fg_color=t["GLASS_INPUT"], corner_radius=10, border_width=1, border_color=t["BORDER_SUBTLE"])
            card.pack(fill="x", pady=3, padx=2)

            info_col = ctk.CTkFrame(card, fg_color="transparent")
            info_col.pack(side="left", fill="both", expand=True, padx=10, pady=7)

            status_icon = {"attente": "⏳", "en cours": "⚡", "terminé": "✅", "erreur": "❌", "annulé": "⛔"}.get(item["status"], "⏳")
            display_title = item["title"] if item["title"] else item["url"]
            if len(display_title) > 36: display_title = display_title[:33] + "..."

            status_color = t["SUCCESS"] if item["status"] == "terminé" else (t["DANGER"] if item["status"] == "erreur" else t["TEXT_MAIN"])
            ctk.CTkLabel(info_col, text=f"{status_icon} {display_title}", font=ctk.CTkFont(size=10, weight="bold"), text_color=status_color, anchor="w").pack(fill="x")

            if item["status"] == "en cours":
                pbar = ctk.CTkProgressBar(info_col, height=4, corner_radius=2, fg_color=t["GLASS_CARD"], progress_color=t["ACCENT"])
                pbar.set(max(0.0, min(item["progress"] / 100.0, 1.0)))
                pbar.pack(fill="x", pady=(4, 0))

            if item.get("error"):
                ctk.CTkLabel(info_col, text=f"⚠️ {item['error']}", font=ctk.CTkFont(size=9), text_color=t["DANGER"], anchor="w").pack(fill="x", pady=(2, 0))

            btn_col = ctk.CTkFrame(card, fg_color="transparent")
            btn_col.pack(side="right", padx=6, pady=4)

            up_color = t["ACCENT"] if item.get("rating") == "up" else t["GLASS_PANEL"]
            down_color = t["DANGER"] if item.get("rating") == "down" else t["GLASS_PANEL"]

            ctk.CTkButton(btn_col, text="👍", width=26, height=22, font=ctk.CTkFont(size=10), fg_color=up_color, hover_color=t["ACCENT"], border_color=t["BORDER_SUBTLE"], border_width=1, corner_radius=4, command=lambda i=item_id: self.rate_queue_item(i, "up")).pack(side="left", padx=1)
            ctk.CTkButton(btn_col, text="👎", width=26, height=22, font=ctk.CTkFont(size=10), fg_color=down_color, hover_color=t["DANGER"], border_color=t["BORDER_SUBTLE"], border_width=1, corner_radius=4, command=lambda i=item_id: self.rate_queue_item(i, "down")).pack(side="left", padx=1)
            ctk.CTkButton(btn_col, text="▲", width=22, height=22, font=ctk.CTkFont(size=9), fg_color=t["GLASS_PANEL"], hover_color=t["GLASS_CARD_HOVER"], border_color=t["BORDER_SUBTLE"], border_width=1, corner_radius=4, command=lambda i=item_id: self.move_queue_item(i, -1)).pack(side="left", padx=1)
            ctk.CTkButton(btn_col, text="▼", width=22, height=22, font=ctk.CTkFont(size=9), fg_color=t["GLASS_PANEL"], hover_color=t["GLASS_CARD_HOVER"], border_color=t["BORDER_SUBTLE"], border_width=1, corner_radius=4, command=lambda i=item_id: self.move_queue_item(i, 1)).pack(side="left", padx=1)
            ctk.CTkButton(btn_col, text="✕", width=22, height=22, font=ctk.CTkFont(size=10, weight="bold"), fg_color=t["GLASS_PANEL"], hover_color=t["DANGER"], text_color=t["DANGER"], border_color=t["BORDER_SUBTLE"], border_width=1, corner_radius=4, command=lambda i=item_id: self.remove_queue_item(i)).pack(side="left", padx=1)

    def add_history_entry(self, title, filepath):
        self.history.insert(0, {"title": title, "path": filepath, "time": datetime.now().strftime("%H:%M")})
        self.refresh_history_ui()

    def clear_history(self):
        self.history.clear()
        self.refresh_history_ui()

    def refresh_history_ui(self):
        t = self.t
        for widget in self.history_frame.winfo_children(): widget.destroy()
        if not self.history:
            ctk.CTkLabel(self.history_frame, text="Aucun téléchargement récent", font=ctk.CTkFont(size=11), text_color=t["TEXT_SUBTLE"]).pack(pady=35)
            return

        for entry in self.history:
            card = ctk.CTkFrame(self.history_frame, fg_color=t["GLASS_INPUT"], corner_radius=10, border_width=1, border_color=t["BORDER_SUBTLE"])
            card.pack(fill="x", pady=3, padx=2)

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=10, pady=7)

            title_display = entry["title"] if len(entry["title"]) <= 40 else entry["title"][:37] + "..."
            ctk.CTkLabel(info, text=title_display, font=ctk.CTkFont(size=10, weight="bold"), text_color=t["TEXT_MAIN"], anchor="w").pack(fill="x")
            ctk.CTkLabel(info, text=f"✅ {entry['time']} • {os.path.basename(entry['path'])}", font=ctk.CTkFont(size=9), text_color=t["SUCCESS"], anchor="w").pack(fill="x")

            btn_box = ctk.CTkFrame(card, fg_color="transparent")
            btn_box.pack(side="right", padx=6, pady=4)

            ctk.CTkButton(btn_box, text="▶", width=28, height=24, font=ctk.CTkFont(size=10), fg_color=t["GLASS_PANEL"], hover_color=t["GLASS_CARD_HOVER"], border_color=t["BORDER_SUBTLE"], border_width=1, corner_radius=6, text_color=t["TEXT_MAIN"], command=lambda p=entry["path"]: self.play_media(p)).pack(side="left", padx=2)
            ctk.CTkButton(btn_box, text="📁", width=28, height=24, font=ctk.CTkFont(size=10), fg_color=t["GLASS_PANEL"], hover_color=t["GLASS_CARD_HOVER"], border_color=t["BORDER_SUBTLE"], border_width=1, corner_radius=6, text_color=t["TEXT_MAIN"], command=lambda p=entry["path"]: self.open_folder(p)).pack(side="left", padx=2)

    def start_queue_wrapper(self):
        if not self.queue_running:
            self.queue_running = True
            self.btn_start_queue.configure(text="⏸ Pause", fg_color=self.t["WARNING"])
            threading.Thread(target=self.process_queue_loop, daemon=True).start()
        else:
            self.queue_running = False
            self.btn_start_queue.configure(text="▶ Tout Télécharger", fg_color=self.t["ACCENT"])

    def process_queue_loop(self):
        max_workers = int(self.parallel_var.get())
        threads = []

        while self.queue_running:
            with self.queue_lock:
                pending_items = [item for item in self.queue if item["status"] == "attente"]

            if not pending_items and self.active_downloads == 0: break

            with self.queue_lock:
                for item in pending_items:
                    if self.active_downloads < max_workers and self.queue_running:
                        item["status"] = "en cours"
                        self.active_downloads += 1
                        t = threading.Thread(target=self._run_queue_download, args=(item,), daemon=True)
                        t.start()
                        threads.append(t)

            time.sleep(0.5)

        for t in threads: t.join(timeout=1.0)
        self.queue_running = False
        self.root.after(0, lambda: self.btn_start_queue.configure(text="▶ Tout Télécharger", fg_color=self.t["ACCENT"]))
        self.root.after(0, self.refresh_queue_ui)

    def _run_queue_download(self, item):
        try:
            def q_hook(d):
                if d.get('status') == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    downloaded = d.get('downloaded_bytes', 0)
                    if total > 0: item["progress"] = (downloaded / total) * 100.0
                    self.root.after(0, self.refresh_queue_ui)
                elif d.get('status') == 'finished':
                    item["progress"] = 99.0
                    self.root.after(0, self.refresh_queue_ui)

            title, filepath = self._execute_ytdlp_download(item["url"], custom_hook=q_hook)
            item["status"] = "terminé"
            item["title"] = title
            item["filepath"] = filepath
            item["progress"] = 100.0
            item["error"] = None
            self.root.after(0, lambda: self.add_history_entry(title, filepath))

        except Exception as e:
            item["status"] = "erreur"
            err_msg = str(e)
            item["error"] = err_msg[:60] + "..." if len(err_msg) > 60 else err_msg
        finally:
            with self.queue_lock: self.active_downloads = max(0, self.active_downloads - 1)
            self.root.after(0, self.refresh_queue_ui)

    def start_download_wrapper(self):
        url = self.url_input.get().strip()
        if not url or self.is_processing: return

        self.abort_event.clear()
        self.is_processing = True
        self.btn_download.configure(state="disabled")
        self.btn_cancel.configure(state="normal", fg_color=self.t["DANGER"])
        self.status_label.configure(text="⚡ Préparation du téléchargement...", text_color=self.t["ACCENT"])
        self.progress_bar.set(0)
        self.pct_label.configure(text="0.0%")

        threading.Thread(target=self._direct_download_thread, args=(url,), daemon=True).start()

    def cancel_download(self):
        self.abort_event.set()
        if self.current_postprocessor and self.current_postprocessor.active_proc:
            try: self.current_postprocessor.active_proc.kill()
            except Exception: pass
        self.status_label.configure(text="⛔ Annulation...", text_color=self.t["DANGER"])

    def _direct_download_thread(self, url):
        try:
            title, filepath = self._execute_ytdlp_download(url, custom_hook=self.direct_progress_hook)
            self.root.after(0, self._on_download_complete, title, filepath)
        except Exception as e:
            if not self.abort_event.is_set():
                err_msg = str(e)
                self.root.after(0, lambda m=err_msg: messagebox.showerror("Information", m))
                self.root.after(0, lambda: self.status_label.configure(text="❌ Erreur", text_color=self.t["DANGER"]))
            else:
                self.root.after(0, lambda: self.status_label.configure(text="⛔ Annulé", text_color=self.t["DANGER"]))
        finally:
            self.is_processing = False
            self.root.after(0, self._reset_direct_buttons)

    def _on_download_complete(self, title, filepath):
        self.progress_bar.set(1.0)
        self.pct_label.configure(text="100%")
        self.status_label.configure(text="✅ Téléchargement terminé avec succès !", text_color=self.t["SUCCESS"])
        self.add_history_entry(title, filepath)

    def _reset_direct_buttons(self):
        self.btn_download.configure(state="normal")
        self.btn_cancel.configure(state="disabled", fg_color=self.t["GLASS_PANEL"])

    def direct_progress_hook(self, d):
        if self.abort_event.is_set(): raise Exception("Téléchargement interrompu.")
        if d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0: p = (downloaded / total) * 100.0
            else:
                raw_pct = d.get('_percent_str', '0%')
                clean_pct = re.sub(r'\x1b\[[0-9;]*m', '', raw_pct).replace('%', '').strip()
                p = float(clean_pct) if clean_pct else 0.0
            speed = d.get('_speed_str', 'N/A')
            self.root.after(0, lambda: self._update_direct_ui(p, speed))
        elif d.get('status') == 'finished':
            self.root.after(0, lambda: self.status_label.configure(text="⚙ Finalisation du fichier...", text_color=self.t["WARNING"]))

    def _update_direct_ui(self, p, speed):
        clamped = max(0.0, min(p / 100.0, 1.0))
        self.progress_bar.set(clamped)
        self.pct_label.configure(text=f"{p:.1f}%")
        self.status_label.configure(text=f"⚡ {p:.1f}% — {speed}", text_color=self.t["ACCENT"])

    def _execute_ytdlp_download(self, url, custom_hook=None):
        if yt_dlp is None: raise Exception("yt-dlp n'est pas encore installé.")

        dest_dir = self.path_input.get().strip()
        fmt = self.format_var.get()
        quality = self.quality_var.get()
        resolution = self.resolution_var.get()
        fps_target = self.fps_var.get()
        ratio_target = self.ratio_var.get()
        normalize_loudness = self.normalize_loudness_var.get()
        save_thumbnail = self.save_thumbnail_var.get()
        delete_source = self.delete_source_var.get()

        os.makedirs(dest_dir, exist_ok=True)
        hooks = [custom_hook] if custom_hook else []

        ydl_opts = {
            'outtmpl': os.path.join(dest_dir, '%(title).100s.%(ext)s'),
            'windowsfilenames': True,
            'trim_file_name': 100,
            'progress_hooks': hooks,
            'concurrent_fragment_downloads': 8,
            'fragment_retries': 10,
            'retries': 10,
            'socket_timeout': 25,
            'noplaylist': True,
            'no_warnings': True,
            'add_metadata': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            }
        }

        if FFMPEG_PATH: ydl_opts['ffmpeg_location'] = FFMPEG_PATH
        if save_thumbnail: ydl_opts['writethumbnail'] = True

        if fmt == "MP3":
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            })
        elif fmt == "WAV":
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                }],
            })
        elif fmt == "WEBM":
            ydl_opts.update({
                'format': 'bestvideo+bestaudio/best',
                'merge_output_format': 'webm'
            })
        else:
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if FFMPEG_PATH and fmt in ["MP4", "MOV", "WEBM", "GIF"]:
                status_cb = lambda msg: self.root.after(
                    0, lambda: self.status_label.configure(text=msg, text_color=self.t["WARNING"])
                )
                self.current_postprocessor = UniversalRecodePP(
                    downloader=ydl,
                    ffmpeg_path=FFMPEG_PATH,
                    status_cb=status_cb,
                    export_format=fmt,
                    quality=quality,
                    resolution=resolution,
                    fps_target=fps_target,
                    ratio_target=ratio_target,
                    normalize_loudness=normalize_loudness,
                    delete_source=delete_source,
                    abort_event=self.abort_event
                )
                ydl.add_post_processor(self.current_postprocessor)

            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Vidéo') if info else 'Vidéo'
            filepath = info.get('filepath') if info and info.get('filepath') else (ydl.prepare_filename(info) if info else '')

        return title, filepath


# ── Point d'Entrée Exécutable ────────────────────────────────────────────────
if __name__ == "__main__":
    multiprocessing.freeze_support()

    print("=" * 68)
    print("💎 VIDDROP — TÉLÉCHARGEUR VIDÉO & MUSIQUE UNIVERSEL (HD & 4K)")
    print("⚡ Simple • Rapide • Sans Filigrane • MP4 / MP3")
    print("=" * 68)

    root = ctk.CTk()
    app = ViddRopApp(root)
    root.mainloop()
