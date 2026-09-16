# 🎯 ÉPIC 8 — Confiance et personnalisation du calendrier cultural

> **Nom proposé pour le Milestone GitHub :** `ÉPIC 8 — Confiance et personnalisation du calendrier`
> ⚖️ *Numéro à valider : le persona PO définit déjà un « ÉPIC 5 — Cycle de vie du potager » alors que
> `EPIC_CALENDRIER_CULTURAL.md` se nomme aussi « ÉPIC 5 ». À dédoublonner avant d'ajouter celui-ci.*
> **Statut :** 📝 Cadré — aucune US implémentée
> **Cadrage arrêté au :** 15/09/2026
> **Volume :** 7 US, 34 points (hypothèse, à rechiffrer US par US à la reprise)
> **Origine :** conversation du 15/09/2026 — comparaison avec un outil du marché (calendrier à 36 décades,
> simulation thermique, pourcentage d'avancement), besoin exprimé : « un niveau de confiance comme clé de
> voûte du système ».
> **Branche de référence lue :** `epic-6-referentiel-connaissance-cultures`, HEAD `f08e8b0`, v3.63.0.

---

## 1. Le problème

L'épic 5 a doté l'application d'un référentiel (US-068), d'une filière de semis (US-069), d'une frise lue
du référentiel (US-176) et d'une projection recalée sur le réel (US-070). Elle sait donc **quand on peut
semer** et **quand on récoltera si on sème aujourd'hui**.

Elle ne sait pas encore répondre à la question que le jardinier pose *avant* d'agir : **« est-ce une bonne
idée de semer / planter ça, ici, ce week-end ? »** — et surtout, **à quel point on peut s'y fier**.
Aujourd'hui, la seule réponse possible est une fenêtre conseillée au mois, la même pour un potager en serre
et un potager en fond de vallée, aveugle à la gelée annoncée jeudi.

Trois manques précis, tous vérifiés dans le code :

| Manque | Fait établi (source) |
|---|---|
| Rien ne projette une récolte depuis une **plantation** | `calendrier_cultural.ETAPES = (levee, recolte, repiquage)` — `recolte` compte depuis le semis. Point ouvert d'US-068 (§ amendement, ligne 126) |
| La météo par potager s'arrête à **5 jours** | `utils/meteo.py::fetch_meteo` — `"forecast_days": 6` (US-075 / CA2) |
| La **sensibilité au gel** d'une culture n'est pas renseignée | `culture_config.rusticite_min_c` existe (US-161) mais est `null` partout (`wind_river_attributs.json` : 0 occurrence) |

## 2. La valeur métier

| Bénéfice | Aujourd'hui | Après l'épic |
|---|---|---|
| Décider de semer ou planter | Fenêtre générique au mois | Niveau de confiance 1 à 3 étoiles, avec ses motifs |
| Savoir *pourquoi* on peut s'y fier | Rien | Chaque étoile gagnée ou perdue est nommée |
| Anticiper la gelée | Rien (météo à 5 jours, non reliée au calendrier) | Gel annoncé sur 14 jours pris en compte |
| Plants achetés en jardinerie | Aucune projection de récolte | Récolte attendue depuis la plantation |
| Tenir compte de son abri | Rien | Serre, tunnel, voile déclarés sur la parcelle et pris en compte |
| Passer de la recommandation à l'action | Deux commandes séparées | « Enregistrer le semis » en un geste depuis la réponse |

## 3. Ce qui a été écarté, et pourquoi

⚖️ **Simulation thermique (degrés-jours ou degrés-heures) — écartée, palier 3 abandonné.**
Le référentiel ne porte aucune donnée thermique (zéro de végétation, optimum, cible de degrés-jours) et
aucune source sous licence compatible n'a été identifiée pour les 33 cultures couvertes. Sans ces données,
un modèle thermique produirait des durées inventées — contraire à l'arbitrage « honnêteté » de l'épic 5.
La confiance v1 est **déterministe et par règles** : chaque point du score vient d'une donnée lue.

⚖️ **Frise à 36 décades — écartée.** La frise partagée (`MonthStrip.jsx`) reste au mois ; le calcul de
confiance se fait à la date, pas au mois. Une granularité fine sur l'affichage sans donnée fine derrière
donnerait une fausse impression de précision.

⚖️ **Pourcentage d'avancement — écarté en v1.** Le « reste à courir » d'US-070 est une fourchette de jours ;
la convertir en pourcentage exigerait une durée certaine que le référentiel n'a pas.

## 4. Arbitrages produit actés le 15/09/2026

| Sujet | Décision | Motif |
|---|---|---|
| **Durée plantation → récolte** | Ajoutée au référentiel comme quatrième étape `plantation_recolte` | Sans elle, US-070 ne projette rien pour un plant acheté. `days_to_harvest` de la source compte déjà depuis la plantation pour les cultures élevées à l'abri (`SOURCE.md`) |
| **Nature du score** | Déterministe, par règles pondérées, **aucun appel LLM** pour le calculer | Reproductible, à zéro jeton, explicable règle par règle. Le LLM ne sert qu'à comprendre la question |
| **Forme du score** | 1 à 3 étoiles, jamais un pourcentage | Une précision à l'unité serait fausse. Trois niveaux suffisent à décider |
| **Absence de donnée** | Une règle sans donnée ne rapporte **aucun point et le dit** ; une culture sans référentiel n'a **pas de score** (tiret) | Une étoile obtenue par défaut serait une date inventée sous une autre forme |
| **Météo** | Prévisions à 14 jours sur la localisation du potager (Lot C livré : US-074/075) | 5 jours ne couvrent pas le délai de levée d'un semis |
| **Abri et paillage** | Attributs déclarés sur la **parcelle**, modulateurs de règles, jamais de simulation | Le jardinier sait s'il a une serre ; l'application n'a pas à le deviner |
| **Point d'entrée** | Le **bot** d'abord (« je peux semer des haricots ce week-end ? »), l'écran Plan ensuite | La question se pose au champ, avant d'agir |

## 5. Le modèle cible

```
Entrées (toutes existantes sauf ⚠)
  référentiel      fenêtres par zone (4 phases), durées (levée, récolte, repiquage, ⚠ plantation_recolte)
  culture_config   rusticite_min_c  (⚠ à renseigner pour les cultures du potager de production)
  potager          zone climatique (US-068), latitude/longitude (US-074)
  parcelle         est_pepiniere, exposition, type_sol, ⚠ abri, ⚠ paillage
  météo            ⚠ prévisions 14 jours sur (lat, lon), cache (lat, lon, jour)
  événements       semis (contexte), plantation, récolte — chaînage existant

            ▼
  Moteur de confiance (service déterministe, app/services)
    entrée : culture, action (semis pépinière | semis pleine terre | plantation), date, parcelle
    règles pondérées → score 0-100 → 1 à 3 étoiles + liste de motifs (gagnés / perdus / indéterminés)

            ▼
  Sorties
    bot        « Haricot · pleine terre · ★★☆ — dans la fenêtre, pas de gel annoncé, nuits fraîches »
               + boutons : enregistrer le semis · semer sous voile · attendre
    écran Plan  indicateur sur la tuile pour la semaine de la date de référence + fiche détaillée
```

## 6. La grille de règles v1 (résumé — détail dans US-178)

| Règle | Donnée lue | Points max | Sans donnée |
|---|---|---|---|
| R1 Fenêtre conseillée de la zone, pour la phase demandée | `fenetre_culturale` | 40 | Pas de score du tout (culture sans référentiel) |
| R2 Dernière gelée moyenne de la zone vs date, si la culture est gélive | `rusticite_min_c`, table déclarée par zone | 20 | 0 point, motif « sensibilité au gel inconnue » |
| R3 Gel annoncé sur 14 jours | prévisions Open-Meteo | 20 | 0 point, motif « météo indisponible », 3ᵉ étoile inaccessible |
| R4 Nuits fraîches (Tmin moyenne 7 j) | prévisions Open-Meteo | 10 | idem R3 |
| R5 Saison restante : récolte attendue avant la fin de la fenêtre de récolte | durées + fenêtre récolte | 10 | 0 point, motif « durée inconnue » |
| Modulateurs (US-181) | abri, paillage de la parcelle | — | Aucun effet |

Seuils : **≥ 75 → ★★★**, **45 à 74 → ★★**, **< 45 → ★**. 🧪 Pondérations et seuils sont une hypothèse de
départ, à éprouver sur les cultures réelles du potager de production avant livraison.

## 7. Les User Stories

| US | Titre | Points | Nature | Migration |
|---|---|---|---|---|
| US-177 | Ajouter la durée plantation → première récolte au référentiel | 3 | Donnée de référence | non (vocabulaire d'étape sans CHECK, `migration_v46` l. 50) |
| US-182 | Étendre la météo du potager à 14 jours de prévision, avec cache | 3 | Infrastructure | non |
| US-178 | Calculer un niveau de confiance pour semer ou planter une culture à une date | 8 | Moteur | non |
| US-179 | Répondre au bot à « je peux semer / planter X ? » avec la confiance et ses motifs | 5 | Bot | non |
| US-180 | Afficher la confiance de la semaine sur les tuiles de l'écran Plan | 5 | PWA | non |
| US-181 | Déclarer l'abri et le paillage d'une parcelle et les faire peser sur la confiance | 2 | Saisie + moteur | **oui** |
| US-183 | Ouvrir la fiche calendrier d'une culture — semer ou planter, projection, confiance — depuis Stocks et Plan | 8 | PWA, conception préalable | non |

```
US-177 (durée plantation→récolte) ──┐
US-182 (météo 14 j) ─────────────────┼──→ US-178 (moteur) ──┬──→ US-179 (bot)
rusticité renseignée (tâche, pas US) ┘                       ├──→ US-180 (Plan)
                                                              ├──→ US-183 (fiche culture) ← maquette gelée (Claude Design)
                                                              └──→ US-181 (abri, paillage) ──→ US-178 v1.1
```

**Chemin critique :** US-178 → US-179. US-177 et US-182 sont petites et indépendantes, à livrer d'abord.
US-180 et US-181 sont parallélisables une fois le moteur livré. US-183 attend sa maquette gelée (brief
`BRIEF_FICHE_CALENDRIER_CULTURE.md`, projet Claude Design « potager 2026 ») — la conception démarre dès J1.

## 8. Séquencement

| Jalon | Contenu | Ce que le jardinier gagne |
|---|---|---|
| **J1** | US-177 + US-182 + renseignement de `rusticite_min_c` au bot pour les cultures du potager de production | Récolte projetée pour les plants achetés ; météo à 14 jours |
| **J2** | US-178 + US-179 | « Je peux semer ? » reçoit une réponse étoilée et motivée, avec l'enregistrement en un geste |
| **J3** | US-180 | La même confiance sur l'écran Plan, pour la semaine consultée |
| **J3 bis** | US-183 | La fiche complète d'une culture, depuis Stocks et Plan : semer ou planter, où en est ce qui est en terre, quand récolter |
| **J4** | US-181 | Serre, tunnel et voile déclarés pèsent sur le score |

## 9. Impact tokens

| Étape | Coût | Fait / hypothèse |
|---|---|---|
| Calcul du score | **0 jeton** — service déterministe | ✅ par construction |
| Compréhension de « je peux semer des haricots samedi ? » | 0 jeton si la grammaire déterministe de `interpreteur_commandes` reconnaît la question ; sinon 1 appel au routeur de questions existant (US-170), au tier déjà en place | 🔶 à mesurer sur le corpus `us172_commandes.csv` étendu (US-179 / CA8) |
| Formulation de la réponse | 0 jeton — gabarit texte | ✅ par construction |
| Météo | 1 appel Open-Meteo par `(lat, lon, jour)`, mis en cache ; gratuit | ✅ US-182 |

Aucun nouvel appel LLM n'est introduit par l'épic. C'est une condition de la Definition of Done.

## 10. Risques

| Risque | Niveau | Traitement |
|---|---|---|
| **Score jugé arbitraire** par le jardinier | 🟡 Moyen | Chaque point est motivé en clair (US-178 / CA6) ; les pondérations vivent à un seul endroit et sont documentées |
| **`rusticite_min_c` non renseignée** → règle R2 muette pour toutes les cultures | 🟡 Moyen | Tâche de J1 : renseigner au bot les cultures du potager de production ; la rédaction interne (`attributs_redaction_interne.json`) porte déjà le champ. Aucune valeur n'est inventée par l'épic |
| **Table « dernière gelée moyenne par zone »** est une décision, pas une mesure | 🟡 Moyen | Déclarée comme `ZONE_USDA_PAR_ZONE` l'est déjà : quatre valeurs, un seul endroit, « à valider par un humain », corrigeable |
| **Potager sans localisation** → R3/R4 muettes, 3ᵉ étoile inaccessible | 🟢 Faible | Comportement voulu et affiché ; l'invitation à localiser existe déjà (US-076) |
| **US-070 / US-176 non poussées** sur la branche de référence | 🔶 À lever | Cet épic suppose leur livraison telle que spécifiée. À confirmer par un push avant de démarrer US-178 |
| **Question mal reconnue** au bot → appel LLM inutile | 🟢 Faible | Corpus de mesure étendu (US-179 / CA8), même méthode qu'US-172 |

## 11. Definition of Done de l'épic

- [ ] Les six US sont livrées, leurs CA cochés et leurs tests passants.
- [ ] Pour chaque culture du potager de production, « je peux semer / planter X ce week-end ? » reçoit un
      score ou un tiret motivé — jamais une erreur, jamais une étoile obtenue sans donnée.
- [ ] Aucun appel LLM supplémentaire mesuré par `tools/audit_appels_llm.py` sur le parcours
      question → réponse → enregistrement, hors repli vers le routeur existant.
- [ ] Une plantation de plant acheté affiche une récolte attendue (US-177 + US-070).
- [ ] Un potager sans localisation reçoit un score plafonné à deux étoiles avec le motif visible.
- [ ] Les fiches d'aide du corpus « fonctionnement de l'application » concernées sont relues (US-099 / CA9).
- [ ] `ANALYSE_REFONTE_UI_WEB_2026.md` §7 est corrigé : Lot C livré (US-074/075/076), pas « à cadrer ».

## 12. À faire au démarrage

- Trancher le numéro d'épic (collision « ÉPIC 5 ») et l'ajouter à `Personna PO.agent.md`.
- Pousser US-070 et US-176 sur la branche de référence.
- Renseigner `rusticite_min_c` au bot (`/culture rusticite <culture> <valeur>`) pour les cultures du potager
  de production — travail de saisie, pas de développement.
- Déclarer la table « dernière gelée moyenne par zone » (quatre valeurs), à valider par un humain.
- Positionner les sept US en `To Do` (`python tools/jira_tracker.py create-issue backlog/US-1xx_*.md`).
- Conception dans le projet Claude Design **« potager 2026 »** (celui de la maquette figée du 15/08) : la fiche
  d'US-183 et le bloc « règle de confiance » partagé avec US-180, à partir de `BRIEF_FICHE_CALENDRIER_CULTURE.md`.
  Gel de la maquette avant tout code, même règle qu'US-073.
- Remplacer la copie d'`ANALYSE_REFONTE_UI_WEB_2026.md` du projet Claude par la version du dépôt (Lot C livré,
  Lot E absorbé par Stocks) — deux raisonnements de cette conversation ont buté sur la copie périmée.
