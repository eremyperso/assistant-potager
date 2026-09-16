# Brief — Fiche calendrier d'une culture : semer ou planter, projection, confiance

Document de travail à emporter dans la conversation Claude Design (projet
`10f5afa7-58f8-4eb0-8dae-ca5834dfff59`, "potager 2026") pour concevoir la fiche
calendrier d'une culture (US-183). Rédigé le 2026-09-15, à éditer librement avant de
le coller. Point de départ : la maquette figée du 15/08/2026 (`Potager - Application
Web - FIGE 2026-08-15.html`), pas un projet vierge.

## Décision actée

**Le calendrier d'une culture se lit dans une fiche unique**, ouverte depuis une ligne
de l'écran Stocks (écran transverse des cultures, US-073) ou depuis une tuile de
l'écran Plan (US-060). Elle réunit trois choses que l'application calcule déjà ou va
calculer, et qu'aucun écran ne montre ensemble :

1. **Semer ou planter** — pour l'action choisie : fenêtre conseillée de la zone du
   potager, niveau de confiance à la date de référence (1 à 3 étoiles) avec ses motifs
   règle par règle, récolte attendue si le geste est fait à cette date, bouton
   d'enregistrement.
2. **Déjà en terre** — pour chaque série en place : origine réelle (semis ou
   plantation), levée et première récolte attendues, reste à courir, écart si dépassé.
3. **Frise** des douze mois — recalée sur la série la plus ancienne si une existe,
   conseillée sinon, avec sa légende et le mois de la date de référence en évidence.

Conséquence backlog : solde l'écart « absence de calendrier `MonthStrip` sur Stocks »
consigné à la livraison d'US-073. **Ne modifie pas `MonthStrip`.**

## Ce qui existe et doit être préservé (code réel)

- `frontend/src/views/Stocks.jsx` — ligne/carte par couple culture + variété, lien
  « N récoltes » ouvrant une **modale** (`components/ui/Modal.jsx`) chronologique avec
  total en pied (US-073 / CA13). La fiche calendrier s'ouvre avec le même composant et
  s'aligne sur cette modale (titre, fermeture, pied).
- `frontend/src/views/Plan.jsx` — tuile de culture : nom, « famille · durée », frise
  `MonthStrip`, quantités, icône d'observations (`onSelect` sur la tuile, `obs.toggle`
  sur l'icône). L'appui sur la frise devient un point d'entrée ; les deux appuis
  existants ne changent pas.
- `frontend/src/components/ui/MonthStrip.jsx` — frise douze mois + légende
  (`MonthStripLegend`). Quatre teintes de phase après US-176 (pépinière bleu, pleine
  terre violet, plantation vert, récolte ambre) ; `bg-brand-soft` réservé à « en
  croissance » (US-070). **Ces teintes sont figées : la fiche ne peut pas en introduire
  une cinquième pour la confiance.**
- Composants réutilisables : `Modal`, `Badge`, `Stat` (label muet + chiffre),
  `SectionLabel`, `Btn`, `InfoBanner` (pour « localise ton potager »).
- Typographie en place : nom de culture en serif (`font-serif text-[18px]`), texte
  secondaire `text-txt2` à 12,5-13 px.

## Ce qui est nouveau et doit être conçu

1. **Le sélecteur d'action** — *semer en pépinière · semer en place · planter*, limité
   aux phases connues (souvent deux, parfois une). Pré-positionné sur la meilleure
   confiance. À 375 px : une ligne de segments, ou un menu ; jamais trois cartes.
2. **Le bloc « règle de confiance »** — une ligne par règle : état (gagné / perdu /
   indéterminé), motif en clair, points obtenus sur points maximum (« 20 / 20 »).
   Cinq lignes. Ce bloc est **partagé** avec la fiche « pourquoi deux étoiles » de la
   tuile du Plan (US-180) : à concevoir une seule fois, dans une seule taille.
3. **Les étoiles** — `★★☆` en texte, une teinte du design system, jamais une couleur
   nouvelle, jamais le seul porteur de sens (libellé « Confiance moyenne » à côté).
4. **La carte « série en terre »** — parcelle, origine (« semée en place le 12 avril »),
   trois `Stat` (levée attendue, première récolte attendue, reste à courir), un état
   d'écart si la récolte est dépassée. Répétable : deux séries de haricots, c'est deux
   cartes, la plus ancienne en tête.
5. **Le titre de la frise** — « Calendrier recalé sur la série de la parcelle 2 » ou
   « Calendrier conseillé pour la zone océanique » : la fiche dit toujours ce qu'elle
   montre.

## Trois états à maquetter (les seuls qui comptent)

| État | Culture d'exemple | Ce qu'on doit voir |
|---|---|---|
| **Tout renseigné, série en terre** | Courgette semée en place le 12 avril, consultée le 15 juin | Partie 1 avec « semer en place ★★☆ », partie 2 avec une série et ses trois `Stat`, frise recalée |
| **Rien en terre, deux actions possibles** | Tomate au 5 mai | Sélecteur à deux segments (pépinière / planter), « Planter ★★★ » pré-sélectionné, pas de partie 2, frise conseillée |
| **Dégradé** | Ail, aucune fenêtre pour la zone, deux séries plantées | Partie 1 réduite à « aucun calendrier… » + lien `/calendrier`, partie 2 avec deux cartes en tirets, frise neutre |

Plus un quatrième, optionnel : **potager non localisé** — même fiche que le premier
état, avec deux règles météo en « indéterminé » et l'`InfoBanner` d'invitation à
localiser.

## Questions ouvertes à trancher (avec une recommandation)

1. **Modale ou page ?** À 375 px la fiche est longue (trois parties). *Recommandation :
   modale plein écran sur mobile, panneau latéral sur desktop — cohérent avec la modale
   des récoltes, et la fermeture ramène à l'écran d'origine dans son état.*
2. **La frise en tête ou en pied ?** Elle est la vue la plus familière, mais la moins
   décisionnelle. *Recommandation : en pied. La fiche sert à décider (partie 1) et à
   savoir où on en est (partie 2) ; la frise confirme.*
3. **Détail des règles replié ou déplié ?** Cinq lignes de motifs sous les étoiles
   allongent la partie 1. *Recommandation : les motifs perdus et indéterminés toujours
   visibles, les gagnés repliés sous « Voir les 5 règles » — c'est ce qui a coûté une
   étoile qu'on veut lire d'abord.*
4. **Le bouton d'enregistrement** — dans la partie 1 (près de l'action) ou en pied de
   fiche ? *Recommandation : dans la partie 1, sous les règles ; le pied de fiche reste
   réservé à la fermeture, comme la modale des récoltes.*

## Contraintes transverses à rappeler à Claude Design

- **Container queries, pas de breakpoints d'écran** pour tout composant réutilisable
  (règle non négociable de `CLAUDE.md`).
- **Tokens sémantiques uniquement**, aucun alias `--g-*`, aucune couleur nouvelle : les
  teintes de phase de la frise sont figées, la confiance ne peut pas en prendre une.
- **Aucune date sèche.** La récolte attendue est une fourchette ou un tiret ; le reste à
  courir aussi. Le vocabulaire reste au conditionnel (« attendue »).
- **Aucune valeur inventée dans la maquette** : les trois états ci-dessus utilisent les
  chiffres du cas de référence de l'épic 5 (courgette 12/04, 10 j levée, 95 j récolte)
  et des fenêtres lues dans `wind_river_attributs.json` (tomate océanique : pépinière
  février-mars, plantation avril-mai, récolte juillet-septembre).
- **Composants existants d'abord** : `Modal`, `Badge`, `Stat`, `SectionLabel`, `Btn`,
  `InfoBanner`, `MonthStrip` tels quels. Un seul composant nouveau attendu : le bloc
  « règle de confiance ».
- **Aucun nouvel endpoint ni migration** : la fiche lit `GET /cultures/{culture}/calendrier`
  (US-068), la lecture groupée de confiance (US-178) et les données déjà chargées par
  l'écran d'origine.
- **Livrable attendu** : les trois états à 375 px, 768 px et desktop, puis gel dans
  `Maquette figée/` avec sa ligne dans `LISEZ-MOI.md`, avant tout code.
