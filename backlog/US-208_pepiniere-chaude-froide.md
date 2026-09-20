**ID :** US-208
**Titre :** Déclarer une pépinière chaude ou froide
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux dire si chacune de mes pépinières est chauffée ou non — ma mini-serre chauffante dans la véranda, mon châssis froid au fond du jardin
Afin que l'application ne traite pas pareil un semis de tomates en février au chaud et le même semis sous un châssis gelé, et qu'elle sache où mes plants s'endurcissent

**Contexte fonctionnel :**
Une parcelle peut être déclarée pépinière (`est_pepiniere`, migration v13) ; c'est un booléen. Les wireframes dessinent pourtant deux pépinières de nature différente — « SERRE » et « Châssis froid » (v2 § 3b) — et le jardinier en a souvent deux : une **pépinière chaude** pour démarrer tôt les cultures qui lèvent au chaud (tomate, poivron, aubergine), une **pépinière froide** pour les cultures rustiques (choux, poireaux, laitues) et pour **endurcir** les plants avant la mise en terre.

Le moteur de confiance connaît déjà ce manque : « Un semis en pépinière tient R2, R3 et R4 pour acquises : la pépinière non chauffée de février attend l'abri d'US-181 » (`docs/domaines/calendrier-cultural.md`).

Cette US ajoute le **type** de la pépinière et le rend déclarable et visible. Elle ne change encore aucun calcul : ses effets arrivent avec US-214 (endurcissement), US-219 (onglet Emplacements) et US-220 (confiance du semis) — arbitrage A17.

⚖️ Le type de pépinière n'est **pas** l'abri d'US-181 (voile, châssis, tunnel, serre), qui module la confiance des cultures **en place**. Une serre de production n'est pas une pépinière ; une pépinière chaude peut être une étagère d'intérieur. Deux attributs, deux sens, comme `est_pepiniere` et `abri` (US-181, point de vigilance).

**Critères d'acceptance :**
- [ ] CA1 : Une parcelle pépinière porte un **type** : *chaude* ou *froide*, **nullable** — « type non renseigné » est un état à part entière. Une parcelle qui n'est pas pépinière n'a jamais de type (contrainte en base). Aucun backfill : aucune pépinière existante n'est supposée chaude ou froide
- [ ] CA2 : Le type se déclare au bot par la commande existante : `/parcelle modifier <nom> pepiniere=chaude`, `pepiniere=froide`, `pepiniere=oui` (pépinière sans type, comportement actuel), `pepiniere=non` (qui retire aussi le type)
- [ ] CA3 : Il se déclare en une phrase, par la grammaire déterministe sans appel au modèle : « la serre est une pépinière chaude », « le châssis est une pépinière froide », « ma mini-serre est chauffée » quand la parcelle est déjà une pépinière. La phrase est récapitulée et confirmée avant d'être appliquée ; un nom de parcelle approchant est proposé, jamais substitué (US-172)
- [ ] CA4 : `/parcelle lister` affiche « pépinière chaude », « pépinière froide » ou « pépinière (type non renseigné) »
- [ ] CA5 : `GET /plan` et `GET /pepiniere/lots` exposent le type de chaque pépinière ; aucun champ existant n'est retiré ni renommé
- [ ] CA6 : La PWA l'affiche là où une pépinière apparaît — carte de la Vue plan (US-200 / V8), emplacement d'un lot (US-210) — sans jamais offrir de le corriger (RT1) ; « type non renseigné » est écrit, jamais remplacé par une supposition. L'assistant de premier potager (US-058) ne le demande pas
- [ ] CA7 : Le type ne change **aucun calcul** dans cette US — stock, occupation, confiance : un test le vérifie. Ses effets sont portés par US-214, US-219 et US-220
- [ ] CA8 : Le catalogue des commandes connaît les nouvelles valeurs de `pepiniere` (`FORMES_DICTABLES`, vocabulaire fermé) ; `controler_parite()` reste vert
- [ ] CA9 : La fiche `parcelles-et-plan.md` (section « Déclarer une serre ou une pépinière ») explique la différence entre pépinière chaude, pépinière froide et abri, avec des exemples du jardin, et le guide utilisateur (§ 21.4) est mis à jour (US-099 / CA9) ; `docs/domaines/migrations.md` décrit la migration
- [ ] CA10 : Des tests couvrent : chaque valeur de la commande, la phrase dictée, `pepiniere=non` qui retire le type, la contrainte « pas de type hors pépinière », l'exposition dans les deux lectures, l'absence d'effet sur les calculs

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement (parcelle)
- Migration BDD requise : **oui** — colonne nullable du type de pépinière sur `parcelles`, vocabulaire validé au point d'écriture, contrainte de cohérence avec `est_pepiniere`, rollback fourni. Numéro à lire dans `migrations/` au démarrage — dernier constaté : v48
- Dépendances : aucune bloquante
- Consommateurs : US-200 (carte de pépinière), US-210 (emplacement d'un lot), US-214 (endurcissement), US-219 (Emplacements), US-220 (confiance)
- Impact tokens : zéro
- Point de vigilance : « chaude » veut dire **chauffée ou à l'intérieur**, pas « exposée au soleil ». Une serre non chauffée plein sud reste une pépinière froide la nuit. La fiche d'aide le dit en une phrase
- Point de vigilance : coordination avec **US-181** (abri et paillage, non livrée) : si les deux US sont en cours ensemble, le vocabulaire et la commande `/parcelle modifier` sont revus une seule fois

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Déclarer une pépinière chaude par une phrase
  Given la parcelle "serre" est une pépinière sans type
  When le jardinier dicte "la serre est une pépinière chaude"
  Then le bot récapitule "serre : pépinière chaude" et demande confirmation
  When le jardinier confirme
  Then la serre est une pépinière chaude

Scénario: Déclarer une pépinière froide par la commande
  When le jardinier tape "/parcelle modifier châssis pepiniere=froide"
  Then le châssis devient une pépinière froide

Scénario: Retirer le statut de pépinière
  Given le châssis est une pépinière froide
  When le jardinier tape "/parcelle modifier châssis pepiniere=non"
  Then le châssis n'est plus une pépinière et n'a plus de type

Scénario: Type non renseigné affiché tel quel
  Given la pépinière "véranda" n'a pas de type
  When j'ouvre la Vue plan
  Then sa carte porte "type non renseigné"
```

**Labels GitHub :** `us`, `backend`, `bot`, `migration`, `pepiniere`, `parcelles`
