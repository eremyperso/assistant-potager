**ID :** US-196
**Titre :** Préparer un geste dans la PWA et le faire confirmer au compagnon Telegram
**Épic :** ÉPIC 9 — Socle commun Plan, Cultures, Pépinière *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux, depuis l'écran où je regarde une culture, un rang libre ou un lot, lancer le geste correspondant avec la culture, le lot, la parcelle et la date déjà remplis
Afin de l'enregistrer en une confirmation dans mon compagnon, sans le redicter en entier ni chercher la bonne commande

**Contexte fonctionnel :**
Les wireframes posent une règle constante (v2, encart « BACKOFFICE ») : *« Ces écrans lisent. Les boutons d'action qui restent ouvrent le flux existant avec des champs pré-remplis, ils n'écrivent pas eux-mêmes — c'est déjà la règle d'US-183 (CA6). »* Ils en tirent une dizaine de boutons : « Enregistrer le semis » de la fiche calendrier, « ajouter une culture » d'un rang libre du Plan, « Repiquer », « Noter la levée », « Mettre en terre », « Clôturer » d'un lot de pépinière.

**Or ce flux n'existe pas dans la PWA.** C'est écrit dans `docs/domaines/calendrier-cultural.md` : « Pas de bouton d'enregistrement dans la fiche tant que la PWA n'a pas de flux d'enregistrement : `FicheCalendrier` ne le rend que si l'appelant fournit `onEnregistrer`, et aucun écran ne le fournit. `/parse` n'en est pas un — il passe par le modèle de langage et écrit sans confirmation. » Le CA6 d'US-183 est donc livré sans bouton.

Le flux d'enregistrement de l'application, c'est **le bot** — le « backoffice » au sens du document d'analyse de la refonte (§ 5.5). Et il sait déjà recevoir un geste pré-rempli : le bouton « Enregistrer » de la réponse de confiance (US-179) appelle `saisie._parse_and_save` avec un item **pré-parsé**, « même contrat que le parseur déterministe d'US-094. Donc la confirmation habituelle, les avertissements de rotation, la demande de parcelle : tout est celui du flux existant ». Il sait aussi être ouvert depuis la PWA par un lien profond `?start=<code>` (US-091).

Cette US assemble les deux : la PWA **prépare** un geste (une intention de geste, stockée côté serveur, de courte durée) et ouvre le compagnon par un lien profond ; le bot **présente** ce geste pré-rempli dans son flux de confirmation habituel. Rien n'est écrit avant « Confirmer ». Aucun nouveau chemin d'écriture.

⚖️ **Arbitrage A16** (plan des épics § 6) : un formulaire de saisie web branché sur le même service est l'alternative. Il est hors périmètre : il créerait un second chemin d'écriture, que les wireframes excluent.

**Critères d'acceptance :**

*Préparer le geste*
- [ ] CA1 : `POST /gestes/intentions` reçoit un geste pré-parsé — action, culture, variété, quantité, unité, parcelle, rang, lot, date, filière de semis, écran d'origine, tous facultatifs sauf l'action — et répond par un code, son heure d'expiration, le lien profond vers le compagnon et la phrase équivalente à dicter (CA9)
- [ ] CA2 : Le serveur valide sans écrire aucun événement : action du référentiel d'actions (US-168) et parmi les gestes ouverts à la PWA ; parcelle et lot appartenant au potager consulté (US-042) ; rôle propriétaire ou éditeur, un membre en lecture seule reçoit un refus (US-047). Une intention n'apparaît ni au Journal, ni dans un stock, ni dans une statistique
- [ ] CA3 : Le code est opaque et non devinable (au moins 128 bits d'aléa), tient dans le paramètre `start` de Telegram (64 caractères au plus, alphabet `A-Z a-z 0-9 _ -`), porte un préfixe réservé qui le distingue des codes de liaison (US-045) ; il est à **usage unique**, valable **15 minutes** — même durée que l'état en attente d'US-179 — et lié au compte et au potager qui l'ont préparé
- [ ] CA4 : Les intentions vivent en base, puisque l'API et le bot sont deux processus : une table dédiée, sous RLS par potager, purgée des intentions expirées. Migration avec rollback

*Confirmer au compagnon*
- [ ] CA5 : `/start <code>` présente le geste pré-rempli **par le même chemin que le bouton « Enregistrer » d'US-179** : item pré-parsé, récapitulatif et confirmation (US-021), avertissement de rotation à la plantation (US-167), parcelle demandée si elle manque, quantité demandée si elle manque. Rien n'est écrit avant « Confirmer ». Zéro jeton consommé
- [ ] CA6 : Le code est refusé en clair s'il a expiré, s'il a déjà servi, ou si la conversation Telegram est liée à un **autre compte** que celui qui l'a préparé ; le message invite à relancer depuis l'application. Un code de liaison existant garde son traitement inchangé
- [ ] CA7 : Le geste s'enregistre dans le **potager de l'intention**. Si le potager actif du bot est un autre, le récapitulatif nomme le potager et la bascule est faite et dite (US-088) ; jamais d'écriture silencieuse dans un autre potager. Un compte qui n'en est plus membre reçoit un refus
- [ ] CA8 : « Modifier » et « Annuler » du récapitulatif fonctionnent comme pour une saisie dictée ; l'état en attente suit la règle d'US-179 (hors du mode de conversation, 15 minutes)

*Dans la PWA*
- [ ] CA9 : Un seul composant — bouton et crochet partagés — sert tous les boutons d'action des épics 9 à 12. Il prépare l'intention puis ouvre le lien. À côté, il propose **la phrase à dicter** (« Ou dites au compagnon : « levée du lot 128 : 40 » »), copiable. Chaque gabarit de phrase est reconnu par le parseur déterministe sans appel au modèle : un test passe chaque gabarit dans le parseur
- [ ] CA10 : Sans conversation Telegram liée au compte (lu dans `GET /auth/me`), le bouton ouvre d'abord l'activation du compagnon (US-091), puis reprend le geste
- [ ] CA11 : Un membre en lecture seule ne voit aucun bouton d'action (RT11)
- [ ] CA12 : Au retour sur la PWA (onglet redevenu visible), l'écran qui a lancé le geste relit ses données **une fois**, pour que le geste confirmé y apparaisse ; aucune interrogation périodique

*Premier consommateur : la fiche calendrier (US-183 / CA6)*
- [ ] CA13 : Tous les points d'entrée de la fiche calendrier — tuile du Plan, puce de Stocks, fiche culture (US-207) — lui fournissent `onEnregistrer`. « Semer en pépinière », « semer en place » et « planter » deviennent un semis avec sa filière ou une plantation ; la parcelle est pré-remplie quand la fiche a été ouverte depuis une parcelle
- [ ] CA14 : Le geste est daté de la date de référence si elle est passée ou du jour, **du jour** si elle est dans le futur, et le bouton le dit (« enregistré à la date d'aujourd'hui ») : un geste ne se date jamais dans le futur
- [ ] CA15 : Le bouton reste **actif hors fenêtre** (arbitrage A8) : la confiance conseille, elle n'interdit pas

*Définition de terminé*
- [ ] CA16 : Fiches corrigées dans la même livraison (US-099 / CA9) : `compagnon-telegram.md` (lancer un geste depuis l'application), `enregistrer-un-geste.md` (une troisième façon de commencer un geste), `calendrier-et-zone-climatique.md` (le bouton de la fiche calendrier). `docs/domaines/calendrier-cultural.md` retire la mention « pas de bouton d'enregistrement » ; `docs/domaines/commandes-bot.md` documente le préfixe de `/start`
- [ ] CA17 : Des tests couvrent : validation de l'intention (action inconnue, parcelle d'un autre potager, lecteur refusé), expiration, usage unique, autre compte, autre potager actif, parcelle et quantité demandées, rien d'écrit avant confirmation, zéro jeton, gabarits de phrase reconnus par le parseur, activation préalable du compagnon, date future ramenée au jour

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement
- Migration BDD requise : **oui** — table des intentions de geste (code unique, compte, potager, geste pré-parsé, création, expiration, consommation), RLS par potager. Numéro à lire dans `migrations/` au démarrage — dernier constaté : v48
- Dépendances : US-045 (liaison), US-091 (lien profond `?start=`), US-179 (item pré-parsé et état en attente), US-021 (confirmation), US-167 (rotation), US-088 (potager actif), US-047 (rôles) — toutes livrées ; US-183 (premier consommateur, livrée)
- Consommateurs suivants : US-201 (rang libre), US-216 (gestes d'un lot), US-217 (mettre en terre ici), US-218 (semer maintenant)
- Impact tokens : zéro — le parseur n'est pas appelé, l'item arrive pré-parsé
- Point de vigilance : le lien profond ne transporte **que** le code. Aucune donnée du potager, aucun nom de culture n'apparaît dans l'adresse, ni dans les journaux du serveur web
- Point de vigilance : un jardinier sans Telegram ne peut toujours rien enregistrer depuis la PWA — c'est l'état actuel, pas une régression. Le signaler dans la fiche `compagnon-telegram.md`
- Point de vigilance : les gestes introduits plus tard (levée, US-212 ; déplacement, US-211) s'ajoutent à la liste des gestes ouverts à la PWA dans leur propre US, avec leur gabarit de phrase

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Enregistrer un semis depuis la fiche calendrier
  Given mon compte est lié à mon compagnon Telegram
  And la fiche calendrier de l'épinard est ouverte au 19 septembre sur "Semer en place"
  When j'appuie sur "Enregistrer le semis"
  Then mon compagnon s'ouvre sur le récapitulatif "semis d'épinard en pleine terre, le 19 septembre"
  And la parcelle m'est demandée
  And rien n'est enregistré avant que j'appuie sur "Confirmer"

Scénario: Lien expiré
  Given un geste préparé il y a vingt minutes
  When j'ouvre son lien dans Telegram
  Then le compagnon m'indique que le lien a expiré et m'invite à relancer depuis l'application

Scénario: Lien ouvert depuis un autre compte
  Given un geste préparé par Camille
  When le lien est ouvert dans une conversation liée au compte de Dominique
  Then le compagnon refuse le geste
  And rien n'est enregistré

Scénario: Compagnon pas encore activé
  Given mon compte n'est lié à aucune conversation Telegram
  When j'appuie sur "Enregistrer la plantation"
  Then l'activation du compagnon s'ouvre d'abord
  And le geste pré-rempli est présenté une fois le compagnon activé

Scénario: Membre en lecture seule
  Given je suis membre du potager en lecture seule
  When j'ouvre la fiche calendrier de la tomate
  Then aucun bouton d'enregistrement n'est affiché

Scénario: Retour sur l'application
  Given j'ai confirmé au compagnon un geste préparé depuis la Pépinière
  When je reviens sur l'onglet de l'application
  Then la Pépinière relit ses lots une fois et affiche le geste enregistré
```

**Labels GitHub :** `us`, `backend`, `bot`, `frontend`, `pwa`, `securite`
