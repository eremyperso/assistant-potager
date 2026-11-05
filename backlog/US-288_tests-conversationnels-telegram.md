**ID :** US-288
**Titre :** Jouer des scénarios de dialogue Markdown sur Telegram et produire un rapport
**Épic :** ÉPIC 13 — Agent interpréteur *(à valider)*

**Story :**
En tant que mainteneur du compagnon
Je veux écrire des dialogues en Markdown et les voir joués depuis un vrai compte Telegram devant le bot branché sur le vrai modèle
Afin de vérifier ce que le jardinier lit et ce qui est écrit en base, sans simuler à sa place l'état que les tests unitaires fabriquent

**Contexte fonctionnel :**
Les tests unitaires simulent l'état du bot et ne reproduisent pas l'agent ; `tools/evaluer_dialogues.py` (US-256) rejoue la cascade sur le vrai modèle mais en processus, sans handler, sans bouton inline et sans base. Le harnais `tests_conv/` comble l'écart : Telethon pilote un compte de test, le bot tourne en `APP_ENV=test`, et les vérifications lisent le texte, les boutons et la base. Voir `docs/domaines/tests-conversationnels.md`.

**Critères d'acceptance :**
- [x] CA1 — Un scénario est un fichier Markdown (en-tête, tours `> message` ou `[clic] libellé`, puces de vérification). Le parseur refuse un scénario mal formé en disant le fichier et la ligne ; `validate` ne lance rien.
- [x] CA2 — `/reset_test` n'est enregistrée qu'en `APP_ENV=test`, refuse une base sans « test » dans son nom, vide les données du potager et les états en attente du bot, et n'est jamais au menu.
- [x] CA3 — Le pilote envoie, clique un bouton par son libellé, attend la fin de réponse par quiescence (éditions comprises), respecte `FloodWait` et relance après une coupure.
- [x] CA4 — Vérifications déterministes : texte, regex, boutons, aucune écriture, écriture, événement, outil, latence. Le juge est parsé mais non branché.
- [x] CA5 — Verdict par scénario sur N passages : réussi, à surveiller, échec ; rapport JSON, HTML et JUnit avec version du bot, mode et modèle de l'agent, jetons consommés.
- [x] CA6 — `run` sans `--go` annonce le volume d'appels au modèle et ne lance rien.
- [ ] CA7 — Recette sur un bot de test réel : SC-000, puis SC-010 et SC-011 (libellés à calibrer) passent. **Nécessite le compte, le bot et la base de test.**
- [ ] CA8 — Juge LLM (modèle distinct de l'agent), calibré sur une vingtaine de tours annotés, accord ≥ 85 %.
- [ ] CA9 — CI : sous-ensemble `critique` sur pull request, campagne complète de nuit ; secrets du dépôt.

**Hors périmètre :**
- Simulateur de persona et mode rapide (injection d'Updates sans Telegram).

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : outillage de test, bot Telegram (mode test)
- Migration BDD requise : non
- Dépendances : `requirements-conv.txt` (telethon, pyyaml), jamais déployées
- Code concerné : `tests_conv/`, `app/services/mode_test.py`, `app/bot/mode_test.py`, `app/bot/application.py`
