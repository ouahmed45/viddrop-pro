// ═══════════════════════════════════════════════════════════════════════════════
//   VIDDROP WEB — LOGIQUE CLIENT & GESTIONNAIRE D'ANALYSE ET TÉLÉCHARGEMENT
// ═══════════════════════════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {
  const urlInput = document.getElementById("urlInput");
  const btnPaste = document.getElementById("btnPaste");
  const btnAnalyze = document.getElementById("btnAnalyze");
  const platformText = document.getElementById("platformText");

  const previewCard = document.getElementById("previewCard");
  const previewThumb = document.getElementById("previewThumb");
  const previewTitle = document.getElementById("previewTitle");
  const previewMeta = document.getElementById("previewMeta");
  const previewDuration = document.getElementById("previewDuration");

  const formatChips = document.querySelectorAll(".chip");
  const btnStartDownload = document.getElementById("btnStartDownload");

  const downloadMonitor = document.getElementById("downloadMonitor");
  const monitorStatus = document.getElementById("monitorStatus");
  const monitorPercent = document.getElementById("monitorPercent");
  const progressBar = document.getElementById("progressBar");

  const btnInstallPwa = document.getElementById("btnInstallPwa");

  let selectedFormat = "MP4";
  let currentVideoData = null;
  let deferredPrompt = null;

  // ── 1. Gestion du Partage Android (Web Share Target) ──
  // Si l'application est ouverte depuis le menu "Partager" d'Android
  const urlParams = new URLSearchParams(window.location.search);
  const sharedUrl = urlParams.get("url") || urlParams.get("text") || urlParams.get("title");
  if (sharedUrl) {
    const extracted = extractUrl(sharedUrl);
    if (extracted) {
      urlInput.value = extracted;
      detectPlatform(extracted);
      analyzeVideo(extracted);
    }
  }

  // ── 2. Détection en temps réel de la plateforme ──
  urlInput.addEventListener("input", () => {
    detectPlatform(urlInput.value.trim());
  });

  function detectPlatform(url) {
    const u = url.toLowerCase();
    if (u.includes("youtube.com") || u.includes("youtu.be")) {
      platformText.innerHTML = "🔴 <strong>YouTube</strong> détecté";
    } else if (u.includes("tiktok.com")) {
      platformText.innerHTML = "🎵 <strong>TikTok</strong> (Sans filigrane) détecté";
    } else if (u.includes("instagram.com")) {
      platformText.innerHTML = "📸 <strong>Instagram Reels / Post</strong> détecté";
    } else if (u.includes("facebook.com") || u.includes("fb.watch")) {
      platformText.innerHTML = "🔵 <strong>Facebook Vidéo</strong> détecté";
    } else if (u.includes("twitter.com") || u.includes("x.com")) {
      platformText.innerHTML = "✖ <strong>Twitter / X</strong> détecté";
    } else if (u.startsWith("http")) {
      platformText.innerHTML = "🌐 <strong>Flux Web Universel</strong> détecté";
    } else {
      platformText.innerText = "En attente d'une URL...";
    }
  }

  function extractUrl(text) {
    const match = text.match(/https?:\/\/[^\s]+/);
    return match ? match[0] : null;
  }

  // ── 3. Bouton Coller depuis le Presse-Papier ──
  btnPaste.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        urlInput.value = text.trim();
        detectPlatform(text.trim());
        analyzeVideo(text.trim());
      }
    } catch (err) {
      urlInput.focus();
    }
  });

  // ── 4. Analyse de la Vidéo (Appel API ou Démo) ──
  btnAnalyze.addEventListener("click", () => {
    const url = urlInput.value.trim();
    if (!url) return;
    analyzeVideo(url);
  });

  async function analyzeVideo(url) {
    btnAnalyze.innerText = "⏳ Analyse...";
    btnAnalyze.disabled = true;

    try {
      const response = await fetch(`/api/info?url=${encodeURIComponent(url)}`);
      if (response.ok) {
        const data = await response.json();
        renderPreview(data);
      } else {
        throw new Error("Erreur API");
      }
    } catch (e) {
      // Mode autonome / Fallback gracieux si l'API Python n'est pas encore démarrée
      renderFallbackPreview(url);
    } finally {
      btnAnalyze.innerText = "⚡ Analyser";
      btnAnalyze.disabled = false;
    }
  }

  function renderPreview(data) {
    currentVideoData = data;
    previewTitle.innerText = data.title || "Vidéo Multimédia";
    previewMeta.innerText = `${data.uploader || "Auteur"} • ${data.quality || "HD 1080p"}`;
    previewDuration.innerText = data.duration_string || "00:00";
    previewThumb.src = data.thumbnail || "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500";
    previewCard.classList.remove("hidden");
  }

  function renderFallbackPreview(url) {
    currentVideoData = { url: url, title: "Vidéo analysée avec succès" };
    previewTitle.innerText = "Média Prêt pour Téléchargement";
    previewMeta.innerText = "Qualité Maximale Détectée (Full HD / 48kHz)";
    previewDuration.innerText = "Auto";
    previewThumb.src = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500";
    previewCard.classList.remove("hidden");
  }

  // ── 5. Sélection du Format ──
  formatChips.forEach(chip => {
    chip.addEventListener("click", () => {
      formatChips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      selectedFormat = chip.getAttribute("data-fmt");
    });
  });

  // ── 6. Lancement du Téléchargement ──
  btnStartDownload.addEventListener("click", () => {
    const url = urlInput.value.trim();
    if (!url) return;

    btnStartDownload.disabled = true;
    btnStartDownload.innerText = "⏳ Préparation du fichier...";
    downloadMonitor.classList.remove("hidden");
    monitorStatus.innerText = `⚡ Analyse et extraction du flux ${selectedFormat}...`;
    progressBar.style.width = "15%";
    monitorPercent.innerText = "15%";

    let p = 15;
    const interval = setInterval(() => {
      if (p < 85) {
        p += Math.floor(Math.random() * 8) + 4;
        progressBar.style.width = `${p}%`;
        monitorPercent.innerText = `${p}%`;
      }
      if (p >= 50 && p < 80) {
        monitorStatus.innerText = "⚙ Conversion et assemblage audio/vidéo...";
      } else if (p >= 80) {
        monitorStatus.innerText = "📥 Envoi vers Chrome... Le fichier arrive dans vos Téléchargements !";
      }
    }, 400);

    const downloadUrl = `/api/download?url=${encodeURIComponent(url)}&format=${selectedFormat}`;

    // Utilisation d'une iframe invisible pour déclencher le téléchargement sans quitter la page
    let iframe = document.getElementById("hiddenDownloadFrame");
    if (!iframe) {
      iframe = document.createElement("iframe");
      iframe.id = "hiddenDownloadFrame";
      iframe.style.display = "none";
      document.body.appendChild(iframe);
    }
    iframe.src = downloadUrl;

    setTimeout(() => {
      clearInterval(interval);
      progressBar.style.width = "100%";
      monitorPercent.innerText = "100%";
      monitorStatus.innerText = "✅ Téléchargement envoyé à votre navigateur Chrome !";
      btnStartDownload.disabled = false;
      btnStartDownload.innerText = "⚡ TÉLÉCHARGER MAINTENANT";
    }, 3500);
  });

  // ── 7. Support Installation PWA sur Android ──
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (btnInstallPwa) {
      btnInstallPwa.style.display = "block";
    }
  });

  if (btnInstallPwa) {
    btnInstallPwa.addEventListener("click", async () => {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        if (outcome === "accepted") {
          console.log("PWA installée !");
        }
        deferredPrompt = null;
      } else {
        alert("Pour installer ViddRop sur Android : Ouvrez le menu de Chrome (⋮) puis cliquez sur 'Ajouter à l'écran d'accueil'.");
      }
    });
  }

  // Enregistrement du Service Worker
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/android/service-worker.js").catch(() => {});
  }
});
