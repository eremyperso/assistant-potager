# 🎯 ÉPICS 9 à 12 — Refonte des écrans Plan, Cultures et Pépinière

> **Noms proposés pour les Milestones :**
> `ÉPIC 9 — Socle commun Plan, Cultures, Pépinière` ·
> `ÉPIC 10 — Plan : l'occupation en rangs` ·
> `ÉPIC 11 — Cultures : tout savoir d'une culture` ·
> `ÉPIC 12 — Pépinière : le poste de travail sous abri`
> ⚖️ *Numéros à valider, même réserve que l'ÉPIC 8 : le persona PO ne liste encore que les épics 1 à 6.*
> **Statut :** 📝 Cadré — aucune US implémentée
> **Cadrage arrêté au :** 19/09/2026
> **Volume :** 28 US (US-194 à US-221), 117 points (hypothèse, à rechiffrer US par US, hors conception des maquettes)
> **Sources :** trois wireframes produits avec Claude Design, dossier `maquette front/wireframes/`
> (⚠️ non tracké à ce jour : à committer pour que les références des US restent valides)
> **Branche de référence lue :** `epic-8-confiance-personnalisation-calendrier`, HEAD `6cbaf69`, v3.72.0

---

## 1. Les trois wireframes, et ce que chacun fait foi

Les trois fichiers sont trois étapes d'une même analyse. Le plus récent l'emporte **sur le sujet qu'il
traite**, pas au-delà.

| Fichier | Date | Ce qu'il décide | Ce qui en reste |
|---|---|---|---|
| `Wireframes - Plan Cultures Pepiniere.html` (v1) | 18/09 | Règle de répartition des trois écrans. Plan en treemap. Écran **Cultures** (grille de cartes, fiche culture). Pépinière **calendrier** (gantt par culture, panneau de lot, « Où les mettre ») | Répartition, **Cultures** et **calendrier de pépinière** font foi. La treemap est remplacée par la v3 |
| `Wireframes v2 - Plan Cultures Pepiniere.html` (v2) | 19/09 | Enchaînement Cultures → fiche calendrier d'US-183. Plan **géométrique** (longueur × largeur, espacements). Pépinière **poste de travail** : onglets Aujourd'hui · Lots · Calendrier · Emplacements, écran de terrain, étiquettes à QR code | Enchaînement et **Pépinière** font foi. Le Plan géométrique est **reporté** par la v3 |
| `Wireframes v3 - Plan simplifie.html` (v3) | 19/09 | **Vue plan V1** : une carte par parcelle, un trait par rang, trois formes, dix-sept règles de rendu et d'interaction | Fait foi pour la **Vue plan** |

## 2. La règle de répartition (v1, conservée)

| Écran | Répond à | Ne montre pas |
|---|---|---|
| **Plan** | Où est quoi, quelle place reste | Calendrier, confiance, famille (sur la Vue plan) |
| **Cultures** | Tout ce que l'application sait d'une culture, et quoi faire maintenant | Les quantités en stock |
| **Pépinière** | Ce qui se passe sous abri : quoi faire aujourd'hui, où c'est posé, ce qui sera prêt quand, ce qui traîne | L'occupation des planches |
| **Stocks** (inchangé) | Combien | — |

## 3. Le parcours : comment les écrans se renvoient

Chaque sortie est un lien réel. Les **fiches** (culture, calendrier, lot) sont des panneaux ouverts
par-dessus l'écran, jamais des navigations : les fermer rend l'écran d'origine dans son état exact.

| Depuis | Appui sur | Ouvre | US |
|---|---|---|---|
| Plan · Vue plan | un rang occupé | la **fiche culture** (panneau) | US-201 |
| Plan · Vue plan | un rang libre | « ajouter une culture » : geste pré-rempli, parcelle connue | US-201, US-196 |
| Plan · Vue plan | « Fiche parcelle → » | l'onglet **Parcelles**, parcelle sélectionnée | US-201, US-195 |
| Plan · Vue plan | la carte d'une pépinière | **Pépinière**, sur cet emplacement | US-201, US-195 |
| Plan · Vue plan | « Journal du jour » | **Journal**, filtré sur la date de référence | US-201, US-195 |
| Plan · Parcelles | « Voir la culture » sur une tuile | la **fiche culture** | US-201 |
| Cultures | une carte | la **fiche culture** | US-205, US-207 |
| Fiche culture | « Ouvrir la fiche calendrier » | la fiche calendrier d'US-183, par-dessus | US-207 |
| Fiche calendrier | « Enregistrer le semis / la plantation » | geste pré-rempli, confirmé au compagnon | US-196 |
| Pépinière | un lot | la **fiche du lot** (panneau, plein écran à 375 px) | US-216 |
| Fiche du lot | Repiquer · Noter la levée · Mettre en terre · Déplacer · Perte · Clôturer | geste pré-rempli, lot connu | US-216, US-196 |
| Fiche du lot | « Mettre en terre ici » (Où les mettre) | geste de plantation pré-rempli, parcelle connue | US-217, US-196 |
| Pépinière | le nom d'une culture | la **fiche culture** | US-215, US-218 |
| Étiquette de lot (option) | scan du QR code | la fiche du lot | US-221 |

## 4. Règles transverses — elles valent pour toutes les US des quatre épics

| # | Règle | Origine |
|---|---|---|
| **RT1** | **Les écrans lisent, ils n'écrivent pas.** Un bouton d'action prépare un geste pré-rempli et le fait confirmer au compagnon Telegram, par le flux de confirmation existant. Aucun nouveau chemin d'écriture. Seule exception : l'ordre des parcelles (US-202), réglage de mise en page | v2 « BACKOFFICE », v3 règle 13, US-183 / CA6 |
| **RT2** | **Rien n'est inventé.** Une donnée absente est dite (« nombre de rangs non renseigné », « délai non renseigné »), jamais estimée, moyennée ni complétée par un modèle | v3 règle 9, arbitrage « honnêteté » de l'épic 5 |
| **RT3** | **Date de référence** affichée en haut de chaque écran ; tout ce qui s'affiche est l'état à cette date, jamais une projection présentée comme un fait | v3 règle 15, US-030 / US-031 |
| **RT4** | **Couleur = phase, forme = mode d'implantation.** Deux variables visuelles indépendantes, jamais une troisième palette. La phase est aussi écrite en mot : l'écran reste lisible en niveaux de gris | v2, v3 règles 4, 5, 16 |
| **RT5** | **Responsive** : breakpoints Tailwind pour la page, container queries pour tout composant. Cibles d'appui de 44 px minimum à 375 px, 48 px sur l'écran de terrain de la pépinière | `frontend/CLAUDE.md`, v3 règle 11, v2 3c |
| **RT6** | **Budget de lectures** : une lecture groupée par écran, jamais une requête par carte, par rang ou par lot | US-176 / CA11, US-180 / CA6 |
| **RT7** | **Une règle métier vit à un seul endroit, côté serveur.** Le front ne fait que de la mise en forme, isolée dans `frontend/src/lib/*.js` et couverte par `npm test` | pratique d'US-060, US-061, US-176 |
| **RT8** | **Définition de terminé** : fiches `data/connaissance/doc_app/` corrigées dans la même livraison (US-099 / CA9) ; fiche de domaine `docs/domaines/` créée ou complétée et référencée dans sa table | `CLAUDE.md` |
| **RT9** | **Maquette haute fidélité gelée avant le code** de toute US d'écran (projet Claude Design « potager 2026 »), après tranchage des arbitrages du § 6 | précédent d'US-183 ; v2 § 4 « Ce qui bloque la haute fidélité » |
| **RT10** | **Bot** : toute commande ou tout geste ajouté est tranché au catalogue (`menu_commandes`, `controler_parite`), dictable sans appel au modèle quand c'est possible, et cohérent avec `/help` et le corpus | US-171, US-172 |
| **RT11** | **Droits** : un membre en lecture seule ne voit aucune action d'écriture ; propriétaire et éditeur les voient | US-047 |

## 5. Écarts constatés entre les wireframes et le modèle réel

Les wireframes affirment à plusieurs endroits que « rien de nouveau n'est en base » ou que « tout existe
déjà ». Vérification faite, voici ce qui n'existe pas — et l'US qui le crée.

| Le wireframe suppose | Le code et la documentation disent | Conséquence |
|---|---|---|
| Un **nombre de rangs** par parcelle (v3 : « existe déjà ») | Aucune colonne. `/parcelle modifier` ne connaît que `exposition`, `superficie`, `ordre`, `pepiniere` | US-197 (migration) |
| Le **rang** d'un événement est une position (« Rang 1 : tomate ») | `rang` est un **multiplicateur** : « planté 4 salades sur 3 rangs » enregistre 12 plants (guide § 6.5, `stock-plants-calcul.md`) | Numérotation V1 dans l'ordre d'installation (US-198) ; position à la saisie en option (US-203) |
| Unités « poquets » et « ml » déjà présentes (v2) | En production : `plants`, `g`, `graines`, `kg`, plus `m2` à la dictée (US-168) | US-199 |
| Un **mode d'implantation** (v3 : « champ à valeur par défaut ») | N'existe pas | Déduit de l'unité en V1, sans colonne (US-198) |
| Le « flux d'enregistrement existant » des boutons (v2, US-183 / CA6) | La PWA n'en a pas : `FicheCalendrier` ne rend son bouton que si l'appelant fournit `onEnregistrer`, et aucun écran ne le fournit (`docs/domaines/calendrier-cultural.md`) | US-196 |
| « Noter la levée », « 48 semés → 40 levés » | Aucun geste de levée : la germination se déduit des mises en godet (US-065) | US-212 |
| « Repiquage attendu à 12 j » | La durée `repiquage` du référentiel est le délai **semis → mise en place** (« délai avant plantation »), pas semis → godet | US-213 |
| Les godets sont posés dans une pépinière (v2 3b) | `mise_en_godet` est créée avec `parcelle_id = NULL` en dur (analyse du 17/07) | US-210 |
| Un numéro de lot court « #128 » | Un lot n'est identifié que par l'identifiant technique de son semis | US-209 |
| « La V1 ne sait pas calculer un pourcentage de surface » (v3) | `occupation_pct` existe, calculé depuis l'empreinte au pied (`culture_config.surface_m2`) | Il reste sur l'onglet Parcelles ; la Vue plan lit des rangs (arbitrage A3) |
| « Parcelle sous abri » = carte hachurée sans rangs (v3 règle 8) | L'**abri** (US-181, non livrée) et la **pépinière** (`est_pepiniere`) sont deux attributs distincts ; une serre de production porte des rangs | La carte hachurée est celle d'une **parcelle pépinière** (US-200) |
| Règles « Sol » et « Pluie 48 h » dans la fiche calendrier (v2 § 1b) | Le moteur d'US-178 a cinq règles : fenêtre, dernière gelée, gel sur quinze jours, nuits douces, saison restante | La fiche livrée par US-183 fait foi ; rien à développer |
| Pépinière chaude ou froide (demande du 19/09) | `est_pepiniere` est un booléen. « Un semis en pépinière tient R2, R3 et R4 pour acquises : la pépinière non chauffée de février attend l'abri d'US-181 » | US-208, US-220 |

## 6. Arbitrages proposés — à confirmer avant la haute fidélité

Chaque « à trancher » des wireframes reçoit une décision par défaut, portée par l'US concernée. Aucune
n'est irréversible : les changer, c'est amender l'US avant son démarrage.

| # | Question (source) | Décision proposée | Motif | US |
|---|---|---|---|---|
| **A1** | Deux colonnes de cartes en desktop, ou une seule ? (v3 § 4.1) | **Deux colonnes** à partir de 720 px de conteneur, une en dessous, jamais trois | Au-delà de deux, les traits deviennent trop courts pour se comparer | US-200 |
| **A2** | Plancher de 12 % sur les traits courts ? (v3 § 4.2) | **Conservé**, la quantité étant toujours écrite à côté du trait | Un trait invisible n'est plus cliquable ; le chiffre écrit empêche la fausse lecture | US-200 |
| **A3** | « 13 rangs sur 18 » suffit-il ? (v3 § 4.3) | **Oui** sur la Vue plan : « N rangs sur M » par carte, total en pied. Le pourcentage de surface reste sur l'onglet Parcelles | Deux mesures d'occupation côte à côte se contrediraient à l'œil | US-200 |
| **A4** | Mode d'implantation saisi ou déduit ? (v3 § 4.4) | **Déduit de l'unité** : `m2` → surface, `poquets` → poquet, sinon rang | La v3 le dit : l'unité suffit dans la quasi-totalité des cas ; aucune colonne | US-198 |
| **A5** | Numéro affiché « Rang N » alors que la base ne connaît pas la position | Rangs numérotés **dans l'ordre d'installation**, ce que la carte dit une fois. La position réelle devient possible par US-203 (option) | Numéroter comme une position ce qui n'en est pas une serait une donnée inventée | US-198, US-203 |
| **A6** | Parcelle sans nombre de rangs (v3 : « sans dessin ») | Ses cultures restent **dessinées** (un rang chacune), sans rang libre, avec la mention du champ manquant. Seule une parcelle sans rangs **et** sans culture reste en pointillé, sans dessin | Au premier jour, aucune parcelle n'a de nombre de rangs : « sans dessin » viderait tout le Plan et masquerait des cultures, ce que la v3 interdit ailleurs | US-200 |
| **A7** | Tuile de l'onglet Parcelles : la v1 lui retire frise et confiance, la v2 la garde comme entrée de la fiche calendrier | **v2 retenue** : tuile inchangée (US-180, US-183 venant d'être livrées), plus un lien « Voir la culture ». La simplification de la v1 reste à décider | Pas de régression d'une livraison de la veille ; la décision se reprend quand l'écran Cultures sera en service | US-201 |
| **A8** | Bouton « Enregistrer » hors fenêtre : actif ou masqué ? (v2 § 4.4) | **Actif** | La confiance conseille, elle n'interdit pas | US-196 |
| **A9** | Récolte attendue dépassée de 44 jours : mention seule ou clôture ? (v2 § 4.5) | **Mention seule**, comme aujourd'hui | Aucun geste d'arrachage n'existe (`US_Enregistrer_arrachage_fin_culture` non livrée) | — |
| **A10** | La maquette haute fidélité d'US-183 couvre-t-elle ces états ? (v2 § 4.6) | **Oui** : la page `/fiche-calendrier` rejoue les quatre états (US-183 / CA18) | — | — |
| **A11** | Endurcissement : stade du modèle ou compte à rebours ? (v2 § 4.7) | **Compte à rebours** de sept jours avant la mise en terre prévue, **pour les lots en pépinière chaude ou de type inconnu**. Un lot en pépinière froide s'endurcit sur place | Aucun coût de modèle ; le type de pépinière donne enfin un sens au compte à rebours | US-214 |
| **A12** | La « plaque » : notion réelle ou l'emplacement s'arrête à la pépinière ? (v2 § 4.8) | **L'emplacement s'arrête à la parcelle pépinière** | La plaque n'existe nulle part ; elle se décidera sur usage | US-210, US-219 |
| **A13** | QR code ou numéro de lot manuscrit ? (v2 § 4.9) | **Numéro de lot d'abord** (US-209), étiquettes à QR code en **option** ensuite (US-221) | « Zéro impression, 80 % du bénéfice » (v2) | US-209, US-221 |
| **A14** | Ce que porte une étiquette imprimée | **Identité du lot et rappel de date seulement** : ni quantité, ni emplacement, qui changent | « Le lot bouge, l'étiquette ment » (v2) ; l'exemple dessiné portait l'emplacement, la règle écrite l'exclut | US-221 |
| **A15** | Ce que fait « Journal du jour » (v1, v3 : aucun comportement décrit) | Ouvre le **Journal filtré sur la date de référence** | Seule lecture compatible avec « les écrans lisent » ; si l'intention était « noter mes gestes du jour », le bouton ouvrirait le compagnon sans geste pré-rempli | US-201 |
| **A16** | Où écrire, puisque la PWA n'a pas de flux d'enregistrement | **Geste pré-rempli confirmé au compagnon Telegram** par lien profond, sur le mécanisme de liaison existant | Respecte « aucun nouveau chemin d'écriture » et réutilise la confirmation, la rotation, la demande de parcelle du bot. L'alternative — un formulaire web branché sur le même service — est hors périmètre | US-196 |
| **A17** | Pépinière chaude ou froide : que change le type ? | Trois choses : le compte à rebours d'endurcissement (A11), l'onglet Emplacements, et la confiance d'un semis en pépinière (une pépinière froide ne tient plus nuits fraîches et dernière gelée pour acquises) | C'est exactement le manque noté par US-178 : « la pépinière non chauffée de février » | US-208, US-214, US-219, US-220 |

## 7. Découpage

### ÉPIC 9 — Socle commun Plan, Cultures, Pépinière (14 points)

| US | Titre | Pts | Dépend de |
|---|---|---|---|
| US-194 | Calculer la phase du moment d'une culture en place | 3 | US-070, US-177 (livrées) |
| US-195 | Ouvrir un écran depuis un autre avec son contexte | 3 | US-053 (livrée) |
| US-196 | Préparer un geste dans la PWA et le faire confirmer au compagnon Telegram | 8 | US-045, US-091, US-179, US-183 (livrées) |

### ÉPIC 10 — Plan : l'occupation en rangs (29 points)

| US | Titre | Pts | Dépend de |
|---|---|---|---|
| US-197 | Déclarer le nombre de rangs d'une parcelle | 3 | — |
| US-198 | Répartir les cultures en place sur les rangs de leur parcelle | 5 | US-194, US-197 |
| US-199 | Reconnaître le poquet et le mètre de rang comme unités d'implantation | 2 | US-168 (livrée) |
| US-200 | Afficher la Vue plan : une carte par parcelle, un trait par rang | 8 | US-198, US-194 |
| US-201 | Relier la Vue plan et l'onglet Parcelles aux autres écrans | 3 | US-200, US-195, US-196, US-207 |
| US-202 | Réordonner les parcelles depuis la Vue plan | 3 | US-200 |
| US-203 | Préciser à la saisie le rang où l'on sème ou plante *(optionnelle)* | 5 | US-198 |

### ÉPIC 11 — Cultures : tout savoir d'une culture (18 points)

| US | Titre | Pts | Dépend de |
|---|---|---|---|
| US-204 | Lire en une fois ce qu'affiche l'écran Cultures | 5 | US-194 |
| US-205 | Afficher l'écran Cultures | 5 | US-204, US-207 |
| US-206 | Composer la fiche d'une culture pour la PWA | 3 | US-194 |
| US-207 | Ouvrir la fiche d'une culture et enchaîner vers sa fiche calendrier | 5 | US-206, US-195 |

### ÉPIC 12 — Pépinière : le poste de travail sous abri (56 points)

| US | Titre | Pts | Dépend de |
|---|---|---|---|
| US-208 | Déclarer une pépinière chaude ou froide | 3 | — |
| US-209 | Numéroter les lots de semis et les retrouver par leur numéro | 5 | — |
| US-210 | Rattacher les godets à leur pépinière et savoir où se trouve chaque lot | 3 | — (US-208 conseillée) |
| US-211 | Déplacer un lot d'une pépinière à l'autre | 3 | US-209, US-210 |
| US-212 | Noter la levée d'un lot | 5 | US-209 |
| US-213 | Ajouter au calendrier le délai entre semis et repiquage en godet | 3 | — |
| US-214 | Calculer les échéances d'un lot | 5 | US-208, US-210, US-213 |
| US-215 | Afficher l'onglet « Aujourd'hui » de la Pépinière | 5 | US-214, US-216, US-196 |
| US-216 | Ouvrir la fiche d'un lot et y faire ses gestes | 5 | US-214, US-196, US-209 |
| US-217 | Proposer où mettre en terre les plants d'un lot | 3 | US-198, US-216 |
| US-218 | Afficher l'onglet « Calendrier » de la Pépinière | 5 | US-214, US-215 |
| US-219 | Afficher l'onglet « Emplacements » de la Pépinière | 3 | US-208, US-210, US-215 (US-211 conseillée) |
| US-220 | Tenir compte du type de pépinière dans la confiance d'un semis | 3 | US-208 |
| US-221 | Imprimer des étiquettes de lot à QR code *(option)* | 5 | US-209, US-216, US-195 |

## 8. Ordre de livraison proposé

| Vague | Contenu | Pourquoi dans cet ordre |
|---|---|---|
| **A — Données** | US-194, US-197, US-199, US-206, US-208, US-209, US-213 | Aucun écran ; chacune est livrable seule et débloque les suivantes |
| **B — Socle et Plan** | US-195, US-198, US-200, US-207, US-196, US-201, US-202 | La Vue plan est la plus attendue ; la fiche culture et le geste pré-rempli en sont les sorties |
| **C — Cultures** | US-204, US-205 | Réutilise la fiche culture déjà livrée en B |
| **D — Pépinière** | US-210, US-211, US-212, US-214, US-216, US-215, US-217, US-218, US-219, US-220 | Les données du lot d'abord (emplacement, levée, échéances), l'écran ensuite |
| **Options** | US-203, US-221 | À déclencher sur usage |

## 9. Hors périmètre

- L'**onglet Rotation** du Plan, encore en construction. Les composants de la Vue plan acceptent une
  palette passée en paramètre pour qu'il les reprenne tels quels (v1, v3).
- Le **Plan géométrique** de la v2 — longueur × largeur, orientation des rangs, espacements sur le rang
  et entre rangs, emprise en m², débordement, échelle. **Reporté, pas abandonné** : la v2 reste le
  dossier de référence le jour où ces données existeront (v3 § 4).
- La **plaque** et l'alvéole de pépinière (A12).
- Une **saisie web directe** d'un geste (A16).
- Un geste d'**arrachage** ou de clôture d'une culture en terre (A9).
- Le suivi de **levée en pleine terre** : US-212 ne couvre que les lots de pépinière.
- Le **déplacement partiel** d'un lot (une partie des godets seulement).
- Les **étiquettes de parcelle** et de **bocal de graines** évoquées par la v2 § 3d.
- Les observations (US-039) sur la Vue plan : elles restent sur l'onglet Parcelles.

## 10. Ce qui reste à confirmer avec le PO

1. Les arbitrages A1 à A17 du § 6, en particulier **A6** (parcelle sans nombre de rangs), **A7** (tuile
   de l'onglet Parcelles) et **A16** (geste confirmé au compagnon plutôt qu'un formulaire web).
2. Le seuil du **lot dormant** (US-214 : 60 jours sans mouvement une fois la mise en terre prévue
   dépassée) et la durée d'**endurcissement** (7 jours) : décisions produit, corrigeables au même endroit.
3. Le remplissage du **délai semis → godet** (US-213) : la source ouverte ne le porte pas, le gabarit est
   livré vide. Qui renseigne les valeurs des cultures réellement semées en pépinière ?
4. Les **numéros d'épic** 9 à 12 et leur ajout au persona PO.
