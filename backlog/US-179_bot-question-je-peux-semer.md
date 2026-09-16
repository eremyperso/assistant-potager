**ID :** US-179
**Titre :** Répondre au bot à « je peux semer / planter X ? » avec le niveau de confiance et ses motifs
**Épic :** ÉPIC 8 — Confiance et personnalisation du calendrier *(numéro à valider, voir le plan de l'épic)*

**Story :**
En tant que jardinier
Je veux demander au bot, en langage naturel, si je peux semer ou planter une culture ce week-end
Afin d'obtenir une réponse étoilée et motivée, et d'enregistrer le geste en un appui si je décide de le faire

**Contexte fonctionnel :**
US-178 calcule la confiance ; cette US la met dans la main du jardinier, là où la question se pose : au champ, au téléphone, souvent à la voix. Trois exigences :

1. **Comprendre la question sans la faire payer.** « Je peux semer des haricots samedi ? », « c'est le moment de planter les tomates ? », « je sème les carottes ce week-end ou j'attends ? » doivent passer par la grammaire déterministe de l'interpréteur (US-172), à zéro jeton. Ce n'est qu'à défaut que la question rejoint le routeur de questions existant (US-170), au tier déjà en place.
2. **Répondre court et motivé.** La réponse tient en un message : culture, action, zone, étoiles, motifs (gagnés puis perdus puis indéterminés), et la récolte attendue si le jardinier agit à cette date (US-070, US-177).
3. **Fermer la boucle.** La réponse propose des boutons qui mènent au geste : enregistrer le semis ou la plantation à cette date, ou revenir dans dix jours. L'enregistrement réutilise le flux existant, avec le contexte de semis pré-rempli (US-069) — la recommandation et l'enregistrement ne sont plus deux commandes.

**Critères d'acceptance :**
- [ ] CA1 : Une question dictée ou tapée demandant s'il est opportun de **semer** ou **planter** une culture, avec ou sans date, avec ou sans parcelle, est reconnue et reçoit la réponse de confiance. Sans date, la date de référence est aujourd'hui ; « ce week-end » se résout au samedi suivant ; « samedi », « le 20 mai », « dans dix jours » sont compris par l'extraction de date existante de l'interpréteur
- [ ] CA2 : La reconnaissance passe **d'abord par la grammaire déterministe** ; une phrase reconnue ne consomme aucun jeton. Une phrase non reconnue rejoint le routeur de questions existant (US-170) sans traitement particulier, et n'est jamais rejetée en silence
- [ ] CA3 : L'**action** est déduite du verbe (« semer » / « planter ») et, pour un semis, la filière est demandée en un seul geste quand la culture se sème des deux façons et que la phrase ne le dit pas — même mécanique que la proposition d'US-069 / CA3, réutilisée. Une parcelle pépinière nommée dans la phrase impose *semis en pépinière*
- [ ] CA4 : La réponse affiche, dans cet ordre : culture · action · zone du potager, le niveau en **étoiles**, les motifs *gagnés*, puis *perdus*, puis *indéterminés*, chacun sur sa ligne, puis la **récolte attendue** si le geste est fait à cette date (fourchette, jamais une date sèche), ou un tiret
- [ ] CA5 : Quand aucun score n'est possible (culture sans calendrier pour la zone), la réponse le dit en une ligne et propose de compléter le calendrier au bot (`/calendrier`) — jamais une estimation
- [ ] CA6 : La réponse porte des **boutons** : « Enregistrer le semis » / « Enregistrer la plantation » à la date demandée, avec la filière et la parcelle pré-remplies, qui enchaînent sur le flux d'enregistrement existant (confirmation incluse) ; et « Redemander dans 10 jours », qui répond par la même évaluation décalée de dix jours. Aucun nouveau chemin d'enregistrement n'est créé
- [ ] CA7 : Quand la parcelle n'est pas nommée et que le potager en a plusieurs compatibles, la réponse est calculée pour le potager (règles R1, R2, R3, R4, R5, sans modulateur de parcelle) et le bouton d'enregistrement demande la parcelle, comme le fait le flux existant
- [ ] CA8 : Le corpus de mesure de l'interpréteur (`us172_commandes.csv`) est étendu d'au moins **20 formulations** de cette question (vocales, elliptiques, avec et sans date, avec et sans parcelle) et d'au moins **5 phrases hors périmètre** proches (« j'ai semé des haricots samedi » est un enregistrement, pas une question) ; le taux de reconnaissance et le taux de faux positifs sont consignés dans la livraison
- [ ] CA9 : La réponse est formatée sans risque d'erreur Telegram (`Can't parse entities`) : les libellés de cultures, de parcelles et de motifs sont échappés comme les autres messages du bot ; un test le vérifie avec un nom de culture contenant un caractère spécial
- [ ] CA10 : Aucun état de conversation (`ctx.user_data`) n'est laissé ouvert après une réponse sans appui sur un bouton ; un test vérifie qu'une commande suivante n'est pas capturée par cette US
- [ ] CA11 : La fiche d'aide `calendrier-et-zone-climatique.md` gagne une section « Savoir si c'est le moment », avec au moins deux questions de mesure servies (US-099 / CA9), et le corpus de mesure reste classé
- [ ] CA12 : Des tests couvrent : reconnaissance des formulations du CA8, résolution des dates du CA1, déduction d'action et proposition de filière du CA3, réponse complète du CA4, absence de score du CA5, enchaînement des boutons du CA6 jusqu'à la confirmation existante, potager multi-parcelles du CA7, échappement du CA9, absence d'état résiduel du CA10

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement (par réutilisation)
- Migration BDD requise : **non**
- Dépendances : **US-178** (moteur, bloquante), **US-172** (interpréteur déterministe, livrée), **US-170** (routeur de questions, livrée), **US-069** (proposition de filière, livrée), **US-070** / **US-177** (récolte attendue)
- Impact tokens : **0 jeton** sur le chemin déterministe (CA2). Repli : 1 appel au routeur existant, au tier en place — à mesurer, le CA8 en donne la fréquence attendue. Aucun appel pour la réponse elle-même (gabarit texte)
- Point de vigilance — **ordre des handlers** : la question « je peux semer… » contient le mot « semer » que la grammaire d'enregistrement pourrait capter ; l'ouverture interrogative (`_ouverture_interrogative`, `_est_demande_de_savoir`) doit être testée **avant** la règle d'enregistrement, et le corpus du CA8 contient les deux formes pour le garantir
- Point de vigilance — **fluidité** : la proposition de filière du CA3 ne doit pas transformer la question en interrogatoire ; si la culture ne se sème que d'une façon dans le référentiel, aucune question n'est posée (même règle qu'US-069)
- Point de vigilance : la réponse reste au **conditionnel** (« récolte attendue »), et une fourchette reste une fourchette

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Question reconnue, réponse motivée
  Given un potager localisé en zone océanique avec une parcelle "rang 3"
  And le moteur de confiance rend deux étoiles pour semer des haricots en pleine terre samedi
  When le jardinier dicte "je peux semer des haricots rang 3 ce week-end ?"
  Then la réponse affiche "Haricot · semis en pleine terre · océanique"
  And deux étoiles
  And chaque motif sur sa ligne, gagnés avant perdus
  And une récolte attendue en fourchette
  And aucun jeton n'a été consommé

Scénario: Filière proposée en un geste
  Given une tomate qui se sème en pépinière et en pleine terre dans le référentiel
  When le jardinier dicte "c'est le moment de semer des tomates ?"
  Then le bot propose la filière la plus probable avec un bouton pour la confirmer et un pour l'autre
  And la réponse de confiance est rendue après ce seul geste

Scénario: De la recommandation à l'enregistrement
  Given une réponse de confiance affichée pour planter des tomates samedi en parcelle 2
  When le jardinier appuie sur "Enregistrer la plantation"
  Then le flux d'enregistrement existant s'ouvre avec la culture, la date, la parcelle pré-remplies
  And la confirmation habituelle est demandée

Scénario: Sans calendrier, pas d'estimation
  Given l'ail n'a aucune fenêtre pour la zone du potager
  When le jardinier demande "je peux planter de l'ail ?"
  Then la réponse dit qu'aucun calendrier n'existe pour l'ail dans sa zone
  And propose de le compléter avec /calendrier
  And n'affiche aucune étoile ni aucune date

Scénario: Enregistrement, pas question
  When le jardinier dicte "j'ai semé des haricots rang 3 samedi"
  Then la phrase est traitée comme un enregistrement
  And aucune réponse de confiance n'est produite

Scénario: Phrase non reconnue
  When le jardinier dicte "tu penses quoi des haricots en ce moment ?"
  Then la phrase rejoint le routeur de questions existant
  And le jardinier reçoit une réponse
```

**Labels GitHub :** `us`, `bot`, `cultures`
