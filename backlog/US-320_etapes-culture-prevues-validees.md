**ID :** US-320
**Titre :** Suivre les étapes d'une culture, prévues puis validées
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(numéro à valider)*

**Story :**
En tant que jardinier
Je veux que chaque culture en place connaisse son étape — semée, levée, plantée, en croissance, en fleur, en récolte, terminée — et sache si cette étape est seulement prévue ou déjà vue
Afin que le plan me montre où en est chaque rang, et me dise ce qui est à confirmer aujourd'hui

**Contexte fonctionnel :**
Maquette de référence : `Plan - Pistes.html` (projet Claude Design « potager 2026 », piste C retenue), sections « Langage visuel commun » et « Une culture qui évolue : la fève du rang 6 ».

Aujourd'hui une culture n'a qu'une **phase** à trois valeurs (`semee`, `en_place`, `en_recolte`, US-194), déduite du dernier geste. La maquette remplace ce code par **sept étapes**, chacune **prévue** (d'après le calendrier de la culture, US-183 / recalage US-070) ou **validée** (un geste du jardinier, via le compagnon). C'est le socle de tout l'épic : plan, liste mobile, suivi de culture et cartes de Gaston lisent la même étape.

**Séquence d'étapes selon l'origine et le type de culture :**

| Origine | Type | Séquence |
|---|---|---|
| Semis direct en pleine terre | végétatif (carotte, radis, mâche) | Semé → Levé → En croissance → En récolte → Terminé |
| Semis direct en pleine terre | reproducteur (fève, haricot, pois) | Semé → Levé → En croissance → **En fleur** → En récolte → Terminé |
| Plant (pépinière ou achat) | végétatif (poireau, laitue, chou) | Planté → En croissance → En récolte → Terminé |
| Plant (pépinière ou achat) | reproducteur (tomate, courgette) | Planté → En croissance → **En fleur** → En récolte → Terminé |

**Règles :**

| # | Règle |
|---|---|
| E1 | Une étape porte : son code, sa date, son **statut** (`prevue` ou `validee`) et sa **source** (`jardinier`, `compagnon`, `calendrier`) |
| E2 | Une étape **prévue** vient du calendrier recalé de la culture (US-070, US-183). Faute de calendrier, aucune étape n'est prévue : l'étape courante reste la dernière validée |
| E3 | Une étape prévue dont la date est atteinte devient **« à confirmer »**. Elle n'avance jamais seule : seul un geste confirmé la valide |
| E4 | Les gestes existants valident les étapes correspondantes : `semis` → Semé, `levee` → Levé, `plantation` → Planté, première `recolte` → En récolte. Les étapes sans geste aujourd'hui — **En croissance**, **En fleur**, **Terminé** — gagnent leur geste ou leur enregistrement d'étape (arbitrage P3) |
| E5 | **Végétatif** : une récolte consomme les pieds. L'étape reste « En récolte » tant que des pieds restent ; la dernière récolte qui solde le stock, ou un arrachage, passe la culture à « Terminé » |
| E6 | **Reproducteur** : une récolte ne consomme pas les pieds. La première récolte ouvre « En récolte », les suivantes **s'ajoutent au rendement cumulé de la saison** sans changer l'étape ; seuls un arrachage, une perte totale ou « Culture terminée » mènent à « Terminé ». Le nombre de pieds actifs et le rendement cumulé restent deux mesures distinctes |
| E7 | « **Pas encore** » sur une étape à confirmer repousse le rappel de trois jours, sans rien valider |
| E8 | Une culture « Terminée » dont le rang n'est pas libéré est listée **« à libérer »** ; libérer le rang archive la culture et rend le rang libre |
| E9 | Aucune étape ne se calcule côté écran : `GET /plan` et la lecture du suivi de culture les fournissent toutes, à la date de référence (US-030) |

**Critères d'acceptance :**
- [ ] CA1 : Chaque culture en place expose, dans `GET /plan` et dans la lecture du suivi, son étape courante, son statut, sa date et la liste ordonnée de ses étapes (passées, courante, à venir avec leur date prévue si connue)
- [ ] CA2 : La séquence dépend de l'origine (semis direct / plant) et du type de culture (`type_organe_recolte`) ; « En fleur » n'apparaît que pour une culture reproductrice
- [ ] CA3 : Semis initial : un semis de fèves crée l'étape Semé validée, et une Levée prévue à la date du calendrier
- [ ] CA4 : Date prévue atteinte : la culture est « à confirmer » ; elle apparaît dans le compte « À confirmer » du plan
- [ ] CA5 : Première récolte d'un reproducteur : l'étape passe à « En récolte », le rendement cumulé démarre
- [ ] CA6 : N-ième récolte d'un reproducteur : l'étape ne change pas, le rendement cumulé s'additionne, le nombre de pieds actifs ne bouge pas
- [ ] CA7 : Récolte d'un végétatif : les pieds diminuent ; la récolte qui solde le stock passe la culture à « Terminé »
- [ ] CA8 : Fin de vie : un arrachage ou « Culture terminée » passe à « Terminé » ; la culture est listée « à libérer » jusqu'à la libération du rang
- [ ] CA9 : « Pas encore » repousse le rappel de trois jours sans écrire d'étape
- [ ] CA10 : La phase à trois valeurs d'US-194 reste fournie, dérivée des étapes, tant qu'un écran la lit encore ; aucun calcul existant (stock, rendement, confiance) ne change — test de comparaison avant / après
- [ ] CA11 : `docs/domaines/` gagne la description des étapes ; la fiche `data/connaissance/doc_app/parcelles-et-plan.md` (et celle du cycle de vie) explique au jardinier « prévue », « à confirmer » et « à libérer » ; `pytest tests/test_us099_corpus_fonctionnement.py` reste vert
- [ ] CA12 : Le bot Telegram accepte les nouvelles phrases d'étape (« les fèves sont en fleur », « culture terminée ») avec confirmation, comme les gestes existants

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement et analyse
- Migration BDD requise : **oui** — stockage des étapes validées (statut, source) et du report de rappel ; forme exacte selon l'arbitrage P3
- Dépendances : US-194 (phase, livrée), US-070 / US-183 (calendrier recalé, livrés), US-212 (levée, livrée)
- Arbitrage **P3 à trancher avant de démarrer** : liste des étapes par type de culture et leur source dans le référentiel ; enregistrement de « En croissance », « En fleur », « Terminé » par nouveaux types de geste ou par une table d'étapes
- Modèle / effort conseillé : **Opus 5.5, `high`** — chemin d'écriture, cycle de vie végétatif / reproducteur, et socle de tout l'épic

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: La fève du rang 6
  Given j'ai semé 40 fèves le 2 novembre sur la planche centrale
  And le calendrier prévoit leur levée le 12 novembre
  When nous sommes le 12 novembre
  Then la fève est à l'étape "Levé", statut prévu, "à confirmer"
  When je confirme la levée par le compagnon
  Then l'étape "Levé" est validée, source compagnon, datée du 12 novembre

Scénario: Récoltes successives d'un reproducteur
  Given mes haricots nains sont "En récolte" avec 30 pieds
  When je note une récolte de 800 g
  Then l'étape reste "En récolte"
  And le rendement cumulé de la saison augmente de 800 g
  And 30 pieds restent actifs

Scénario: Dernière récolte d'un végétatif
  Given il reste 5 laitues en place
  When je récolte les 5 laitues
  Then la culture passe à "Terminé"
  And elle est listée "à libérer"
```

**Labels GitHub :** `us`, `backend`, `bot`, `plan`, `cycle-de-vie`
