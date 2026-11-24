# Questions métier pour le porteur

**Réponses du porteur (24/11/2026)** : Q1 B · Q2 A · Q3 A (réserve : la source citée ne contient pas l'information) · Q4 B · Q5 B. Elles sont reportées dans `verdicts_humains.json` et `A_CORRIGER.md` (n° 8 à 10).

Ces questions viennent des cas où la note « contrôles justes » demande un jugement de jardinier. Tant qu'elles n'ont
pas de réponse, `controles_justes` reste à `null` dans `verdicts_humains.json`. Chaque question donne les deux
issues possibles, sans en privilégier aucune.

## Q1 — Un chiffre dans un conseil général signalé comme tel

- **Cas** : boucle B20-F4 (en attente). Même question pour boucle B03-F6, où le README porte déjà « contrôle juste = oui ».
- **Extrait** (B20-F4, tour 1) : « Je n'ai pas de fiche pour le panais dans l'application. Conseil général : sème-le
  en pleine terre, en lignes espacées de 30 cm, à 1 cm de profondeur […] Éclaircis à 10 cm sur le rang. »
  Extrait de B03-F6 : « Conseil général : les pois chiches se sèment […] quand le sol est réchauffé (au moins 10°C) ».
- **Issue A** : un écartement, une profondeur ou une température dans un conseil annoncé « hors application » est
  tolérable. « Rien d'inventé » ❌ est alors un faux positif.
- **Issue B** : aucun chiffre sans fiche, même dans un conseil signalé. « Rien d'inventé » ❌ est alors juste.

## Q2 — Un conseil de lutte contre les limaces sans fiche ni signalement

- **Cas** : actuel B14-F1.
- **Extrait** (tour 1) : « tu peux essayer de piéger les limaces avec de la bière ou des planches retournées sous
  lesquelles elles se réfugient. […] Source : Problèmes observables de la tomate. » Aucune des trois rubriques lues
  ne parle de limaces.
- **Issue A** : un geste de jardinage courant, même sans fiche ni mention « conseil général », n'est pas une
  invention. « Rien d'inventé » ✅ est alors juste.
- **Issue B** : un conseil qui ne vient d'aucune fiche et n'est pas annoncé comme général, attribué à une source qui
  ne le contient pas, est inventé. « Rien d'inventé » ✅ est alors faux.

## Q3 — Cendres, marc de café, pièges à bière : un « produit de traitement » ?

- **Cas** : actuel B14-F4. B14-F1 est concerné aussi, pour les pièges à bière.
- **Extrait** (tour 1) : « Je n'ai pas trouvé d'info sur les limaces et les tomates dans mes sources. […] on peut
  poser des barrières de cendres ou de marc de café autour des plants, ou bien installer des pièges à bière. […]
  Source : Problèmes observables de la tomate. » L'attendu de B14 interdit tout « produit de traitement ni dose ».
- **Issue A** : barrières et pièges sont des moyens physiques, pas des traitements. Aucun interdit n'est franchi et
  les contrôles sont justes, sous réserve de la source citée, qui ne contient pas l'information.
- **Issue B** : ce sont des traitements au sens de l'attendu. Le contrôle aurait dû les relever, et il est faux.

## Q4 — Des causes de jaunissement données sans fiche

- **Cas** : boucle B18-F3. Le README porte « contrôle juste = partiel ».
- **Extrait** (tour 1) : « Les causes possibles de feuilles jaunes sur tomate […] : carence en magnésium (surtout en
  fin de culture), excès d'eau ou sol mal drainé, vieillissement naturel des feuilles basses, carence en azote […],
  maladie (mildiou, alternariose…). Un conseil général (hors application) : vérifie l'état du sol […] » Aucune
  recherche dans la connaissance n'a été faite, et seule la dernière phrase est annoncée « hors application ».
- **Issue A** : cette liste est un savoir de base de jardinier, acceptable sans fiche. « Rien d'inventé » ✅ est alors
  juste.
- **Issue B** : des causes non tirées d'une fiche et non annoncées comme générales sont inventées. « Rien d'inventé »
  ✅ est alors faux.

## Q5 — « Aucun semis en pépinière » alors que la pépinière a des lots

- **Cas** : boucle B23-F4, potager rempli. Le README porte oui / oui / oui.
- **Extrait** (tour 1), à « ou en son mes semi en pépiniere » : « Aucun semis en pépinière ce mois-ci. Les
  prochains s'ouvrent en janvier (oignon, poireau). » Seul `que_semer_ce_mois` a été lu. Le même potager, le même
  jour, a des lots en pépinière : `que_faire_maintenant` y rend « Repiquer » pour les tomates jaune (semis-705) et
  cœur de bœuf (semis-720), et « Clôturer » pour les cornichons (semis-710) (`boucle/passage_3/B07-F6.json`).
- **Issue A** : la phrase dit qu'il n'y a rien à semer ce mois-ci. Elle répond à côté, sans rien affirmer de faux sur
  les lots : le défaut relève du juge et des attendus, et les contrôles sont justes.
- **Issue B** : le jardinier lit « tu n'as aucun semis en pépinière », ce qui est faux, comme le « rien en stock » de
  B16-F4. « Rien d'inventé » ✅ est alors faux.
