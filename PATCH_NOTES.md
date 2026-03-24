# Patch — Synthèse vocale dynamique (TTS toggle)

## Fichiers modifiés

| Fichier | Nature |
|---------|--------|
| `app/utils/tts.py` | Remplace `TTS_ENABLED = True` par état persistant JSON |
| `app/bot.py` | Import TTS étendu + 3 handlers `/tts` + appels décommentés |
| `.gitignore` | Exclusion de `utils/.tts_state.json` |

---

## Déploiement

### 1. Remplacer les 2 fichiers Python

```
assistant-potager/app/utils/tts.py   ← remplacer
assistant-potager/app/bot.py          ← remplacer
```

### 2. Mettre à jour .gitignore (racine du repo)

Ajouter la ligne :
```
utils/.tts_state.json
```

### 3. Aucune migration SQL nécessaire

Aucun changement de schéma DB.

### 4. Aucune nouvelle dépendance

`gtts` était déjà dans requirements.txt.

---

## Utilisation depuis Telegram

| Commande | Effet |
|----------|-------|
| `/tts` | Affiche l'état actuel + rappel des commandes |
| `/tts_on` | Active les réponses vocales (persiste au redémarrage) |
| `/tts_off` | Désactive les réponses vocales (persiste au redémarrage) |

**Par défaut :** désactivé au 1er lancement (comportement identique à avant).

---

## Comportement de la persistance

L'état TTS est sauvegardé dans `utils/.tts_state.json` (fichier local, hors Git).  
Il survit au redémarrage du bot. Pour réinitialiser manuellement :

```bash
del app\utils\.tts_state.json   # Windows
rm app/utils/.tts_state.json    # Linux/Mac
```

---

## Synthèse vocale active sur 4 événements

1. **Enregistrement d'action** — lecture du récapitulatif (action + culture + quantité + date)
2. **Réponse analytique** (`/ask`, question vocale) — lecture de la réponse Groq
3. **Statistiques** (`/stats`) — lecture du résumé
4. **Historique** (`/historique`) — lecture des 10 derniers événements

---

## BotFather — commandes à déclarer (optionnel)

Pour que les commandes apparaissent dans le menu de suggestion Telegram :

```
/setcommands → sélectionner votre bot → coller :

start - Démarrer l'assistant
stats - Statistiques du potager
historique - 10 derniers événements
ask - Poser une question analytique
corriger - Corriger un enregistrement
tts - État de la synthèse vocale
tts_on - Activer les réponses vocales
tts_off - Désactiver les réponses vocales
```
