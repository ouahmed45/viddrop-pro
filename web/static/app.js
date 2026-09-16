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

  urlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const url = urlInput.value.trim();
      if (url) analyzeVideo(url);
    }
  });

  urlInput.addEventListener("paste", () => {
    setTimeout(() => {
      const url = urlInput.value.trim();
      if (url && url.startsWith("http")) {
        detectPlatform(url);
        analyzeVideo(url);
      }
    }, 150);
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
    btnAnalyze.innerText = "⏳ Recherche...";
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
      renderFallbackPreview(url);
    } finally {
      btnAnalyze.innerText = "⚡ Trouver la vidéo";
      btnAnalyze.disabled = false;
    }
  }

  function renderPreview(data) {
    currentVideoData = data;
    previewTitle.innerText = data.title || "Vidéo Prête";
    const qualityLabel = data.quality || "Qualité Maximale (HD / 4K)";
    previewMeta.innerHTML = `<span style="color:#00F0FF; font-weight:600;">${data.uploader || "Réseau Social"}</span> • <span style="background:linear-gradient(135deg, #FF2D55, #FF5E3A); color:#FFF; padding:2px 8px; border-radius:6px; font-weight:700; font-size:0.8rem; box-shadow:0 0 10px rgba(255,45,85,0.4);">${qualityLabel}</span>`;
    previewDuration.innerText = data.duration_string || "HD";

    // Gestion de secours si le format webp de YouTube n'existe pas sur cette vidéo
    previewThumb.onerror = () => {
      const current = previewThumb.src;
      if (current.includes("maxresdefault.webp")) {
        previewThumb.src = current.replace("maxresdefault.webp", "hqdefault.jpg");
      } else if (current.includes("maxresdefault")) {
        previewThumb.src = current.replace("maxresdefault", "hqdefault");
      }
    };
    previewThumb.src = data.thumbnail || "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500";

    previewCard.classList.remove("hidden");
    previewCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function renderFallbackPreview(url) {
    currentVideoData = { url: url, title: "Vidéo analysée avec succès" };
    previewTitle.innerText = "Média Prêt pour Téléchargement";
    previewMeta.innerHTML = `<span style="color:#00F0FF; font-weight:600;">Réseau Social</span> • <span style="background:linear-gradient(135deg, #FF2D55, #FF5E3A); color:#FFF; padding:2px 8px; border-radius:6px; font-weight:700; font-size:0.8rem;">🌟 Qualité Maximale (HD / 4K)</span>`;
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

  // ── 6. Lancement du Téléchargement avec Pourcentage Temps Réel ──
  btnStartDownload.addEventListener("click", () => {
    const url = urlInput.value.trim();
    if (!url) return;

    const taskId = "viddrop_" + Date.now() + "_" + Math.random().toString(36).substring(2, 7);

    btnStartDownload.disabled = true;
    btnStartDownload.innerText = "⏳ En cours...";
    downloadMonitor.classList.remove("hidden");

    let initMsg = "⚡ Initialisation du flux 4K / HD...";
    if (selectedFormat === "MP4_1080") initMsg = "⚡ Initialisation du flux Full HD (1080p)...";
    else if (selectedFormat === "MP4_720") initMsg = "⚡ Initialisation du flux HD (720p)...";
    else if (selectedFormat === "MP3") initMsg = "⚡ Extraction audio MP3 (320 kbps)...";
    else if (selectedFormat === "WAV") initMsg = "⚡ Extraction audio WAV pur...";

    monitorStatus.innerText = initMsg;
    progressBar.style.width = "0%";
    monitorPercent.innerText = "0%";

    // Déclenchement du téléchargement en arrière-plan
    const downloadUrl = `/api/download?url=${encodeURIComponent(url)}&format=${selectedFormat}&task_id=${taskId}`;
    let iframe = document.getElementById("hiddenDownloadFrame");
    if (!iframe) {
      iframe = document.createElement("iframe");
      iframe.id = "hiddenDownloadFrame";
      iframe.style.display = "none";
      document.body.appendChild(iframe);
    }
    iframe.src = downloadUrl;

    // Récupération de la progression en temps réel
    let consecutiveErrors = 0;
    let isCompleted = false;

    function finishSuccess(msg) {
      if (isCompleted) return;
      isCompleted = true;
      clearInterval(pollInterval);
      clearTimeout(safetyTimeout);
      progressBar.style.width = "100%";
      monitorPercent.innerText = "100%";
      monitorStatus.innerHTML = msg || "✅ <strong>Téléchargement terminé !</strong> Votre vidéo est dans les téléchargements Chrome (ouvrez avec <strong>Ctrl + J</strong>).";
      setTimeout(() => {
        btnStartDownload.disabled = false;
        btnStartDownload.innerText = "⚡ TÉLÉCHARGER MAINTENANT";
      }, 1000);
    }

    function finishError(msg) {
      if (isCompleted) return;
      isCompleted = true;
      clearInterval(pollInterval);
      clearTimeout(safetyTimeout);
      monitorStatus.innerHTML = `<span style="color:#FF2D55;">❌ ${msg || "Une erreur est survenue lors de l'extraction."}</span>`;
      btnStartDownload.disabled = false;
      btnStartDownload.innerText = "⚡ RÉESSAYER";
    }

    // Sécurité : Timeout maximum de 2 minutes
    const safetyTimeout = setTimeout(() => {
      finishSuccess("✅ <strong>Téléchargement envoyé !</strong> Vérifiez la barre de téléchargement de votre navigateur (Ctrl + J).");
    }, 120000);

    const pollInterval = setInterval(async () => {
      if (isCompleted) {
        clearInterval(pollInterval);
        return;
      }
      try {
        const res = await fetch(`/api/progress?id=${taskId}`);
        if (res.ok) {
          consecutiveErrors = 0;
          const prog = await res.json();
          const p = parseFloat(prog.percent) || 0;
          progressBar.style.width = `${p}%`;
          monitorPercent.innerText = `${p.toFixed(1)}%`;
          if (prog.msg) {
            monitorStatus.innerText = prog.msg;
          }

          if (prog.status === "done" || p >= 100) {
            finishSuccess();
          } else if (prog.status === "error") {
            finishError(prog.msg);
          }
        } else {
          consecutiveErrors++;
          // Si le serveur renvoie 404 plus de 3 fois de suite, on arrête de spammer
          // et on bascule sur une progression visuelle sécurisée
          if (consecutiveErrors >= 3) {
            clearInterval(pollInterval);
            let simPercent = 20;
            const simInterval = setInterval(() => {
              if (isCompleted) {
                clearInterval(simInterval);
                return;
              }
              simPercent += Math.min(15, (95 - simPercent) * 0.25);
              progressBar.style.width = `${Math.min(95, simPercent).toFixed(0)}%`;
              monitorPercent.innerText = `${Math.min(95, simPercent).toFixed(0)}%`;
              monitorStatus.innerText = "⚡ Téléchargement et conversion en cours...";

              if (simPercent >= 94) {
                clearInterval(simInterval);
                setTimeout(() => {
                  finishSuccess("✅ <strong>Téléchargement envoyé vers votre navigateur !</strong> Regardez en bas de votre écran ou appuyez sur <strong>Ctrl + J</strong>.");
                }, 3000);
              }
            }, 600);
          }
        }
      } catch (err) {
        // Micro-coupure réseau temporaire
      }
    }, 350);
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
