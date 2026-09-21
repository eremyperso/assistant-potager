**ID :** US-221
**Titre :** Imprimer des étiquettes de lot à QR code qui ouvrent la fiche du lot *(option)*
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier qui a une imprimante
Je veux imprimer pour mes barquettes des étiquettes qui portent le nom du lot et un QR code
Afin d'ouvrir la fiche d'un lot en visant l'étiquette avec mon téléphone, sans rien taper

**Contexte fonctionnel :**
La v2 (§ 3d) dessine cette option et la défend en une phrase : le QR supprime « trois écrans avant le premier chiffre ». Elle la borne aussitôt : « C'est le seul argument ; s'il ne tient pas, l'option tombe », et « l'application doit être complète sans imprimante ». C'est l'arbitrage A13 : le **numéro de lot** écrit au crayon (US-209) est le premier pas ; l'étiquette imprimée vient **en option**, sur usage.

Elle en fixe les règles :
- **ce que fait le scan** : « 1 · Ouvre le lot, déjà authentifié si la session est ouverte. 2 · Rien d'autre : pas d'écriture au scan, pas de geste automatique » ;
- **ce que porte l'étiquette** : « une donnée figée collée sur du vivant : le lot bouge, l'étiquette ment. Elle ne doit donc jamais porter autre chose que l'identité du lot et un rappel de date » (arbitrage A14 — l'exemple dessiné portait la quantité et l'emplacement ; la règle écrite les exclut) ;
- **la question de sécurité** : « Jeton opaque non devinable, révocable, sans donnée dans l'URL — et que voit quelqu'un qui n'est pas membre du potager : rien, ou une page « demander l'accès » ? » Décision proposée : **rien** — un message sans aucune donnée ; aucune demande d'accès en V1.

⚖️ **US optionnelle.** Aucune autre US n'en dépend.

**Critères d'acceptance :**

*Les étiquettes*
- [ ] CA1 : Un bouton « Étiquettes » dans la barre de la Pépinière ouvre l'écran d'impression : sélection des lots (lots en cours par défaut, tout lot numéroté possible, pour réimprimer), aperçu de la planche, « Imprimer ». Réservé au propriétaire et à l'éditeur (RT11)
- [ ] CA2 : La planche est une **page A4 de 12 étiquettes de 70 × 37 mm** (v2), mise en page pour l'impression du navigateur à l'échelle 100 % ; les emplacements restants de la planche sont laissés vides. Le format est confirmé à la haute fidélité (les planches du commerce de ce format en portent souvent 24)
- [ ] CA3 : Chaque étiquette porte **seulement** : la culture en capitales, la variété, « lot #128 », la date de semis, et un rappel de date quand une échéance est connue (« repiquage vers le 13/09 », US-214). **Ni quantité, ni emplacement**. Le texte seul suffit à identifier le lot sans téléphone
- [ ] CA4 : Le QR code, d'au moins 20 mm de côté, encode l'adresse `https://<application>/l/<jeton>` et rien d'autre ; il est produit avec la bibliothèque déjà utilisée pour la liaison Telegram (`qrcode.react`), sans nouvelle dépendance

*Le jeton*
- [ ] CA5 : Le jeton est **opaque et non devinable** (au moins 128 bits d'aléa), sans aucune donnée du potager ni du lot ; il est créé à la première impression d'un lot, stocké côté serveur sous RLS par potager, et **réutilisé** aux réimpressions pour que les anciennes étiquettes restent valables
- [ ] CA6 : « Régénérer l'étiquette » **révoque** l'ancien jeton d'un lot et en crée un nouveau ; une étiquette révoquée ne mène plus à rien
- [ ] CA7 : La création et la révocation d'un jeton sont les seules écritures de cette US ; aucune n'apparaît au Journal ni ne touche un stock

*Le scan*
- [ ] CA8 : L'adresse `/l/<jeton>` est résolue par le serveur **pour l'utilisateur connecté** : membre du potager, elle ouvre la **fiche du lot** (US-216) par le mécanisme d'intention d'US-195, avec bascule de potager dite si nécessaire ; déconnecté, il se connecte puis arrive sur le lot (US-195 / CA6)
- [ ] CA9 : Non membre, jeton révoqué ou inconnu, lot supprimé : **le même message**, « Cette étiquette n'ouvre aucun lot accessible avec ce compte », sans révéler si le lot ou le potager existe
- [ ] CA10 : **Aucune écriture au scan**, aucun geste automatique ; un test le vérifie

*Définition de terminé*
- [ ] CA11 : La composition du texte d'une étiquette et la disposition de la planche vivent dans une lib sans React couverte par `npm test` ; l'impression est vérifiée sur Chrome et Firefox (marges, échelle, coupure des étiquettes)
- [ ] CA12 : La fiche `pepiniere-par-lot.md` explique comment imprimer, réimprimer et régénérer une étiquette, et rappelle que le numéro écrit à la main fait le même travail (US-099 / CA9) ; `docs/domaines/migrations.md` décrit la migration
- [ ] CA13 : Des tests couvrent : format et entropie du jeton, réutilisation à la réimpression, révocation, résolution pour un membre, un non-membre, un utilisateur déconnecté, un jeton révoqué et un lot supprimé (même réponse), absence d'écriture au scan, contenu de l'étiquette sans quantité ni emplacement
- [ ] CA14 : Le rendu de l'écran d'impression et de la planche correspond à la maquette haute fidélité gelée

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA), sécurité
- Migration BDD requise : **oui** — table des jetons d'étiquette (potager, lot, jeton unique, création, révocation), RLS par potager, rollback fourni. Numéro à lire dans `migrations/` au démarrage
- Dépendances : **US-209** (numéro de lot), **US-216** (fiche du lot), **US-195** (intention par l'adresse) ; US-214 pour le rappel de date
- Impact tokens : zéro
- Point de vigilance : l'adresse d'une étiquette finit dans l'historique du navigateur et les journaux du serveur web ; c'est acceptable **parce que** le jeton ne porte aucune donnée et n'ouvre rien sans être membre du potager
- Point de vigilance : deux autres usages évoqués par la v2 — étiquette de parcelle, étiquette de bocal de graines — sont hors périmètre (plan des épics § 9)
- Wireframe : `maquette front/wireframes/Wireframes v2 - Plan Cultures Pepiniere.html`, § 3d et les notes « Pourquoi l'étiquette vaut le coup », « Pourquoi ça doit rester une option », « Sans imprimante »

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Imprimer trois étiquettes
  Given les lots 128, 131 et 119 sont en cours
  When j'ouvre "Étiquettes", je sélectionne les trois lots et j'appuie sur "Imprimer"
  Then une planche A4 porte trois étiquettes remplies et neuf emplacements vides
  And l'étiquette du lot 128 porte "CHOU FRISÉ", "lot #128", la date de semis et son QR code
  And aucune étiquette ne porte de quantité ni d'emplacement

Scénario: Scanner une étiquette
  Given je suis connecté et membre du potager du lot 128
  When je vise l'étiquette du lot 128 avec mon téléphone
  Then la fiche du lot 128 s'ouvre
  And rien n'est enregistré

Scénario: Étiquette trouvée par un tiers
  Given une personne qui n'est pas membre du potager
  When elle scanne l'étiquette du lot 128
  Then elle voit "Cette étiquette n'ouvre aucun lot accessible avec ce compte"
  And rien n'indique à quel potager appartient le lot

Scénario: Régénérer une étiquette
  Given l'étiquette du lot 128 a été perdue
  When j'appuie sur "Régénérer l'étiquette" pour le lot 128
  Then l'ancienne étiquette ne mène plus à rien
  And la nouvelle ouvre la fiche du lot 128
```

**Labels GitHub :** `us`, `frontend`, `backend`, `migration`, `pepiniere`, `securite`, `optionnelle`
