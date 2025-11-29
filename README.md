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

## Exemple de code utilisable
Le dépôt inclut désormais un prototype Python (module `dj_identifier`) pour segmenter un set, fingerprint chaque segment et le comparer à une base JSON de références locales.

### Installation minimale
```
pip install librosa numpy
```

### Lancer l'identification
```
python -m dj_identifier.cli set.wav --bootstrap examples/fingerprints.json --max-segments 12
```

- `--bootstrap` : fichier JSON optionnel contenant des empreintes connues (voir ci-dessous).
- `--fingerprints` : chemin où persister/charger la base d'empreintes locale.

### Mode "j'upload mon set et ça marche"
Un petit serveur HTTP est fourni pour accepter un fichier uploadé et renvoyer les morceaux détectés. Installe `fastapi` et `uvicorn`, démarre le serveur puis envoie simplement le fichier audio.

```bash
pip install fastapi uvicorn
uvicorn dj_identifier.server:app --port 8000
```

Le serveur précharge automatiquement la démo `examples/fingerprints.json` et écrit sa base
`fingerprints.json` à la racine du dépôt, peu importe le répertoire depuis lequel `uvicorn`
est lancé. Remplace ces chemins en configurant ta propre base avant de démarrer si tu as
tes empreintes.

Ensuite, envoie ton set :

```bash
curl -F "file=@set.wav" http://127.0.0.1:8000/identify | jq
```

La réponse contient les timecodes et les titres (d'après les empreintes connues) sous forme JSON, par exemple :

```json
{
  "matches": [
    {
      "track_id": "track-01",
      "title": "Artist One - Intro",
      "artist": "Artist One",
      "start": 0.0,
      "end": 92.3,
      "confidence": 1.0
    }
  ]
}
```

### Identifier directement un .mp4/.mkv
Si ton set est dans un conteneur vidéo (MP4/MKV), le script `identify_video.py` extrait l'audio avec `ffmpeg` et lance le pipeline :

```bash
pip install librosa numpy  # dépendances audio
sudo apt-get install ffmpeg
python identify_video.py chemin/vers/set.mp4
```

Sans argument, le script demande simplement le chemin du fichier. Le résultat liste chaque morceau avec son timecode :

```
[00:00 - 01:32] Artist One - Intro (confiance 1.00)
[01:32 - 03:05] Artist Two - Anthem (confiance 0.85)
```

### Structure d'un fichier d'empreintes
```json
{
  "track-01": {
    "title": "Artist One - Intro",
    "artist": "Artist One",
    "hashes": ["ab12cd..."]
  }
}
```

### Utilisation programmatique
```python
from dj_identifier.pipeline import bootstrap_store, run_pipeline

store = bootstrap_store({
    "track-01": {"title": "Artist One - Intro", "artist": "Artist One", "hashes": ["ab12cd"]},
    "track-02": {"title": "Artist Two - Anthem", "artist": "Artist Two", "hashes": ["de34fa"]},
})

matches = run_pipeline("set.wav", store)
for match in matches:
    print(match.segment.start, match.segment.end, match.title, match.artist, match.confidence)
```

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
