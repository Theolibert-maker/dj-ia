# DJ Set Track Identifier

Ce dépôt décrit une approche simple pour créer une IA capable de recevoir un set de DJ (enregistrement audio) et de générer une liste de lecture avec les timecodes et les titres des morceaux détectés.

## Fonctionnalités cibles
- Ingestion d'un fichier audio longue durée (set mixé).
- Segmentation des transitions pour repérer le début de chaque morceau.
- Identification de chaque morceau via empreintes audio.
- Génération d'une feuille de timecode exportable (CSV/JSON) indiquant titre, artiste et horodatage.

## Pipeline proposé
1. **Prétraitement audio** : convertir en WAV mono 44.1 kHz pour homogénéiser l'entrée.
2. **Détection de changement de piste** :
   - Extraire des caractéristiques de spectre (chroma, MFCC).
   - Appliquer une détection de ruptures (ex. `librosa.segment.agglomerative` ou `ruptures` avec le coût de divergence de spectre) pour estimer les points de transition.
3. **Empreintes audio** :
   - Générer une empreinte (fingerprint) par segment grâce à `chromaprint`/`fpcalc`.
   - Interroger une base de données (p. ex. AcoustID ou une base interne) pour récupérer titre/artist/album.
4. **Consolidation** : si plusieurs segments correspondent au même morceau, fusionner et lisser les timecodes (tolérance de quelques secondes autour des transitions).
5. **Export** : produire un fichier JSON/CSV avec `start_time`, `end_time`, `artist`, `title`, `confidence`.

## Exemple minimal (pseudocode)
```python
import json
import librosa
import numpy as np
from acoustid import fingerprint_file

AUDIO_PATH = "set.wav"

# 1) Charger l'audio
signal, sr = librosa.load(AUDIO_PATH, sr=44100, mono=True)

# 2) Détection de transitions basique
chroma = librosa.feature.chroma_stft(y=signal, sr=sr)
flux = np.mean(np.abs(np.diff(chroma, axis=1)), axis=0)
boundaries = librosa.onset.onset_detect(onset_envelope=flux, sr=sr, units="time")
segments = list(zip([0.0] + boundaries.tolist(), boundaries.tolist() + [len(signal)/sr]))

# 3) Empreintes + lookup (schéma simplifié)
tracks = []
for start, end in segments:
    # Sauvegarder le segment temporaire
    segment_path = "segment.wav"
    librosa.output.write_wav(segment_path, signal[int(start*sr):int(end*sr)], sr)
    fp, dur = fingerprint_file(segment_path)
    # TODO: requête API AcoustID avec l'empreinte pour récupérer les métadonnées
    tracks.append({"start": start, "end": end, "artist": None, "title": None, "confidence": None})

# 4) Export
with open("playlist.json", "w") as f:
    json.dump(tracks, f, indent=2)
```

## Points clés pour la production
- Prévoir une base d'empreintes locale ou un cache pour réduire les appels réseau.
- Nettoyer les segments (filtres passe-bas/normalisation) avant fingerprinting pour améliorer la robustesse.
- Ajouter un modèle de classification des transitions basé sur un petit réseau CNN/CRNN pour réduire les faux positifs.
- Enrichir l'export avec l'URL source (Spotify/YouTube) et la confiance retournée par l'API.

## Ressources utiles
- [`librosa`](https://librosa.org/) pour l'analyse audio.
- [`chromaprint`](https://acoustid.org/chromaprint) et [`acoustid`](https://github.com/beetbox/pyacoustid) pour les empreintes et l'identification.
- [`spleeter`](https://github.com/deezer/spleeter) pour séparer les stems si besoin d'isoler la mélodie/basse avant fingerprinting.

Cette base fournit un point de départ pour assembler rapidement une IA capable d'annoter automatiquement un set de DJ avec les timecodes et les titres des morceaux.
