**ID :** US-070
**Titre :** Recaler le calendrier cultural sur les événements réels de la parcelle

**Story :**
En tant que jardinier
Je veux que le calendrier affiché pour une culture déjà en terre parte de la date à laquelle je l'ai réellement semée
Afin de savoir où en est cette culture et dans combien de temps je la récolte, au lieu de relire une période conseillée que j'ai déjà dépassée

**Contexte fonctionnel :**
US-068 constitue le référentiel : fenêtres conseillées et durées attendues entre le semis, la levée et la récolte. Utile en planification — « qu'est-ce que je peux semer ce week-end ? » — mais sans valeur devant une parcelle où la culture est déjà en place : le jardinier a semé, il sait quand. La seule question qui reste est *où en est cette culture, et quand est-ce que je récolte*.

Cette US répond à cette question en **recalant** le calendrier sur les événements réels. Le semis du 12 avril devient l'origine ; la levée et la récolte attendues se déduisent des durées du référentiel appliquées à cette date, et non plus des mois conseillés génériques. Une courgette semée en pleine terre le 12 avril, référentiel à 10 jours jusqu'à la levée et 95 jours jusqu'à la récolte, affiche une levée attendue autour du 22 avril et une récolte à partir du 16 juillet — pas « récolte de juin à octobre », qui est vrai pour la courgette en général et faux pour celle-ci.

Le recalage fait apparaître un état que la maquette 2026 n'a pas : entre la levée et la première récolte, la culture n'est ni semée ni récoltée, elle **pousse**. La frise gagne donc un quatrième état, neutre, distinct de « rien de prévu ce mois-ci ».

**L'application sait déjà presque tout faire.** Les dates réelles de `semis`, `mise_en_godet`, `plantation` et `recolte` sont en base, et le chaînage `semis → godet → plantation` existe (`origine_graines_id`, `source_evenement_ids` — US-029, US-065, US-066). Aucune saisie nouvelle n'est demandée au jardinier : cette US calcule et affiche, elle n'enregistre rien.

**Critères d'acceptance :**

*Ancrage sur le réel*
- [ ] CA1 : Pour une culture en place dans une parcelle, l'application détermine son **événement d'origine réel** : le semis en pleine terre, ou — pour un itinéraire pépinière — le semis en godet dont découle la plantation, retrouvé par le chaînage existant
- [ ] CA2 : La **levée attendue** et la **première récolte attendue** sont calculées depuis la date de cet événement d'origine et les durées du référentiel (US-068), et non depuis les fenêtres conseillées génériques
- [ ] CA3 : La **durée restante** avant la première récolte attendue est affichée en clair, exprimée en jours. Quand la durée du référentiel est une fourchette, le reste à courir l'est aussi — jamais présenté comme une date certaine
- [ ] CA4 : Quand la culture relève d'un itinéraire pépinière et que la plantation a déjà eu lieu, la projection tient compte de la date réelle de plantation si elle s'écarte du délai de repiquage conseillé — c'est le calendrier du jardinier qui fait foi, pas celui du référentiel
- [ ] CA5 : Dès qu'une **récolte réelle** est enregistrée sur cette culture, la frise reflète le réel plutôt que l'attendu : la période de récolte démarre à la première récolte constatée
- [ ] CA6 : La projection respecte le type d'organe de récolte : pour une culture **végétative**, la récolte est terminale et clôt la frise ; pour une culture **reproductrice**, elle s'étale et se poursuit jusqu'à la fin de la fenêtre conseillée ou jusqu'à la dernière récolte constatée

*Affichage*
- [ ] CA7 : La frise des douze mois distingue **quatre états** : semis, en croissance, récolte, et rien de prévu. L'état « en croissance » couvre la période entre la levée et la première récolte attendue
- [ ] CA8 : Le **mois mis en évidence** sur la frise suit la **date de référence** de l'écran (US-030/031) et non l'horloge du navigateur. Quand le jardinier recule la date de référence, toute la frise et la durée restante se replacent à cette date — sans quoi l'écran serait dans le passé et la frise dans le présent
- [ ] CA9 : Quand la fenêtre de semis conseillée n'est pas terminée à la date de référence, la **prochaine plage de semis possible** est indiquée — c'est ce qui permet d'échelonner une deuxième série

*Cas limites*
- [ ] CA10 : Quand plusieurs semis échelonnés de la même culture coexistent dans la parcelle, la projection porte sur **le plus ancien encore en place** — celui qui se récolte en premier — et l'existence des séries suivantes est signalée. Les séries ne sont jamais fusionnées en une projection moyenne
- [ ] CA11 : Sans référentiel pour cette culture (US-068 non renseignée), la frise reste **neutre** et la durée restante en tiret. Sans contexte de semis connu (US-069), l'itinéraire n'est pas deviné : les fenêtres conseillées génériques s'affichent sans recalage. **Aucune date ni durée n'est jamais inventée**
- [ ] CA12 : Aucun écran n'est bloqué ni en erreur par une culture sans historique exploitable, sans date de semis, ou dont la récolte attendue est déjà dépassée sans récolte constatée — ce dernier cas est affiché comme tel plutôt que masqué
- [ ] CA13 : Aucune régression : cette US ne modifie aucun événement, aucun calcul de stock, aucune statistique existante. Elle lit et projette
- [ ] CA14 : Des tests couvrent le recalage sur semis en pleine terre, le recalage via chaînage pépinière, la plantation décalée du CA4, la bascule sur récolte réelle du CA5, la différence végétatif/reproducteur du CA6, le suivi de la date de référence du CA8, les semis échelonnés du CA10 et les deux modes dégradés du CA11

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (calcul et affichage, aucune écriture)
- Migration BDD requise : **non** — cette US n'ajoute aucune donnée, elle projette celles qui existent
- Dépendances : **US-068** (référentiel des durées et fenêtres, bloquante), **US-069** (contexte de semis, nécessaire pour choisir l'itinéraire ; sans elle le mode dégradé du CA11 s'applique), US-029 / US-065 / US-066 (chaînage, déjà livrées)
- Consommateurs : écran **Plan** (US-060), vue « Cultures » du **Lot E**
- Impact design system : le composant de frise des douze mois (`components/ui/MonthStrip.jsx`, US-052) doit accueillir le quatrième état du CA7 et recevoir le mois mis en évidence en paramètre au lieu de le lire sur l'horloge (CA8). C'est une **évolution du composant partagé** — à traiter comme telle, tous ses usages en héritent
- Point de vigilance : ne jamais présenter une projection comme une certitude. Le vocabulaire d'interface doit rester au conditionnel (« récolte attendue »), une fourchette doit rester une fourchette
- **Amendement d'US-068 du 15/09/2026 — fenêtre de plantation.** Le référentiel porte désormais une fenêtre de **plantation** par zone. Deux conséquences ici : (1) une culture **plantée sans semis connu** (plants achetés, ail, pomme de terre) n'est plus sans référence — son mode dégradé du CA11 affiche au moins la fenêtre de plantation conseillée ; (2) le CA7 compte désormais **cinq** états possibles sur la frise (semis, plantation, en croissance, récolte, rien de prévu), à articuler avec la règle de priorité d'US-176 / CA3bis. ⚠️ Projeter une récolte **depuis une plantation** exige une durée plantation → première récolte que le référentiel n'a pas : point ouvert d'US-068, à trancher avant de chiffrer à nouveau cette US
- **Avancement du 15/09/2026 — implémentée (v3.65.0), en revue.** Projection serveur dans `app/services/recalage_calendrier.py` (lecture seule), servie par `GET /plan/calendriers?date_ref=…` (bloc `projections`), affichée par la tuile de l'écran Plan (`lib/calendrier.js`, `MonthStrip` prop `croissance`). Tests : `tests/test_us070_calendrier_recale.py` (38, couverture 97 %) et `frontend/src/lib/calendrier_recale.test.js` (11). Rendu vérifié à 375 / 768 / 1280 px sur la base de dev. Arbitrages pris en implémentation, à relire :
  - **Origine = semis seulement.** Une plantation sans semis chaîné n'est pas projetée (point ouvert tranché par US-177) : la tuile garde la frise conseillée, plantation comprise, et dit « planté le … ».
  - **Filière du semis (CA11).** Un semis sans `contexte_semis` n'est pas recalé ; un semis chaîné à une mise en godet compte comme pépinière — même preuve que la reprise de `migration_v47`. Le contexte dit l'emporte, même incohérent avec le chaînage.
  - **Durée absente.** Sans durée `recolte` chiffrée (absente ou « vivace »), pas de recalage. Sur la base de dev : 2 tuiles recalées sur 35, 17 faute de durée (tomate, poivron…).
  - **CA4.** Le décalage se mesure au bord le plus proche de la fourchette de repiquage ; sans durée de repiquage, aucun décalage.
  - **CA6.** Une reproductrice ne s'étale jusqu'à la fin de la fenêtre de récolte que si sa récolte commence DANS cette fenêtre.
  - **CA7.** « En croissance » part de la levée attendue, ou du lendemain du semis sans durée de levée, et ne chevauche aucun autre état. Teinte `bg-brand-soft` cerclée de `ring-brand` : sur le fond de tuile, la teinte seule était invisible. La maquette d'US-060 ne porte pas cet état — écart non validé contre une maquette.
  - **CA10.** Horizon d'une série : 365 jours. Une récolte va à la plus ancienne série ouverte qui la précède ; en végétatif elle la clôt. Une récolte sans parcelle n'est rattachée que si la culture n'est en place que dans une seule parcelle.
  - **Corpus d'aide.** Une question contenant « récolter » est aiguillée vers la fiche des récoltes (type de fiche) : les deux questions ajoutées au corpus l'évitent. Limite du moteur de recherche, pas de la fiche.
- Point laissé ouvert : les alertes et rappels dérivés de ces projections (« ta courgette est récoltable depuis 5 jours ») relèvent du module « À faire cette semaine » du **Lot D**, pas de cette US

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Recalage sur un semis en pleine terre
  Given une courgette semée en pleine terre le 12 avril
  And un référentiel indiquant 10 jours jusqu'à la levée et 95 jours jusqu'à la récolte
  When le jardinier consulte cette parcelle le 15 juin
  Then la levée attendue est affichée autour du 22 avril
  And la première récolte attendue est affichée autour du 16 juillet
  And la durée restante affichée est d'environ 31 jours

Scénario: Quatrième état sur la frise
  Given la même courgette consultée le 15 juin
  When la frise des douze mois s'affiche
  Then avril est marqué comme mois de semis
  And mai et juin sont marqués comme période de croissance
  And juillet à octobre sont marqués comme période de récolte

Scénario: Recalage via la filière pépinière
  Given une tomate semée en godet le 15 mars puis plantée en parcelle le 10 mai
  When le jardinier consulte cette parcelle
  Then la projection part du semis du 15 mars
  And elle tient compte de la plantation réellement faite le 10 mai

Scénario: Bascule sur la récolte réelle
  Given une courgette dont la première récolte était attendue le 16 juillet
  And une récolte réellement enregistrée le 8 juillet
  When le jardinier consulte cette parcelle
  Then la période de récolte affichée démarre au 8 juillet

Scénario: Culture végétative, récolte terminale
  Given une laitue, culture végétative, dont la récolte est attendue en juin
  When le jardinier consulte sa frise
  Then la période de récolte ne se prolonge pas au-delà de la récolte attendue

Scénario: La frise suit la date de référence
  Given une culture consultée avec une date de référence reculée au 15 mars
  When la frise s'affiche
  Then le mois mis en évidence est mars
  And la durée restante est celle calculée au 15 mars

Scénario: Semis échelonnés
  Given deux semis de haricot dans la même parcelle, l'un du 2 mai et l'autre du 30 mai
  When le jardinier consulte cette parcelle
  Then la projection affichée est celle du semis du 2 mai
  And l'existence d'une seconde série est signalée

Scénario: Culture sans référentiel
  Given une culture "topinambour" sans fenêtre ni durée renseignée
  When le jardinier consulte la parcelle qui la contient
  Then la frise reste neutre
  And la durée restante est affichée en tiret

Scénario: Récolte attendue dépassée
  Given une culture dont la récolte était attendue il y a 15 jours, sans aucune récolte enregistrée
  When le jardinier consulte cette parcelle
  Then l'écart est affiché explicitement
  And la culture n'est ni masquée ni traitée comme terminée
```

**Labels GitHub :** `us`, `frontend`, `backend`, `cultures`, `plan`
