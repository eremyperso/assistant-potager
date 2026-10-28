**ID :** US-269
**Titre :** Enregistrer un geste sans dépendre de Telegram
**Épic :** ÉPIC 15 — Compagnon dans la PWA *(numéro à valider, voir `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md`)*

**Story :**
En tant que jardinier
Je veux que l'enregistrement d'un geste fonctionne de la même façon quel que soit le canal
Afin de pouvoir, plus tard, confirmer un geste directement dans la PWA

**Contexte fonctionnel :**
Lot 6 du cadrage (§0, §4.6). Le chemin d'écriture des gestes (`_parse_and_save`, `_do_save_items`) vit dans `app/bot/` et prend un `Update` Telegram. **Prérequis de la levée d'A16** (D3). US techniquement indépendante, réalisable en parallèle des lots 1 à 5.

**Critères d'acceptance :**
- [ ] CA1 : Un service `app/services/gestes.py` enregistre un geste à partir de données structurées, sans objet Telegram.
- [ ] CA2 : Le bot appelle ce service ; aucun changement visible pour le jardinier (mêmes messages, mêmes stocks, mêmes événements).
- [ ] CA3 : Aucun `db.query` direct hors `app/services/` (test US-041 vert).
- [ ] CA4 : Les tests existants de saisie et d'enregistrement restent verts sans modification de leurs attentes.
- [ ] CA5 : Un test appelle le service directement (sans `Update`) et obtient le même événement que par le bot.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement
- Migration BDD requise : non
- Dépendances : aucune ; **livrer d'abord** les modifications en cours sans lien sur `app/bot/enregistrement.py` (pépinière, stock)
- Production conseillée : **Opus 5.5, effort `high`** — refactorisation à comportement constant de gros fichiers du bot, avec de nombreux cas de stock et de cycle de vie.

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given un geste structuré "semis radis planche Sud 2 rangs"
When il est enregistré par le service gestes sans Update Telegram
Then l'événement créé est identique à celui produit par le bot pour la même phrase
```

**Labels GitHub :** `us`, `compagnon`, `pwa`, `refactorisation`
