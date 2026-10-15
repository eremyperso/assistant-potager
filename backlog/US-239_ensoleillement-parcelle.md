**ID :** US-239
**Titre :** Déclarer l'ensoleillement d'une parcelle, distinct de son orientation
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux dire si une parcelle est en plein soleil, à mi-ombre ou à l'ombre, en plus de son orientation
Afin que l'application puisse me dire quelles planches conviennent à une culture, au lieu de répondre « exposition non comparable »

**Contexte fonctionnel :**
US-217 compare l'exposition d'une parcelle à celle de la culture (US-161 : *plein soleil*, *mi-ombre*, *ombre*). Or la fiche parcelle (US-230) propose une **orientation** : *Sud*, *Est*, *Ouest*, *Nord*, *Mi-ombre*, en texte libre. Les deux vocabulaires ne se recoupent que sur « mi-ombre » : une culture de plein soleil n'a **jamais** de parcelle concordante, et « Où les mettre » rend « non comparable » pour presque toutes les planches.

Traduire l'orientation en ensoleillement (Sud → plein soleil) a été écarté le 15/10/2026 : une planche plein sud peut être à l'ombre d'un mur ou d'une haie, et ce serait une donnée supposée (RT2). L'orientation et l'ensoleillement sont **deux informations**, la parcelle porte les deux.

**Critères d'acceptance :**

*La donnée*
- [ ] CA1 : La parcelle gagne un **ensoleillement** facultatif, à vocabulaire fermé : *plein soleil*, *mi-ombre*, *ombre* — le même que l'exposition des cultures (US-161), mêmes règles de normalisation (casse, accents, « mi ombre » accepté). Une valeur hors vocabulaire est refusée avec la liste des valeurs admises
- [ ] CA1 bis : Chaque valeur est **définie en heures de soleil direct par jour**, et cette définition s'affiche partout où l'on choisit (PWA, réponse du bot, `/help`, corpus) : *plein soleil* = 6 h et plus, *mi-ombre* = de 3 à 6 h, *ombre* = moins de 3 h. C'est ce que reçoit la parcelle qu'on déclare, pas où elle regarde
- [ ] CA2 : L'**orientation** existante (`exposition`, texte libre) est conservée telle quelle ; aucune valeur n'est convertie ni déduite. Une parcelle existante a un ensoleillement **non renseigné**
- [ ] CA3 : Migration avec rollback

*La saisie*
- [ ] CA4 : Bot : « ensoleillement planche racines plein soleil » (et `/parcelle modifier … ensoleillement …`) renseigne la valeur, sans appel au modèle ; tranché au catalogue (`menu_commandes`, `controler_parite`) et cohérent avec `/help` (RT10)
- [ ] CA5 : PWA, fiche parcelle (US-230) : un champ **Ensoleillement** à liste fermée, à côté de l'orientation : trois choix, chacun avec sa définition en heures sous le libellé, plus « non renseigné » (le champ est facultatif) ; propriétaire et éditeur seulement (RT11)
- [ ] CA6 : La liste des parcelles (bot et PWA) affiche l'ensoleillement quand il est renseigné

*L'usage*
- [ ] CA7 : « Où les mettre » (US-217) compare l'**ensoleillement** de la parcelle à l'exposition de la fiche de la culture (US-161) ; l'orientation n'entre plus dans la comparaison. Le calcul reste à un seul endroit, côté serveur (`comparer_exposition`, RT7)
- [ ] CA7 bis : **La meilleure parcelle vient en premier.** L'écart se mesure en crans sur l'échelle *plein soleil* → *mi-ombre* → *ombre*, et l'ordre de CA3 d'US-217 devient : 1) concordante ; 2) écart d'un cran (« mi-ombre, pour une culture de plein soleil ») ; 3) écart de deux crans (« ombre, pour une culture de plein soleil ») ; 4) non comparable (ensoleillement ou exposition de la culture non renseignés) ; 5) rangs libres inconnus. À rang égal : le plus de places libres (US-227), sinon le plus de rangs libres, puis l'ordre des parcelles
- [ ] CA7 ter : Le libellé dit l'écart en mots, jamais par une coche seule ; un écart de deux crans est signalé comme déconseillé (« déconseillé : ombre, pour une culture de plein soleil »). Une parcelle déconseillée reste proposée : la suggestion conseille, elle n'interdit pas (A8)
- [ ] CA8 : Une parcelle sans ensoleillement dit « ensoleillement de la parcelle non renseigné » et invite à le déclarer (la phrase à dire au compagnon)

*Définition de terminé*
- [ ] CA9 : Fiches `parcelles-et-plan.md` et `pepiniere-par-lot.md` mises à jour (US-099 / CA9)
- [ ] CA10 : Tests : vocabulaire fermé et normalisation, refus hors vocabulaire, orientation inchangée, saisie bot et PWA, droits, les trois issues de la comparaison, isolation entre potagers
- [ ] CA11 : Le rendu de la fiche parcelle correspond à la maquette à 375 px / 768 px / desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement, consultation (PWA), interaction Telegram
- Migration BDD requise : **oui** (colonne facultative sur `parcelles`)
- Dépendances : US-161 (vocabulaire), US-230 (fiche parcelle), US-217 (consommateur)
- Inspiration : le sélecteur « Niveau d'ensoleillement » de potagerr.com (relevé le 15/10/2026) — retenu : la définition en heures de soleil direct ; écarté : sa 4ᵉ valeur « Lumière artificielle », sans équivalent côté culture (US-161) donc jamais comparable, et qui concerne les pépinières d'intérieur plutôt que les planches. À instruire à part, avec le type de pépinière (US-208) si le besoin se confirme
- Point de vigilance : ne **pas** retirer « Mi-ombre » des orientations proposées par US-230 dans cette US — les parcelles existantes le portent ; le nettoyage éventuel de cette liste se décide à part

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Une planche au soleil devient concordante
  Given la planche racines, orientée Nord, sans ensoleillement
  And un lot de 40 choux en godet, culture de plein soleil
  When je dis « ensoleillement planche racines plein soleil » et que je confirme
  And j'ouvre la fiche du lot
  Then "Où les mettre" propose la planche racines, "plein soleil, comme la culture le demande"
  And son orientation affichée reste "Nord"

Scénario: La meilleure parcelle d'abord
  Given un lot de choux, culture de plein soleil
  And la planche A à l'ombre avec 4 rangs libres, la planche B à mi-ombre avec 1 rang libre, la planche C en plein soleil avec 1 rang libre
  When j'ouvre la fiche du lot
  Then "Où les mettre" propose dans l'ordre C, puis B, puis A "déconseillé : ombre, pour une culture de plein soleil"

Scénario: Valeur refusée
  When je dis « ensoleillement planche racines sud »
  Then le compagnon refuse et liste "plein soleil (6 h et plus de soleil direct), mi-ombre (3 à 6 h), ombre (moins de 3 h)"

Scénario: Ensoleillement non renseigné
  Given la tubercule n'a pas d'ensoleillement
  When j'ouvre la fiche du lot
  Then la tubercule apparaît "ensoleillement de la parcelle non renseigné"
```

**Labels GitHub :** `us`, `backend`, `frontend`, `pwa`, `bot`, `migration`, `plan`, `pepiniere`
