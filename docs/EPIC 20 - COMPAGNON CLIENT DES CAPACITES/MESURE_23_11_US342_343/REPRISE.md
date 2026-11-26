# Reprise — mesure du 23/11/2026 (US-342 / US-343) et relecture humaine

Écrit le 24/11/2026, branche `refonte-architecture-agent`, avant la pause du porteur et le passage à une nouvelle branche
(refonte ergo / design). Ce dossier est la copie versionnée de `rapports_evaluation/US342_343_20261123/` (ce dossier-là est
dans `.gitignore` et ne part pas avec le commit).

## Où en est le code

- US-342 (boucle à capacités, interrupteur `COMPAGNON_MOTEUR`) et US-343 (fil complet compacté, migration v81) sont **codées
  et testées** (58 tests verts), version 3.140.0, Jira PIA-325 / PIA-326 en « Revue en cours ».
- **Elles ne sont PAS validées** : la mesure sur Mistral Small 4 du 23/11 (7 560 appels, ≈ 4,2 $) donne CA7, CA8 et CA8a en échec.
  Ne pas activer `COMPAGNON_MOTEUR=capacites` en production avant la porte G2.
- Migration **v81** : jouée sur `potager_test` seulement (colonne présente aussi sur `potager_dev`, non jouée par nous).
  À jouer sur dev et prod AVANT tout déploiement du code (le modèle déclare la colonne).
- 17 échecs de suite identiques à HEAD (458d566), 1 test de temps instable (us310).

## Résultat de la mesure (rapport.md)

| Critère | actuel (témoin rejoué) | boucle |
|---|---|---|
| Utile au premier tour (seuil 80 %) | 21 % | 43 % |
| Aboutit (seuil 85 %) | 16 % | 40 % |
| Intention gardée (100 %) | 98 % | 98 % |
| Rien d'inventé (100 %) | 90 % | 89 % |
| Écriture sûre (100 %) | 91 % | 94 % |
| Hors-sujet montré (0) | 49 | 182 |
| Jetons d'entrée par tour | 16 872 | 10 395 (-38 %) |
| Part servie par le cache | 80 % | 89 % |

Défauts de la boucle relevés : `que_faire_maintenant` / `que_semer_ce_mois` listent toutes les cultures quand le jardinier
répond « à toi de voir » (hors-sujet) ; propositions d'observation / perte non demandées (B07, B13, B23) ; valeurs non dites
(quantité 1, « 15 °C » sans source). CA8a (salades B01-F1) : 62-69 k jetons pour 51 211 au plus.

## Ce que la relecture a montré : la mesure elle-même est à corriger AVANT de la rejouer

Détail : `A_CORRIGER.md`. Les points qui changent les pourcentages :

1. **Le juge ne voit pas ce que les outils ont rendu** (`tools/jeu_evaluation/juge.py`, `transcrire`) : il note ✅ un « rien en
   stock » faux (actuel B16-F4).
2. **Le contrôle « rien d'inventé »** ne voit ni une affirmation d'absence fausse, ni une cause non sourcée, ni le signe ou
   la date rattachés à un chiffre (`tools/jeu_evaluation/controles.py`). La règle « aucun chiffre sans fiche, même dans un
   conseil signalé » est confirmée (Q1 B).
3. **Le jardinier simulé clique « Confirmer » sans carte en attente** et le dialogue s'arrête (7 cas sur 30) : « aboutit »
   mesure alors le simulateur, pas le compagnon (`tools/jeu_evaluation/utilisateur.py`).
4. **Attendus du jeu inadaptés** : formulations F6 (B03, B17, B19) jugées sur l'attendu générique du besoin ; B07 sans
   `outils_attendus` et attendu trop vague (`tests/corpus/jeu_evaluation_compagnon.json`).
5. **Juge indisponible (quota)** : verdicts manquants, « utile » 49 / 432 en boucle, « aboutit » 64 / 432 ; les taux du rapport
   sont calculés sans eux.
6. À vérifier : `consulter_donnees` rend `disponible: false` dans 56 appels sur 74 de la chaîne actuelle — défaut de production
   ou du montage de la mesure (`tools/jeu_evaluation/moteurs.py`) ? Et la chaîne actuelle transforme ce « pas su répondre » en
   « rien ».

Défauts du compagnon boucle relevés par le porteur : B23-F4 ne consulte pas la pépinière (`voir_pepiniere` jamais appelé) ;
B18-F3 ne lit pas la connaissance de la tomate et invente des causes.

## Relecture humaine : 17 cas sur 30 faits

- Verdicts dans `verdicts_humains.json` (le porteur a donné : utile, aboutit, une remarque ; l'agent de relecture a noté
  `controles_justes`, 16 justes / 14 faux, avec les réponses du porteur aux 5 questions métier de `QUESTIONS_METIER.md`).
- **Restent à relire (13)** : actuel B01-F8, B03-F1, B04-F7, B05-F1, B08-F2, B14-F1 (présenté, en attente de verdict),
  B14-F4, B15-F3, B15-F4, B19-F2, B22-F6 ; boucle B09-F4, B20-F4.
- Protocole : le porteur donne seulement Utile (oui/non), Aboutit (oui/non) et UNE ligne « ce que le compagnon aurait dû
  faire » ; il juge sur la TRACE du passage 3, pas sur ses essais dans l'application. Les contrôles du code sont jugés par
  l'agent, les questions de métier sont posées au porteur en A / B.
- À la fin : écrire `SYNTHESE.md` (accord juge / humain par moteur, désaccords, contrôles faux).
- Les fiches individuelles et les traces complètes restent dans `rapports_evaluation/US342_343_20261123/` (non versionné,
  8 Mo ; à conserver sur ce PC ou à copier ailleurs si le dépôt local est nettoyé).

## Marche à suivre à la reprise

1. ~~Finir la relecture des 13 cas, puis `SYNTHESE.md`.~~ Fait le 26/11/2026 : voir `SYNTHESE.md` (la section
   « Relecture humaine » ci-dessus décrit l'état au 24/11).
2. Corriger la **mesure** (points 1 à 4 ci-dessus), sans appel au modèle : le juge doit voir les résultats des outils, le
   jardinier simulé ne confirme que s'il y a une carte, attendus propres aux formulations F6, outils attendus sur B03 /
   B07 / B08 / B16 / B18 / B23, contrôle d'absence affirmée.
3. Relancer l'appréciation du JUGE sur les traces existantes (pas de nouveau tour du compagnon : 3 passages restent valables
   pour la boucle tant que le code n'a pas changé) — avec accord sur le volume, sur la clé `MISTRAL_API_KEY_MESURE`
   (dans `.env.dev`) et sous verrou d'éveil (veille du PC).
4. Seulement ensuite : corriger la boucle (capacités qui listent tout, propositions non demandées, valeurs non dites) côté
   capacités, sans règle propre à un cas, puis remesurer (accord sur le volume annoncé par `--dry-run`).
5. Le lot 3 (US-344 / US-345 : proposer_commande, proposer_correction, confirmation par la phrase) modifie `boucle.py` ;
   à enchaîner après la remesure.

Lancement de la mesure (rappel) :
`APP_ENV=test python tools/evaluer_compagnon.py --moteur actuel,boucle --potager-neuf 37 --utilisateur-neuf 48
--potager-rempli 38 --utilisateur-rempli 49 --accord <volume>` — sous verrou d'éveil, clé de mesure lue dans `.env.dev`.
Jamais sans accord explicite du porteur sur le volume.
