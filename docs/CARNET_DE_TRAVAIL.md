# Carnet de travail

Avancement, actions ouvertes et pense-bêtes, **par US**. La règle de tenue est dans `CLAUDE.md`, section
« Carnet de travail ».

Marques : `[ ]` à faire · `[~]` en cours · `[x]` fait · `[?]` à vérifier ou à décider · 💡 pense-bête, plus tard.

Dernière mise à jour : **28/11/2026**.

---

## EPIC 20 — Compagnon client des capacités

### Chemin jusqu'à la suite de l'implémentation

1. [x] Relecture humaine de la porte G2 (US-342 / US-343), synthèse écrite (28/11)
2. [ ] Classer chaque échec par cause : capacité manquante, attendu faux, juge sévère, erreur du modèle
3. [ ] Corriger, puis remesurer (volume annoncé, accord avant tout lancement)
4. [ ] **Porte G2 franchie** : utile ≥ 80 %, aboutit ≥ 85 %
5. [ ] Lot 3 : US-344 (écritures et cartes), puis US-345 (corrections, rappels, carnet) → porte G3
6. [ ] US-346 (Telegram, voix, spontanés) → G4 ; US-347 (retrait de l'ancien moteur) → G5

En parallèle, sans bloquer : US-348 (fiches agronomiques), US-349 (référentiel), US-350 (passerelle).

### US-342 / US-343 — Boucle à capacités et fil complet

Branche `refonte-architecture-agent`, `COMPAGNON_MOTEUR=capacites`, pas en production. Commits poussés (vérifié le 27/11).

**Porte G2, mesure du 27/11** (432 dialogues, Mistral Small 4, juge Large 3) : **KO**

| Critère | Seuil | Résultat |
|---|---|---|
| Utile au 1er tour (juge) | ≥ 80 % | 50 % |
| Aboutit en 3 tours (juge) | ≥ 85 % | 48 % |
| Intention gardée / rien d'inventé / écriture sûre (code) | 100 % | 2 échecs / 97 % / 94 % |
| Hors-sujet montré | 0 | 116 |
| Latence p95 | ≤ 4 s | 2,7 s ✅ |

Résultats et fiches : `rapports_evaluation/US342_G2_20261127/` (**non versionné, sur ce PC seulement**).

**Relecture humaine G2 : 16 / 16 dialogues jugés** (28/11)

- oui, oui : B04-F7, B05-F2, B05-F4, B12-F2, B12-F3, B15-F7, B17-F5, B23-F1, B23-F4, B23-F5, B24-F4
- non, non : B13-F1, B03-F4, B05-F6, B08-F4, B16-F2
- [x] 18 cas B25 / B26 / B27 relus : **justes** (28/11) ; B26 : l'attendu exige en plus la cause de la perte (« limaces »),
  contrôlée par le juge seulement — **commité, non joué**
- [x] Synthèse, verdicts et points à corriger dans `docs/EPIC 20 - …/MESURE_27_11_US342_343/` — commité (28/11), non poussé

**Fait**

- [x] Geste dicté sans quantité inventée (`27f9ed6`) ; parcelle dite reconnue (`599a274`)
- [x] Décision sur météo et carnet, sources d'abord, pas de carte fantôme (`9097b51`)
- [x] « je ne sais pas » ne prépare aucune carte (`9d796b5`)
- [~] Cas « même culture sur deux parcelles » B25 / B26, potager de test 41 / utilisateur 52 — **commité, non joué**
  (342 appels ≈ 0,29 $)

**Défauts relevés à corriger** (compagnon)

- [ ] **PRIORITAIRE — le compagnon ne reçoit que 6 000 caractères** d'un résultat d'outil (`compagnon/fil.py`, CA4 d'US-343).
  Pépinière : 16 304, il ne voit que le lot 3 et le début du lot 1 ; lots 9, 8, 7, 2 jamais vus (mesuré le 27/11).
  G2 : 66 dialogues sur 432 concernés (que_faire_maintenant 28/40, voir_plan 25/77, voir_pepiniere 22/28, consulter_carnet 3/69, voir_meteo 1/102)
- [x] Verdicts B23-F1 et F4 maintenus oui / oui par le porteur, coupure connue (28/11)
- [ ] La liste des choix rendue par l'application est retirée de la question (B04-F7) : l'afficher
- [ ] « demande au jardinier quand il a arrosé » ignoré ; affirmation sans lecture non relevée par le code (B08-F4)
- [ ] Dit pouvoir « compléter la fiche » sans en avoir le moyen (B05-F6)
- [ ] Une réponse « je ne sais pas, mais note quand même » est refusée à tort (garde du 27/11)
- [ ] B23-F4, tours 3 et 4 : « Je te montre la carte ? » répété, aucune carte préparée (verdict porteur : oui / oui)
- [?] Deux cartes au même tour : la seconde remplacerait la première (lecture du code, **non testé**)
- [?] Une carte acceptée d'un « oui » peut porter ce que le compagnon a avancé (« levée constatée » seulement attendue)

**Relecture de B16-F2 (porteur, 27/11)** — verdict reporté : non / non ; B16 inchangé (comparaison préservée)

- [ ] Fiche fausse : l'application ne gère **pas** de réserve de graines (conservées, non semées)
- [ ] `voir_stock` se décrit comme « stock de graines et de plants » ; le compagnon a présenté des graines **semées**
  comme des graines restantes (haricot 50, radis 8). Ni le code (« rien d'inventé ✅ ») ni le juge ne l'ont relevé
- [x] Nouveau besoin **B27** « semis ou repiqués » (6 formulations, potager rempli) — tests 196 ✅, **commité, non joué**
- [x] B27 relu : juste (28/11)
- [?] Les lectures actuelles disent-elles la levée et le repiquage en pleine terre ? **non vérifié**
- [?] Attendu de B16-F3 : dire qu'il n'y a pas de réserve de graines (proposé, non appliqué) ; « stock graines ». B16-F1, F4, F5 portent sur le stock en général

- [x] Carnet lu sur **6 mois** par défaut au lieu de 12 (porteur, B17-F5) ; maximum inchangé à 12 — commité (28/11), non poussé ;
  vaut aussi pour les assistants connectés (MCP)

**Constats du porteur sur la pépinière (27/11)**

- Seuls les lots **3** et **9** restent ouverts avec quelque chose à repiquer ; 1 et 2 clôturés, 7 et 8 sans graines
- [ ] Garde-fou voulu : aucun semis ni plantation sans quantité. Telegram (US-021) et compagnon la demandent ; le service
  (`valider_evenement`) ne l'impose qu'à plantation, vente, perte de godets — **pas au semis**. Autres portes non vérifiées
- [ ] Anomalie lue dans les données : lot 2 **clôturé** mais « repiquage en retard de 211 j » ; lot 7 sans graines, « en retard de 190 j »

**Défauts du jeu et de la mesure**

- [ ] **Le juge ne lit que les 1 500 premiers caractères** de chaque résultat d'outil : 265 dialogues sur 432 en ont un
  plus long. B23-F1 : « Courgette (lot 1) inventée » est **faux**, le lot existe. Effet sur 50 % / 48 % **non mesuré** ;
  à corriger puis rejuger les traces (coût à annoncer)
- [ ] Les traces gardent 4 000 caractères au plus : le relecteur ne peut pas tout vérifier (données des potagers de test :
  `relecture/DONNEES_POTAGERS.md`)
- [ ] B05-F6 : attendu du radis appliqué au cerfeuil tubéreux
- [ ] B13 : joué sur le potager neuf, sans haricot en place
- [?] B05-F2 : « sous abri en février » absent de ce que voir_calendrier rend — calendrier ou attendu faux ?
- [x] « Sans parcelle » (porteur, 28/11) : deux cultures identiques non localisées ne se distinguent pas (stock groupé par
  culture et variété). B25 / B26 inchangés, sans « Sans parcelle » (confirmé)
- [ ] Lu dans le code, non testé : `parcelles_avec_culture` ignore les cultures sans parcelle ; avec une plantation sur une
  parcelle et une autre non localisée, Telegram affecte la parcelle **d'office**. À intégrer au lot A (écarts Telegram / PWA)
- [?] Juge sévère (ex. B15-F7 refusé par le juge, accepté par le porteur)
- [ ] Le lanceur marque ✅ des passages en erreur de connexion ; en-tête « rempli 33 » faux

**Arbitrages en attente (porteur)**

- [?] Culture inconnue : réponse issue d'une recherche web (géolocalisation, période, région) ? Aucune capacité
  n'existe ; à concilier avec « les sources d'abord, jamais d'invention »

### Écarts Telegram / PWA sur les gestes — US à créer

Inventaire : `docs/EPIC 20 - COMPAGNON CLIENT DES CAPACITES/ECARTS_GESTES_TELEGRAM_PWA.md` (14 écarts).
**Ne suffit pas à franchir G2** ; justifié par l'exactitude du carnet. À mener à part.

- [?] Feu vert du porteur et cadrage de l'US
- [ ] Lot A — parcelle (choix proposés ; « aucune trace de X sur Y »)
- [ ] Lot B — variété, « au potager ou en pépinière ? », nombre de pieds
- [ ] Lot C — fin de culture
- [ ] Lot D — pépinière (godet : variété, lot, graines ; contexte de semis ; lot d'origine)
- 💡 Plus tard : vente, levée, déplacement, parcelle à créer, culture non dite

---

## Pense-bêtes (plus tard)

- 💡 Essayer un modèle plus fort sur quelques besoins, **après** le classement des causes
- 💡 Quantité déduite de la longueur des rangs (attente du porteur, relecture du 23/11)
- 💡 « Que faire ? » : ajouter semis, levées, récoltes prévues, données manquantes
- 💡 Au déploiement : réingérer le corpus (fiche « enregistrer un geste » modifiée)
- 💡 Avant livraison : `VERSION` et `PATCH_NOTES.md` pour les correctifs US-342
