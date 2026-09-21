**ID :** US-209
**Titre :** Numéroter les lots de semis et les retrouver par leur numéro
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux que chaque semis en pépinière reçoive un numéro court, que j'écris au crayon sur l'étiquette de la barquette
Afin de dire « levée du lot 128 : 40 » ou d'ouvrir le lot 128 dans l'application sans chercher parmi mes semis de choux

**Contexte fonctionnel :**
Depuis US-065, la pépinière se lit **lot par lot** : chaque semis en pépinière forme un lot, identifié par sa date. C'est suffisant à l'écran, pas au jardin : deux barquettes de chou semées la même semaine se ressemblent, et une date ne s'écrit pas vite sur une étiquette.

La v2 dessine un numéro court sur chaque lot (« #128 · Chou frisé ») et en fait la réponse à sa question la plus ouverte : plutôt qu'une étiquette imprimée à QR code, « un numéro de lot court (#128) écrit au crayon sur l'étiquette plastique que le jardinier a déjà, et un champ « aller au lot n° » dans l'app. Zéro impression, 80 % du bénéfice. Peut-être le vrai premier pas. » C'est l'arbitrage A13 : le numéro d'abord, le QR code en option ensuite (US-221).

Aujourd'hui, un lot n'a que l'identifiant technique de son semis, global à toute l'application.

**Critères d'acceptance :**

*Le numéro*
- [ ] CA1 : Chaque lot de pépinière — le même ensemble que celui de `GET /pepiniere/lots` — reçoit un **numéro court**, entier, unique **dans son potager**, attribué dans l'ordre de création à partir de 1, **jamais réutilisé** même après suppression ou correction. Le lot « godets sans semis rattaché » n'a pas de numéro et le dit
- [ ] CA2 : Le numéro est attribué **à l'enregistrement du semis**, dans la même transaction ; deux semis enregistrés au même instant dans le même potager n'obtiennent jamais le même numéro (test de concurrence)
- [ ] CA3 : Les lots existants sont numérotés par la migration, potager par potager, dans l'ordre des dates de semis puis des identifiants. Rejouer la reprise ne renumérote rien. Une numérotation n'est pas une supposition sur les données : c'est un identifiant
- [ ] CA4 : Un semis dont la filière est corrigée de pépinière en pleine terre (US-069) garde son numéro mais quitte la liste des lots ; corrigé dans l'autre sens, il reçoit un numéro s'il n'en avait pas

*Au bot*
- [ ] CA5 : Les gestes de pépinière reconnaissent la référence à un lot — « lot 128 », « le lot 128 », « #128 » — par la grammaire déterministe, sans appel au modèle : mise en godet (le lot devient l'origine des graines, sans la question d'US-066), perte en pépinière, vente de plants, plantation depuis la pépinière (chaînage d'US-029), et les gestes ajoutés par US-211 (déplacement) et US-212 (levée)
- [ ] CA6 : Un numéro inconnu, ou qui contredit la culture dite (« lot 128 de tomates » alors que le lot 128 est un chou), est signalé au récapitulatif, jamais corrigé en silence ; le jardinier choisit
- [ ] CA7 : `/lot 128` — et la phrase « où en est le lot 128 ? » — répond en zéro jeton : culture, variété, date de semis, emplacement, graines semées, plants obtenus et restants, et l'échéance quand US-214 est livrée. La commande est tranchée au catalogue (dictable, menu natif, `controler_parite()` vert)
- [ ] CA8 : Les récapitulatifs et les listes du bot qui nomment un lot affichent son numéro

*Dans la PWA*
- [ ] CA9 : `GET /pepiniere/lots` expose le numéro de chaque lot ; `GET /pepiniere/lots/{numero}` rend un lot du potager consulté, ou une réponse « lot inconnu »
- [ ] CA10 : Le numéro apparaît sur chaque carte de l'onglet Lots actuel (US-061) et partout où un lot est nommé
- [ ] CA11 : Un champ **« Aller au lot n° »** dans la barre de la Pépinière ouvre la fiche du lot (US-216 ; le détail existant du lot tant qu'US-216 n'est pas livrée). Un numéro inconnu affiche « Aucun lot n° 128 dans ce potager ». Le même lot s'ouvre par l'adresse `/?vue=pepiniere&lot=128` (US-195)

*Définition de terminé*
- [ ] CA12 : Les fiches `pepiniere-par-lot.md` (retrouver un lot par son numéro, l'écrire sur l'étiquette), `semis-godet-plantation.md` (citer le lot à la mise en godet et à la plantation) et `enregistrer-un-geste.md`, ainsi que le guide utilisateur (commandes), sont mis à jour (US-099 / CA9) ; `docs/domaines/migrations.md` décrit la migration et sa reprise
- [ ] CA13 : Des tests couvrent : attribution, concurrence, non-réutilisation, reprise idempotente, correction de filière dans les deux sens, référence au lot dans chaque geste du CA5, numéro inconnu ou contradictoire, `/lot`, lecture par numéro, champ « Aller au lot n° », isolation entre potagers (le lot 128 d'un autre potager n'est jamais trouvé)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement, consultation
- Migration BDD requise : **oui** — numéro de lot nullable sur les événements de semis, unique par potager (index partiel), compteur par potager pour une attribution sans collision, reprise de l'existant entre marqueurs `REPRISE` (modèle de la migration v47), rollback fourni. Numéro à lire dans `migrations/` au démarrage
- Dépendances : US-065 (lecture par lot), US-066 (origine des graines), US-069 (filière), US-029 (chaînage) — livrées
- Consommateurs : US-211, US-212, US-214, US-215, US-216, US-221
- Impact tokens : zéro
- Point de vigilance : le numéro n'est **jamais** l'identifiant technique de l'événement. Un identifiant global laisserait deviner le volume d'activité des autres potagers et changerait de sens à chaque import
- Point de vigilance : « lot 12 » peut aussi être une quantité mal comprise (« 12 lots de godets »). Le mot « lot » suivi d'un nombre n'est une référence que dans une phrase de geste de pépinière ; le corpus de dictée porte les deux formes
- Wireframe : v2 § 3 (liste des lots) et note « Sans imprimante »

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Un semis en pépinière reçoit son numéro
  Given le dernier lot du potager porte le numéro 127
  When le jardinier dicte "semé 48 graines de chou frisé dans la serre"
  Then le lot créé porte le numéro 128
  And le récapitulatif l'annonce : "lot 128"

Scénario: Mise en godet depuis un lot cité
  Given le lot 128 est un semis de 48 graines de chou frisé
  When le jardinier dicte "repiqué 40 plants du lot 128 en godet"
  Then la mise en godet est rattachée au lot 128
  And le bot ne demande pas de quelles graines viennent les plants

Scénario: Numéro contradictoire
  Given le lot 128 est un chou frisé
  When le jardinier dicte "repiqué 10 tomates du lot 128 en godet"
  Then le récapitulatif signale que le lot 128 est un chou frisé et demande de choisir

Scénario: Aller au lot depuis l'application
  When je tape 128 dans "Aller au lot n°"
  Then la fiche du lot 128 s'ouvre

Scénario: Isolation entre potagers
  Given le potager A a un lot 5 et le potager B aussi
  When je consulte le potager B et je demande le lot 5
  Then c'est le lot 5 du potager B qui s'ouvre
```

**Labels GitHub :** `us`, `backend`, `bot`, `frontend`, `migration`, `pepiniere`
