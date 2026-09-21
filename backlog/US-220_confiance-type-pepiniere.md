**ID :** US-220
**Titre :** Tenir compte du type de pépinière dans la confiance d'un semis en pépinière
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier qui n'a qu'un châssis froid
Je veux que l'application ne m'annonce pas trois étoiles pour semer des tomates en pépinière en février comme si j'avais une serre chauffée
Afin de me fier au niveau de confiance d'un semis en pépinière autant qu'à celui d'un semis en pleine terre

**Contexte fonctionnel :**
Le moteur de confiance (US-178) évalue cinq règles : fenêtre conseillée (R1), dernière gelée moyenne de la zone (R2), gel annoncé sur la quinzaine (R3), nuits douces (R4), saison restante (R5). Pour un semis en pépinière, il tient aujourd'hui R2, R3 et R4 **pour acquises**, et le dit lui-même : « la pépinière non chauffée de février attend l'abri d'US-181 » (`docs/domaines/calendrier-cultural.md`).

US-208 donne désormais son **type** à chaque pépinière. Cette US l'utilise comme **modulateur de règles**, sur le principe arrêté par US-181 pour les abris des parcelles : « un abri déclaré rend la règle non pertinente, il ne « réchauffe » pas la prévision ». Aucune simulation, aucun décalage de température : une règle est acquise, avec son motif, ou évaluée normalement.

**Table des modulateurs d'un semis en pépinière :**

| Type de pépinière | R2 dernière gelée | R3 gel annoncé | R4 nuits douces | Motif |
|---|---|---|---|---|
| **chaude** | acquise | acquise | acquise | « pépinière chauffée » |
| **froide** | évaluée | acquise | évaluée | « pépinière froide : à l'abri du gel annoncé, pas des nuits fraîches » |
| **type non renseigné** | acquise | acquise | acquise | comportement actuel, **avec un avertissement** : « type de pépinière non renseigné : la confiance suppose une pépinière chauffée » |

La ligne *froide* reprend exactement celle du **châssis** d'US-181 / CA4 (R3 acquise, R4 et R2 évaluées). R1 et R5 ne sont jamais modulées : un abri, chauffé ou non, ne déplace pas la fenêtre (US-181 / CA6).

**Critères d'acceptance :**

*Le moteur*
- [ ] CA1 : La table ci-dessus est écrite **une seule fois**, dans le bloc « Barème » du moteur (US-178 / CA3), à côté — ou au sein — de la table des abris d'US-181 si celle-ci est livrée ; sinon, cette US crée la table qu'US-181 étendra. Un test la compare ligne par ligne
- [ ] CA2 : **Quelle pépinière** : une confiance demandée pour une parcelle pépinière prend son type. Sans parcelle, elle prend la **meilleure pépinière du potager** — chaude, puis type non renseigné, puis froide — et la réponse nomme celle qui a servi (« évalué pour la serre, pépinière chaude »). Un potager sans pépinière garde le comportement actuel, avec l'avertissement « aucune pépinière déclarée »
- [ ] CA3 : Quand le potager a des pépinières **des deux types**, la lecture groupée rend l'évaluation du semis en pépinière pour chacun, pour que l'écran puisse dire, par exemple, « pépinière chaude ★★★ · pépinière froide ★★☆ »
- [ ] CA4 : Les motifs et l'avertissement sont ajoutés au gabarit de réponse (`GABARIT_REPONSE_CONFIANCE_BOT.md`) et figés par test, « à la lettre », comme les motifs existants (US-178)
- [ ] CA5 : Un semis **en pleine terre** et une **plantation** ne sont pas touchés ; leur éventuelle modulation relève de l'abri de la parcelle (US-181)

*Là où cela se voit*
- [ ] CA6 : `/confiance tomate pepiniere` et `/confiance tomate pepiniere serre` au bot rendent le niveau modulé et son motif (US-179)
- [ ] CA7 : La fiche calendrier (US-183), la pastille du Plan (US-180), la puce de Stocks, les cartes de l'écran Cultures (US-205) et la carte « À semer » de la Pépinière (US-215) lisent la même évaluation : aucune valeur différente d'un écran à l'autre pour la même culture, le même jour
- [ ] CA8 : Dans la carte « À semer » et sur la ligne « + semer maintenant » du calendrier de pépinière (US-218), une culture évaluée pour les deux types affiche les deux niveaux, écrits en mots
- [ ] CA9 : Le changement de niveau pour les potagers existants est **mesuré** avant livraison sur une base de taille réelle — nombre de cultures dont la confiance de semis en pépinière change, et dans quel sens — et consigné dans l'US

*Définition de terminé*
- [ ] CA10 : La fiche `calendrier-et-zone-climatique.md` explique pourquoi le type de pépinière change le niveau d'un semis en pépinière, et ce que veut dire l'avertissement (US-099 / CA9) ; `docs/domaines/calendrier-cultural.md` remplace la mention « attend l'abri d'US-181 » par la table
- [ ] CA11 : Des tests couvrent : les trois lignes de la table, le choix de la pépinière avec et sans parcelle, le potager sans pépinière, les deux types présents, l'invariance de R1 et R5, la non-modulation du semis en pleine terre et de la plantation, l'égalité des valeurs entre bot, fiche calendrier et lecture groupée

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (moteur de confiance), interaction Telegram, consultation
- Migration BDD requise : **non**
- Dépendances : **US-208** (type de pépinière) ; US-178, US-179, US-180, US-183 (livrées) ; coordination avec **US-181** (abri et paillage, non livrée) pour une table unique
- Impact tokens : zéro
- Point de vigilance : la ligne « type non renseigné » **conserve** le comportement actuel pour ne pas faire chuter d'un coup la confiance de tous les potagers le jour de la livraison ; c'est une décision produit, à revoir quand les pépinières auront été typées. L'avertissement rend l'hypothèse visible
- Point de vigilance : la table est une **décision produit**, pas une mesure (même statut que la table des abris d'US-181)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Semer des tomates au châssis froid en février
  Given le potager, en zone continentale, n'a qu'une pépinière : le châssis, pépinière froide
  And des nuits à 1 °C annoncées cette semaine
  When je demande la confiance pour semer des tomates en pépinière le 15 février
  Then la règle du gel annoncé est acquise avec le motif "pépinière froide"
  And la règle des nuits douces est perdue
  And la règle de la dernière gelée de la zone est évaluée normalement

Scénario: La serre chauffée
  Given la serre est une pépinière chaude
  When je demande la confiance pour semer des tomates en pépinière dans la serre le 15 février
  Then les règles de dernière gelée, de gel annoncé et de nuits douces sont acquises avec le motif "pépinière chauffée"

Scénario: Deux pépinières
  Given le potager a la serre, pépinière chaude, et le châssis, pépinière froide
  When j'ouvre la Pépinière le 15 février
  And des nuits à 1 °C annoncées cette semaine
  Then la carte "À semer" affiche pour la tomate un niveau pour la pépinière chaude et un niveau plus bas pour la pépinière froide
  And chacun est écrit en toutes lettres avec ses étoiles

Scénario: Type non renseigné
  Given la seule pépinière du potager n'a pas de type
  When je demande la confiance pour semer des tomates en pépinière
  Then le niveau est celui d'aujourd'hui
  And la réponse avertit que la confiance suppose une pépinière chauffée

Scénario: La fenêtre ne bouge pas
  Given la serre est une pépinière chaude
  When je demande la confiance pour semer des tomates en pépinière en juillet
  Then la règle de la fenêtre conseillée est perdue
```

**Labels GitHub :** `us`, `backend`, `bot`, `confiance`, `pepiniere`
