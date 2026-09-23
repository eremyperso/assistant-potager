**ID :** INC-004
**Titre :** /parcelle modifier échoue si le nom de la parcelle contient un espace
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-09-22

**Reproduction (jeu de test réalisé) :**
En ligne (dicté), demande de modification d'une parcelle pour y inclure un
nombre de rangs : message texte "la parcelle tomate à 7 rangs", résolu par
l'interpréteur en commande `/parcelle modifier planche tomate rangs=7` (le
nom réel de la parcelle est "planche tomate", composé de deux mots).

**Résultat obtenu :**
Le bot lève une `LookupError: planche` dans `update_parcelle`
(utils/parcelles.py:374), puis échoue également à envoyer le message d'erreur
de repli ("Parcelle introuvable") avec une `telegram.error.BadRequest: Can't
parse entities` — la commande échoue intégralement, sans confirmation ni
message d'erreur exploitable pour l'utilisateur.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
La commande de modification d'une parcelle avec déclaration du nombre de
rangs doit fonctionner même quand le nom de la parcelle est composé de
plusieurs mots séparés par des espaces (ex. "planche tomate") — la parcelle
doit être retrouvée et mise à jour, avec confirmation au jardinier.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : Bot Telegram (`app/bot/`)
- Nature probable : régression logique — découpage du nom de parcelle sur un
  seul token au lieu de gérer un nom multi-mots
- Fichiers probablement concernés : `app/bot/commandes_parcelle.py` (ligne
  102, `nom = ctx.args[1].strip()` ne prend que le premier mot du nom) ;
  possiblement aussi un second défaut sur le message d'erreur de repli
  (Markdown mal formé côté Telegram)
- Corpus de connaissance concerné : non

**Labels :** incident, bot
