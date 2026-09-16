# Gabarit — réponse de confiance du bot (US-179)

> **Statut :** référence de rendu, à verser dans `docs/EPIC 8 - CONFIANCE CALENDRIER/` avec la
> capture `maquette-confiance-bot.png`. Claude Code doit reproduire ce gabarit **à la lettre** ;
> toute déviation se discute ici, pas dans le code.
> **Contraintes lues dans le dépôt :** `parse_mode="Markdown"` (legacy, 233 usages dans `bot.py`),
> boutons `InlineKeyboardButton`, format de log `HH:MM:SS │ LEVEL │ emoji MESSAGE`.

## 1. Structure du message — ordre fixe, six blocs

```
① *Culture · action · zone*                       ← gras, une ligne
② ★★☆  Confiance moyenne                          ← étoiles pleines/vides + libellé du niveau
③ ✅ motif gagné                                  ← un par ligne, dans l'ordre R1 → R5
   ✅ motif gagné
④ ⚠️ motif perdu                                  ← après les gagnés
⑤ ❔ motif indéterminé                             ← après les perdus, jamais omis
⑥ 🌾 Récolte attendue … si tu sèmes samedi        ← fourchette ou tiret, toujours au conditionnel
─── clavier inline : 3 boutons max, 1 ligne si ≤ 2, 2 lignes si 3 ───
```

Libellés du niveau : `★★★ Confiance élevée` · `★★☆ Confiance moyenne` · `★☆☆ Confiance faible`.
Caractères : `★` (U+2605) plein, `☆` (U+2606) vide — pas d'emoji ⭐, qui n'a pas de forme vide.

## 2. Gabarit Markdown (legacy Telegram)

```
*{culture} · {action} · zone {zone}*
{etoiles}  {libelle_niveau}

{lignes_motifs}

🌾 Récolte attendue {recolte_fourchette} si tu {verbe} {date_relative}
```

- `{lignes_motifs}` : une ligne par règle, préfixe `✅` / `⚠️` / `❔`, texte du motif tel que rendu par le
  moteur (US-178, tableau de règles). Jamais de motif reformulé côté bot.
- `{recolte_fourchette}` : « entre le 16 et le 26 juillet » ; ou « — » si la durée est inconnue, et la
  ligne devient `🌾 Récolte attendue : — (durée inconnue pour cette culture)`.
- `{verbe}` : « sèmes » / « plantes ». `{date_relative}` : « samedi », « le 20 mai », « aujourd'hui ».
- Échappement Markdown legacy : `_ * ` [` dans les noms de cultures, parcelles et motifs sont
  échappés avec le même utilitaire que le reste du bot. Test obligatoire avec un nom contenant `_`.
- Longueur : un message, jamais découpé. Si les motifs dépassent, c'est le moteur qui en rend trop.

## 3. Trois exemples rendus

**Deux étoiles — cas nominal (celui de la maquette)**
```
*Haricot · semis en pleine terre · zone océanique*
★★☆  Confiance moyenne

✅ Dans la fenêtre conseillée pour ta zone
✅ Dernière gelée moyenne passée
✅ Aucun gel annoncé sur 14 jours
⚠️ Nuits fraîches : levée lente probable
✅ La récolte arriverait avant la fin de saison

🌾 Récolte attendue entre le 16 et le 26 juillet si tu sèmes samedi
```
Clavier : `[ Enregistrer le semis ]` `[ Redemander dans 10 jours ]`

**Trois étoiles, potager sous serre (US-181)**
```
*Tomate · semis en pépinière · zone continental*
★★★  Confiance élevée

✅ Dans la fenêtre conseillée pour ta zone
✅ Semis en pépinière : gelée sans objet
✅ Aucun gel annoncé — parcelle sous serre, règle sans objet
✅ Nuits douces — parcelle sous serre, règle sans objet
✅ La récolte arriverait avant la fin de saison

🌾 Récolte attendue entre le 20 juillet et le 9 août si tu sèmes aujourd'hui
```
Clavier : `[ Enregistrer le semis ]` `[ Redemander dans 10 jours ]`

**Potager non localisé — plafond à deux étoiles**
```
*Courgette · semis en pleine terre · zone océanique*
★★☆  Confiance moyenne

✅ Dans la fenêtre conseillée pour ta zone
✅ Dernière gelée moyenne passée
❔ Météo indisponible : localise ton potager pour la prendre en compte
❔ Météo indisponible
✅ La récolte arriverait avant la fin de saison

🌾 Récolte attendue entre le 16 et le 26 juillet si tu sèmes samedi
```
Clavier : `[ Enregistrer le semis ]` `[ Localiser mon potager ]` / `[ Redemander dans 10 jours ]`

**Sans calendrier — pas de score**
```
*Ail · plantation · zone océanique*
Aucun calendrier pour l'ail dans ta zone : je ne peux pas évaluer.
Tu peux le compléter avec /calendrier fenetre ail plantation …
```
Clavier : aucun.

## 4. Clavier inline

| Bouton | Quand | `callback_data` (convention) | Effet |
|---|---|---|---|
| Enregistrer le semis / la plantation | score rendu | `conf:enr:{action}:{culture_id}:{date}:{parcelle_id\|-}` | ouvre le flux d'enregistrement existant, champs pré-remplis, confirmation habituelle |
| Redemander dans 10 jours | score rendu | `conf:redem:{action}:{culture_id}:{date+10}:{parcelle_id\|-}` | ré-évalue à date + 10 j, même message |
| Localiser mon potager | R3/R4 indéterminées faute de localisation | `conf:loc` | renvoie vers le parcours de localisation existant (US-074) |
| Semer sous voile *(maquette)* | ⚖️ **hors v1** — n'existe qu'avec US-181 ; à ne pas coder avant | — | — |

- `callback_data` ≤ 64 octets (limite Telegram) : identifiants numériques, date ISO courte.
- Aucun état `ctx.user_data` posé par l'envoi du message ; seul l'appui sur « Enregistrer » ouvre le flux
  existant, qui gère son propre état (US-179 / CA10).

## 5. Ce que Claude Code ne doit PAS faire

- Reformuler les motifs, en ajouter, en cacher un « indéterminé ».
- Rendre une date sèche (« récolte le 20 juillet ») : toujours une fourchette ou un tiret.
- Appeler le LLM pour rédiger la réponse : gabarit texte, zéro jeton (US-179 / CA2).
- Créer un nouveau chemin d'enregistrement : le bouton réutilise le flux existant.

## 6. Comment le passer à Claude Code

Verser ce fichier et la capture dans `docs/EPIC 8 - CONFIANCE CALENDRIER/`, puis :

```
Implémente backlog/US-179_bot-question-je-peux-semer.md.
Le rendu du message est spécifié dans docs/EPIC 8 - CONFIANCE CALENDRIER/GABARIT_REPONSE_CONFIANCE_BOT.md
(capture : maquette-confiance-bot.png) : reproduis-le à la lettre, sections 1 à 5.
Le moteur est celui d'US-178 (app/services/…) — ne recalcule rien, ne reformule aucun motif.
Avant de coder, lis CLAUDE.md et PATCH_NOTES.md, et vérifie l'ordre des handlers :
l'ouverture interrogative doit être testée avant la grammaire d'enregistrement (US-179 / CA8).
```
