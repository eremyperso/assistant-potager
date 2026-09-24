**ID :** INC-005
**Titre :** /plan tronque un nom de parcelle multi-mots au premier mot
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-09-23

**Reproduction (jeu de test réalisé) :**
Sur Telegram, `/parcelles` liste bien une parcelle nommée "PLANCHE CENTRALE".
Ensuite, `/plan planche centrale` est tapé pour consulter son plan de
cultures.

**Résultat obtenu :**
Le bot répond « Aucune culture active sur la parcelle PLANCHE. » — il ne
retient que le premier mot ("planche") du nom saisi et ne retrouve donc pas
la parcelle "PLANCHE CENTRALE", même si celle-ci a des cultures actives.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
`/plan planche centrale` doit reconnaître le nom complet "PLANCHE CENTRALE"
et afficher le plan/détail de cette parcelle (cultures actives, rangs, etc.),
comme pour toute parcelle dont le nom est composé de plusieurs mots.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : Bot Telegram (`app/bot/`)
- Nature probable : régression logique — découpage du nom de parcelle sur un
  seul token au lieu de gérer un nom multi-mots
- Fichiers probablement concernés : `app/bot/commandes_plan.py` (ligne 71,
  `filtre_arg = args_sans_date[0]...` ne prend que le premier mot des
  arguments) — même famille de défaut que INC-004, sur une commande
  différente
- Corpus de connaissance concerné : non

**Labels :** incident, bot
