# Plan de test manuel — parcourir tous les états de `routage_logs`

Ce document sert à **provoquer délibérément** chacun des états que la cascade
peut inscrire dans `routage_logs`, depuis le bot Telegram. Il ne remplace pas
les tests automatisés : il vérifie le câblage réel, avec le vrai modèle, la
vraie base et le vrai corpus — ce que `pytest` ne fait pas.

Deux colonnes portent l'essentiel, et elles répondent à deux questions
différentes :

| colonne | question à laquelle elle répond |
|---|---|
| `origine_classification` | **comment a-t-on su** de quelle nature était la demande ? |
| `etage_resolveur` | **qui a produit** la réponse finale ? |

Une même question peut être classée par une règle (gratuit) puis résolue par le
raisonnement (payant) — les deux colonnes ne se déduisent pas l'une de l'autre.

---

## 0. Préparer la session

```powershell
cd "C:\Users\eremy\OneDrive - SQLI\Documents\GitHub\assistant-potager"
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "dev"
python bot.py
```

Le cache de classification vit **en mémoire du processus** (TTL 24 h, 2000
entrées) : redémarrer `bot.py` le vide. Le cache de questions, lui, vit **en
base** (`questions_cache`) et survit au redémarrage. Pour repartir d'une
ardoise vraiment propre :

```sql
DELETE FROM questions_cache WHERE type_reponse = 'figee';
```

Requête de contrôle après chaque test — c'est elle qui fait foi, pas la console :

```sql
SELECT to_char(cree_le,'HH24:MI:SS') AS h, nature, origine_classification,
       etage_resolveur, cascade_remontee, issue_savoir, score_savoir,
       tokens_consommes, left(question_normalisee, 50)
FROM routage_logs ORDER BY cree_le DESC LIMIT 5;
```

---

## 1. `origine_classification` — trois états

### `regle` — un motif a suffi, zéro jeton

Aucun appel modèle. C'est le chemin le moins cher et le plus déterministe ;
c'est aussi lui qu'il faut surveiller, car une règle trop large aiguille une
question vers le mauvais étage sans que rien ne le signale.

Couples vérifiés contre la base dev le 04/09/2026 :

| nature visée | à taper au bot | ce qui déclenche |
|---|---|---|
| `ACTION` | `j'ai arrosé les tomates` | commence par un verbe d'action, sans `?` |
| `ACTION` | `/version` | commence par `/` |
| `QUESTION_SAVOIR` | `pourquoi mes tomates ont le cul noir ?` | marqueur « pourquoi mes » |
| `QUESTION_DATA` | `combien de tomates ai-je récolté ?` | marqueur « combien de » |
| `QUESTION_HYBRIDE` | `que dois-je faire pour mes courgettes ?` | marqueur « que dois-je faire » |

> **Piège d'ordre.** Les marqueurs sont évalués dans un ordre strict :
> HYBRIDE, puis SAVOIR, puis geste, puis DATA. « Que dois-je faire contre le
> mildiou ? » porte à la fois un marqueur HYBRIDE et un marqueur SAVOIR
> (« que faire contre ») — c'est HYBRIDE qui gagne. Pour tester SAVOIR par
> règle, éviter les formulations qui demandent un avis.

Le catalogue chiffré (US-096) produit aussi `regle` : `sur quelles parcelles je
trouve des tomates ?` est reconnu sans modèle et sans marqueur.

### `cache` — déjà classée récemment

Reposer **exactement la même question** que celle d'un test précédent, dans la
même session de `bot.py`. La normalisation ignore casse, accents et
ponctuation : « Pourquoi mes tomates ont le cul noir ? » et « pourquoi mes
tomates ont le cul noir » sont la même clé.

⚠️ Ne fonctionne que pour une question dont la classification est venue du
**modèle** : une question résolue par règle ne passe jamais par le cache — la
règle est plus rapide et matchera de nouveau.

> **Attention à l'homonymie.** `origine_classification = 'cache'` est écrit par
> **deux** chemins distincts :
> - le cache de **classification** (mémoire, TTL 24 h) — on sait de quelle
>   nature est la question, mais il reste à y répondre ;
> - le cache de **questions** (base, étage 0bis) — la réponse elle-même est
>   servie telle quelle.
>
> Ils se distinguent par `etage_resolveur` : `cache` pour le second, autre
> chose pour le premier.

### `modele` — la frange ambiguë, payante

Une formulation qu'aucune règle ne reconnaît. Elles se trouvent facilement en
écrivant comme on parle :

```
je récolte des carottes fourchu avec plusieurs pieds ?
sur mes pieds de chou je vois beaucoup de chenilles
comment tuteurer mes haricot grimpant ?
comment tailler un pommier ?
```

Le dernier surprend : « comment planter » et « comment semer » sont des
marqueurs, « comment tailler » n'en est pas un. La liste des marqueurs est
volontairement fermée et courte — chaque ajout élargit une règle qui aiguille
sans filet.

Contrôle : `tokens_consommes` inclut la classification, et la console montre
`🔌 LLM classification`.

---

## 2. `etage_resolveur` — quatre états

### `cache` — étage 0bis, réponse mémorisée, zéro jeton

**Poser deux fois la même question de savoir.** Le premier passage la mémorise
(`🧠 CACHE QUESTION │ mémorisé=figee`), le second la sert (`etage=cache`,
`tokens_consommes = 0`).

Si le second passage ne donne pas `cache`, la mémorisation a été **refusée** —
la console le dit, avec le motif. Trois refus existent, tous délibérés :

- le texte cite un nom propre du potager (parcelle, variété) — protection
  anti-fuite entre potagers ;
- le texte est une non-réponse du modèle (« je n'ai pas accès à… ») ;
- la question est datée (« hier », « la semaine dernière ») — sans réponse
  générale.

Ces trois-là sont des **refus** délibérés, annoncés par `⛔`. Ne pas les
confondre avec un **échec** d'écriture, annoncé par `⚠️ mémorisation impossible
(...)` : celui-là est un défaut, pas une décision. Il est rattrapé pour ne pas
faire perdre la réponse au jardinier, donc rien ne se voit côté Telegram — mais
la question repaie un appel modèle complet à chaque fois qu'on la repose.

### `donnee` — étage 1, la donnée du potager

```
combien de tomates ai-je récolté ?
quel est mon stock de courgettes ?
sur quelles parcelles je trouve des tomates ?
```

Suppose évidemment que le potager contienne les événements correspondants. Une
famille du catalogue qui matche mais ne trouve rien reste `donnee` : « je n'ai
aucune récolte de concombre enregistrée » **est** une réponse exacte, pas une
non-réponse. Seule l'absence de toute famille reconnue fait remonter la cascade
(`cascade_remontee = true`, `etage = raisonnement`).

### `savoir` — étage 2, le passage recopié, zéro jeton

⚠️ **Cet état est inatteignable avec le corpus livré.** Il exige *deux*
conditions simultanées :

1. `score_savoir >= RAG_SEUIL_CONFIANCE` (0.6 par défaut) — largement acquis,
   les scores observés vont de 0.77 à 0.98 ;
2. le passage de tête porte `niveau_confiance = 'verifie'`.

Or les 24 fiches sont en `a-valider`, replié sur `indicatif`. **C'est
volontaire** : `verifie` autorise l'application à servir le texte mot pour mot,
sans qu'aucun modèle ne le nuance — c'est un engagement de relecture phrase par
phrase, pas une case à cocher.

Pour exercer ce chemin, promouvoir **une** fiche relue :

```yaml
# dans la fiche .md, puis réingérer
niveau_confiance: "verifie"
```

```powershell
python tools/ingerer_connaissance.py --racine tests/corpus/corpus_agronomie_24_fiches
```

Puis poser une question que cette fiche couvre. Attendu : `etage=savoir`,
`issue_savoir=servi`, `tokens_consommes = 0` (hors classification), et la
réponse se termine par `_Source : Rédaction interne_`.

### `raisonnement` — étage 3, le modèle rédige

C'est l'état par défaut, et celui que tu obtiens aujourd'hui sur toutes les
questions de savoir. Trois chemins y mènent, distingués par `issue_savoir` :

| `issue_savoir` | signification | `cascade_remontee` |
|---|---|---|
| `transmis` | des passages ont été trouvés et **envoyés au modèle comme contexte** | `true` |
| `vide` | aucun passage — le modèle répond sans corpus | `false` |
| `NULL` | l'étage 2 n'a pas été consulté (question HYBRIDE, ou remontée depuis `donnee`) | selon le cas |

Pour obtenir `vide`, il ne suffit **pas** de citer une culture absente du
corpus : la requête plein texte est un OU, donc « comment planter un pommier ? »
ramène quand même 3 passages sur le verbe « planter ». Il faut une question dont
**aucun** mot porteur n'existe au corpus — vérifié :

```
c'est quoi la rouille du poireau ?          →  0 passage, issue = vide
comment planter un pommier ?                →  3 passages, issue = transmis
```

C'est la même mécanique que le trou de couverture décrit au § 4 : la recherche
ne se tait que si rien du tout ne matche.

Pour obtenir `NULL` avec remontée : une question HYBRIDE
(`à ton avis, que faire de mes courgettes ?`).

---

## 3. Matrice de couverture

Douze messages suffisent à parcourir tous les états. Les cocher dans l'ordre :

| # | à taper | `origine` | `etage` | `issue_savoir` |
|---|---|---|---|---|
| 1 | `/version` | `regle` | — (pas de cascade) | — |
| 2 | `j'ai arrosé les tomates` | `regle` | — (action) | — |
| 3 | `combien de tomates ai-je récolté ?` | `regle` | `donnee` | `NULL` |
| 4 | `sur quelles parcelles je trouve des tomates ?` | `regle` | `donnee` | `NULL` |
| 5 | `pourquoi mes tomates ont le cul noir ?` | `regle` | `raisonnement` | `transmis` |
| 6 | **rejouer le n° 5** | `cache` | `cache` | `NULL` |
| 7 | `c'est quoi la rouille du poireau ?` | `regle` | `raisonnement` | `vide` |
| 8 | `à ton avis, que faire de mes courgettes ?` | `regle` | `raisonnement` | `NULL` |
| 9 | `je récolte des carottes fourchu avec plusieurs pieds ?` | `modele` | `raisonnement` | `transmis` |
| 10 | **rejouer le n° 9 après redémarrage du bot** | `modele` | `cache` | `NULL` |
| 11 | *après avoir promu une fiche en `verifie`* — question couverte | `regle` | `savoir` | `servi` |
| 12 | **rejouer le n° 11** | `cache` | `cache` | `NULL` |

Le n° 10 mérite une explication : après redémarrage, le cache de
classification (mémoire) est vide, donc la question est **reclassée par le
modèle** — mais le cache de questions (base) la sert quand même. C'est
exactement le cas où `origine` et `etage` racontent deux histoires différentes,
et il vaut d'être vu au moins une fois.

---

## 4. Ce que ce plan ne teste pas

- **La justesse des réponses.** Un `etage=savoir` à 0.98 de confiance dit que
  la correspondance lexicale est bonne, pas que le contenu est vrai. Seule la
  relecture humaine le dit.
- **Les trous de couverture.** Quand aucune fiche ne répond, la recherche ne se
  tait pas : elle sert le passage le moins mauvais. « Comment planter des
  pommes de terre » a scoré 0.858 sans qu'aucune fiche ne traite la pomme de
  terre. C'est `GET /admin/savoir/lacunes` qui répond à cette question, pas un
  réglage de seuil.
- **Le mode dégradé** (429 Groq, modèle indisponible) : une cascade qui lève
  n'écrit rien dans `routage_logs`, par construction — aucune réponse n'a été
  servie, il n'y a rien à journaliser.
