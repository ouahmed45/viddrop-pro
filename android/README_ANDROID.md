# Guide Déploiement Android — ViddRop Studio Mobile

Ce dossier contient tout le nécessaire pour déployer et utiliser **ViddRop Studio** sur les appareils **Android**.

---

## Méthode 1 : Installation Instantanée PWA (Sans compilation)

Grâce au standard **Progressive Web App (PWA)** et au `manifest.json`, vous pouvez installer l'application directement sur n'importe quel smartphone Android :

1. Lancez le serveur web ViddRop sur votre machine :
   ```powershell
   python web/server.py
   ```
2. Sur votre smartphone connecté au même réseau Wi-Fi, ouvrez Chrome et accédez à :
   `http://<IP-DE-VOTRE-PC>:8080`
3. Chrome vous proposera automatiquement : **« Ajouter ViddRop à l'écran d'accueil »** (ou via le menu `⋮` de Chrome).
4. L'icône de l'application apparaît sur votre écran d'accueil Android et s'ouvre en plein écran sans barre d'adresse !

### 🎯 Intégration du Menu « Partager » Android (Share Target)
Une fois installée, ViddRop s'enregistre dans le système Android :
- Lorsque vous regardez une vidéo sur **TikTok**, **Instagram** ou **YouTube**, appuyez sur le bouton **Partager**.
- Sélectionnez **ViddRop** dans la liste des applications.
- ViddRop s'ouvre instantanément avec l'URL pré-remplie et prête au téléchargement !

---

## Méthode 2 : Compilation en APK Natif Android (Capacitor)

Si vous souhaitez générer un fichier `.apk` distribuable ou installable manuellement :

1. **Prérequis** : Avoir Node.js et Android Studio installés.
2. Initialiser Capacitor dans le dossier :
   ```bash
   npm install @capacitor/core @capacitor/cli @capacitor/android
   npx cap add android
   npx cap copy
   ```
3. Ouvrir le projet dans Android Studio :
   ```bash
   npx cap open android
   ```
4. Dans Android Studio, cliquez sur **Build > Build Bundle(s) / APK(s) > Build APK(s)** pour générer votre fichier `app-debug.apk` ou `app-release.apk`.
