#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
   VIDDROP — SCRIPT DE COMPILATION PYINSTALLER (WINDOWS .EXE GRAND PUBLIC)
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import subprocess
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_PATH = os.path.join(BASE_DIR, "viddrop_pro.py")
APP_NAME = "ViddRop"
DIST_DIR = os.path.join(BASE_DIR, "dist")
BUILD_DIR = os.path.join(BASE_DIR, "build")

def check_and_install_requirements():
    print("📦 Vérification des outils de compilation...")
    packages = ["pyinstaller", "customtkinter", "yt-dlp"]
    for pkg in packages:
        try:
            __import__(pkg.replace("-", "_"))
            print(f"  ✅ {pkg} est installé.")
        except ImportError:
            print(f"  ⚠️ {pkg} manquant, installation...")
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", pkg], check=True)

def find_app_icon():
    for name in ["viddRop.ico", "vidddrop.ico", "viddrop.ico", "logo.ico", "icon.ico"]:
        p = os.path.join(BASE_DIR, name)
        if os.path.exists(p):
            return p
    return None

def build():
    check_and_install_requirements()

    icon_path = find_app_icon()
    print(f"\n🚀 Démarrage de la compilation pour {APP_NAME}...")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",
        "--noconsole",
        "--clean",
        "--collect-all", "customtkinter",
        "--collect-all", "yt_dlp",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "ctypes",
        "--hidden-import", "ctypes.wintypes",
    ]

    if icon_path:
        print(f"  🎨 Icône détectée : {icon_path}")
        cmd.extend(["--icon", icon_path])
        cmd.extend(["--add-data", f"{icon_path};."])

    ffmpeg_local = os.path.join(BASE_DIR, "ffmpeg.exe")
    if os.path.exists(ffmpeg_local):
        print(f"  🎬 FFmpeg portable détecté, inclusion dans l'exécutable...")
        cmd.extend(["--add-data", f"{ffmpeg_local};."])

    cmd.append(SCRIPT_PATH)

    print("\n⚡ Exécution de la commande PyInstaller :")
    print(" ".join(cmd))
    print("-" * 65)

    res = subprocess.run(cmd)
    if res.returncode == 0:
        exe_file = os.path.join(DIST_DIR, f"{APP_NAME}.exe")
        print("\n" + "=" * 65)
        print("🎉 COMPILATION RÉUSSIE AVEC SUCCÈS !")
        print(f"📁 Exécutable généré : {exe_file}")
        if os.path.exists(exe_file):
            size_mb = os.path.getsize(exe_file) / (1024 * 1024)
            print(f"📊 Taille de l'exécutable : {size_mb:.2f} Mo")
        print("=" * 65)
    else:
        print(f"\n❌ Erreur lors de la compilation (code {res.returncode})")

if __name__ == "__main__":
    build()
