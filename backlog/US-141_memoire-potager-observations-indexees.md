**ID :** US-141
**Titre :** Rendre la mémoire du potager consultable en langage naturel
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier
Je veux retrouver ce que j'avais noté sur une parcelle ou une culture les saisons précédentes
Afin de profiter de ma propre expérience au lieu de la réécrire chaque année

**Contexte fonctionnel :**
Dixième US issue de `docs/ARCHITECTURE_CIBLE_V2_reponses.md` (§4.1, famille C). Elle exploite un
gisement déjà constitué : les observations et notes libres saisies par le jardinier (US-038 et
US-039, livrées), aujourd'hui consultables par filtre et par date, mais pas interrogeables par le
sens de ce qu'elles disent.

C'est la famille de connaissance qui produit le sentiment le plus fort de compagnon — l'assistant se
souvient de *ton* potager — et c'est aussi **celle qui porte le risque d'isolation le plus élevé** :
une note privée qui fuirait vers un autre jardin serait une atteinte directe à la confiance, bien
plus grave qu'une réponse agronomique approximative. L'isolation n'est donc pas ici un critère parmi
d'autres, c'est la raison d'être des tests de cette US.

> **Note de numérotation.** Voir US-140 : la bande 100 à 133 est réservée à l'ancienne numérotation
> du plan multi-tenant, cette déclinaison reprend la bande 140+ suggérée par le §9 du document
> d'architecture.

**Critères d'acceptance :**

*Indexation*
- [ ] CA1 : Les observations et notes libres du potager sont indexées comme fragments de famille `memoire_potager`, avec le `potager_id` du potager concerné — **jamais** avec un `potager_id` nul
- [ ] CA2 : L'indexation est **automatique à l'enregistrement** d'une observation : aucune action du jardinier, aucun délai perceptible
- [ ] CA3 : Une reprise initiale indexe les observations déjà enregistrées, de façon rejouable et sans doublon
- [ ] CA4 : Chaque fragment conserve le lien vers l'événement d'origine, sa date et, quand elle existe, la parcelle et la culture concernées

*Restitution*
- [ ] CA5 : Une question du type « qu'avais-je noté sur la parcelle nord l'an dernier ? » retourne les notes correspondantes avec leur **date** et leur **parcelle**, et un extrait fidèle du texte saisi — jamais une reformulation qui altérerait ce que le jardinier a écrit
- [ ] CA6 : Une réponse qui mêle mémoire du potager et savoir général **distingue les deux** : « ta note du 12 mai indique… » et « en général… » sont deux registres, et les confondre reviendrait à faire dire au jardinier ce qu'il n'a pas dit
- [ ] CA7 : La restitution ne consomme **aucun jeton** en lecture

*Isolation — raison d'être de l'US*
- [ ] CA8 : La recherche dans la famille `memoire_potager` filtre sur l'**égalité** de `potager_id` avec le potager courant, jamais sur la clause de savoir partagé. Un fragment de cette famille ne peut structurellement pas être partagé
- [ ] CA9 : Un test d'isolation dédié, de même niveau d'exigence que celui des événements (US-042), démontre qu'aucune note du potager A n'apparaît dans une recherche du potager B, y compris avec une question conçue pour la provoquer
- [ ] CA10 : Un membre qui quitte un potager (US-086) ou dont l'accès est retiré perd immédiatement l'accès à la mémoire de ce potager, sans traitement particulier : le filtre de potager courant suffit, et l'US le vérifie plutôt que de le supposer

*Cycle de vie de la donnée*
- [ ] CA11 : La suppression ou la correction d'une observation met à jour ou supprime le fragment correspondant : aucune mémoire orpheline ne survit à la donnée dont elle dérive
- [ ] CA12 : La suppression définitive d'un potager (US-084) emporte ses fragments de mémoire au même titre que ses événements, purge comprise
- [ ] CA13 : Un potager **archivé** (US-083) conserve sa mémoire consultable en lecture seule, en cohérence avec le comportement déjà livré pour la consultation d'un potager archivé — l'archivage met le potager en pause, il n'efface pas son histoire

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement | analyse | consultation
- Migration BDD requise : **non** — le socle de tables est livré par US-098 ; l'indexation utilise l'existant
- **Arbitrage tranché — on indexe les notes, pas les événements structurés :** les semis, récoltes et arrosages se répondent en SQL (US-096), exactement et à coût nul. Les verser dans la recherche documentaire donnerait des réponses approximatives sur des données parfaitement structurées. Seul le texte libre entre dans la mémoire
- **Arbitrage tranché — extrait fidèle plutôt que résumé :** la mémoire du potager restitue ce qui a été écrit. Un résumé produit par un modèle ferait perdre la valeur de preuve de la note et coûterait des jetons pour dégrader l'information
- **Arbitrage tranché — pas de mémoire déduite :** l'assistant n'invente pas de note à partir d'événements (« tu semblais avoir des problèmes de limaces »). La mémoire est ce que le jardinier a écrit, rien d'autre
- Dépendances : **US-098** (socle, bloquante), **US-038** et **US-039** (observations, livrées), **US-083** et **US-084** (archivage et suppression, livrées). Rattachement RGPD : le droit à l'effacement porte sur ces fragments comme sur les événements (US-132 du plan initial)
- Invariants projet : isolation inter-potagers testée ; échappement Markdown dans les sorties du bot (les notes contiennent du texte libre, donc potentiellement des caractères spéciaux)

**Notes techniques (pour Persona Developer) :**
- L'indexation doit être branchée dans la couche services d'écriture des observations, au même point que l'invalidation de cache d'US-095 — un seul endroit où « une observation vient de changer »
- Un échec d'indexation ne doit jamais faire échouer l'enregistrement de l'observation : la note prime sur son index, l'index se rattrape
- Le CA9 est le test le plus important de l'US : le rédiger avant l'implémentation
- Une note très longue est découpée comme n'importe quel document (US-098 / CA12) ; une note courte reste un fragment unique

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Retrouver une note ancienne
  Given une observation saisie l'an dernier sur la parcelle nord
  When le jardinier demande "qu'avais-je noté sur la parcelle nord l'an dernier ?"
  Then la note lui est restituée avec sa date et sa parcelle
  And le texte restitué est fidèle à ce qu'il avait écrit

Scénario: Mémoire et savoir général distingués
  Given une note du jardinier sur des limaces et une fiche générale sur les limaces
  When il pose une question sur les limaces
  Then la réponse distingue ce qu'il a noté de ce qui est vrai en général

Scénario: Aucune fuite de mémoire entre potagers
  Given une note privée du potager A
  When un membre du potager B pose une question qui correspond exactement à cette note
  Then aucun résultat issu du potager A ne lui est retourné

Scénario: Membre ayant quitté un potager
  Given un jardinier qui a quitté le potager A
  When il pose une question sur la mémoire de ce potager
  Then aucune note du potager A ne lui est accessible

Scénario: Observation corrigée
  Given une observation indexée puis corrigée par son auteur
  When une question la fait ressortir
  Then c'est le texte corrigé qui est restitué

Scénario: Potager archivé consultable
  Given un potager archivé contenant des observations
  When son propriétaire le consulte et interroge sa mémoire
  Then les notes lui sont restituées en lecture seule
```

**Labels GitHub :** `us`, `sprint-fiabilite-cout`, `rag`, `connaissance`, `isolation`
