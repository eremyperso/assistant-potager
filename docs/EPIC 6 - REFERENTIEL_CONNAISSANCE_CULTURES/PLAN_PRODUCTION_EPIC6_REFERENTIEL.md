# 📋 Plan de production — ÉPIC 6 (référentiel de connaissance) × moteur de réponses V2

> **Rédigé le :** 25/08/2026
> **Base :** branche `docs/backlog-moteur-reponses-us092-143` (commit `dda18a4`, 12 US) +
> `backlog/US-067`, `US-068` sur `main` (HEAD `09f4ca3`, 24/08/2026).
> **Complète :** `CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md`, qu'il **révise sur trois points**.
> **Convention :** ✅ fait établi · 🔶 hypothèse à valider · 🧪 à mesurer · ⚖️ arbitrage PO requis.

---

## 1. Ce que la lecture du backlog change

La déclinaison V2 en 12 US (US-092 → US-099, US-140 → US-143, **70 points**) est déjà écrite, et elle
est bonne. Elle intègre les six correctifs de la revue critique — routage règles-first, invalidation
événementielle du cache, `routage_logs` placée tôt, boucle 👍/👎, périmètre agronomique réduit à dix
cultures, licence tranchée avant rédaction.

**Trois recouvrements avec mon Épic 6 doivent être résolus avant de produire quoi que ce soit.**

| Mon US initiale | Recouvrement constaté | Décision |
|---|---|---|
| **US-166** — pipeline d'ingestion + traçabilité | **US-098** livre déjà les tables, la recherche FTS, l'isolation et **l'outil d'ingestion**. **US-140 / CA3-CA4** impose déjà source, licence et attribution affichée par document | ⛔ **Supprimée dans sa forme initiale.** Devient une US réduite à l'import du **référentiel structuré** (Wikidata, E-Phy → tables), en réutilisant l'outil d'US-098 — « aucun second mécanisme », comme le note US-140 |
| **US-160** — socle taxonomique et familles | **US-067** (5 pts, non livrée) porte déjà la famille botanique dans `culture_config`, pré-remplie et corrigeable depuis le bot | ⛔ **Supprimée.** Remplacée par un **amendement d'un CA** à US-067 (§3.1) |
| **US-140** (V2) vs **US-163** (Épic 6) | US-140 / CA5 fait porter aux fiches narratives « les associations favorables et défavorables, les principes de rotation » | ⚖️ **Amendement requis** (§3.2) — sinon deux vérités concurrentes |

**Épic 6 passe donc de 8 US / 52 points à 7 US / 44 points**, dont un simple amendement.

Et un constat qui vaut d'être dit : **le document de conception produit hier est, littéralement, le
livrable attendu par US-140 / CA2** — « la décision de source est un livrable de cette US, produit et
validé **avant** toute rédaction : liste des sources retenues, licence de chacune, ce qui est
réutilisable et à quelles conditions ». Il n'y a rien à réécrire : il se rattache à US-140 tel quel,
et lève par la même occasion le risque 🔴 de `EPIC_CALENDRIER_CULTURAL.md`.

---

## 2. Réponse à la question de séquencement, vérifiée cette fois sur les US réelles

Ma réponse précédente était juste dans le principe ; le backlog la confirme dans le détail.

| Épic 6 — US | Dépend de la cascade V2 ? | Pourquoi |
|---|---|---|
| US-067 amendée (famille + rotation) | **Non** | Donnée + pré-remplissage. Aucun appel LLM |
| US-161 (attributs de fiche) | **Non** | Colonnes nullables sur `culture_config` |
| US-163 (associations + rotation calculable) | **Non** | Tables de relation + jointure SQL |
| US-164 (`/fiche <culture>` au bot) | **Non** | Commande préfixée → étage 0, gabarit, 0 jeton |
| US-167 (avertissement à la plantation) | **Non** | Jointure déclenchée sur écriture d'événement |
| US-166b (import du référentiel structuré) | 🔶 **Partiel** | Réutilise l'outil d'ingestion d'US-098, mais peut être livré avant avec son propre script |
| US-162 (bioagresseurs) | **Non** pour les tables, **oui** pour l'exploitation | La relation culture × bioagresseur est du SQL ; le texte associé attend US-098 |
| US-165 (pré-diagnostic par symptômes) | **Oui** | Le rapprochement « mots du jardinier → terme technique » passe par la recherche FTS d'US-098 |

**Cinq des sept US de l'Épic 6 sont livrables sans qu'aucune des 12 US du moteur V2 ne soit
commencée.** Elles produisent des services déterministes complets — fiche culture, avertissement de
rotation, associations — accessibles par commande. Seule US-165 attend réellement US-098.

---

## 3. Trois amendements à soumettre au Persona PO avant de produire

Ils coûtent quelques lignes maintenant et évitent une migration rejouée plus tard.

### 3.1 US-067 — rendre la rotation *calculable*, pas seulement *affichable*

US-067 fait de la famille botanique une propriété de `culture_config` pour que les écrans la
**regroupent**. Rien n'y permet de **calculer** un conflit de rotation : il manque le délai de retour
par famille.

> **CA à ajouter :** la famille botanique porte un **délai de retour recommandé, exprimé en années**,
> pré-rempli pour les familles connues, nullable, et corrigeable depuis le bot au même titre que la
> famille elle-même. Une famille sans délai renseigné n'empêche aucun affichage : elle rend
> simplement l'avertissement de rotation indisponible pour cette culture.

**Impact :** +1 point sur US-067 (5 → 6). **Sans cet amendement**, US-163 devra rouvrir la migration
de `culture_config` — exactement le travers « migrations concurrentes » déjà signalé en Épic 5 §9.

⚖️ Sous-arbitrage : la famille reste-t-elle une **colonne texte** (le plus simple, cohérent avec le
CA4 de correction par le bot) ou devient-elle une **table de référence** ? Un délai de retour est un
attribut *de la famille*, pas *de la culture* : le porter en colonne le duplique sur chaque culture
de la famille et le rend incohérent à la première correction. **Recommandation : table de
référence**, décidée maintenant, tant qu'US-067 n'est pas implémentée.

### 3.2 US-140 / CA5 — appliquer aux relations la règle déjà appliquée aux dates

US-140 / CA7 est catégorique : *« les fiches ne contiennent aucune date, aucune fenêtre de semis,
aucune durée »*, motif — « dupliquer des dates dans les fiches créerait deux vérités concurrentes,
dont l'une serait fausse ». **Le raisonnement est exact, et il vaut mot pour mot pour les
associations et la rotation.**

Une association écrite dans une fiche est un texte : elle ne peut ni être jointe à l'historique
d'une parcelle, ni déclencher l'avertissement d'US-167. Écrite dans les deux endroits, elle devient
la deuxième vérité concurrente que CA7 interdit par ailleurs.

> **CA5 amendé :** retirer « associations favorables et défavorables, principes de rotation
> rattachés à la famille botanique » du contenu des fiches. Ces éléments relèvent du référentiel
> structuré (US-163). Les fiches conservent : maladies et ravageurs courants avec leurs symptômes,
> gestes courants d'entretien et de récolte.
>
> **CA à ajouter, symétrique de CA7 :** une fiche ne contient ni association, ni règle de rotation.
> Elle peut en revanche **expliquer** un mécanisme (« les solanacées épuisent le sol en… »), la
> relation elle-même restant portée par le référentiel.

**Impact :** US-140 s'allège. Le périmètre de dix cultures devient plus atteignable, ce qui sert
directement son arbitrage « dix cultures, pas trente ».

### 3.3 US-098 / CA2 — `culture` en référence, pas en libellé

`knowledge_chunks` porte `culture` comme métadonnée texte. C'est exactement l'erreur corrigée par
`migration_v12` sur `evenements.parcelle`. Une culture renommée depuis le bot orpheline
silencieusement ses fragments.

> **CA2 amendé :** la métadonnée de culture est une **référence** à `culture_config`, nullable.

**Impact :** nul si tranché avant l'implémentation d'US-098. Coûteux ensuite.

---

## 4. Le plan de production

### 4.1 Vélocité observée

Mesurée sur l'historique du dépôt, du 14/07 (US-040) au 24/08/2026 (US-091) : **~32 US fusionnées en
6 semaines**, soit **~5 US par semaine**, avec des livraisons groupées (US-074 à 078 le même jour,
US-080 à 084 également).

🔶 **Cette vélocité n'est pas transposable telle quelle à ce plan**, pour trois raisons qu'il vaut
mieux poser maintenant que découvrir au troisième jalon :

- Les livraisons groupées concernent des **écrans PWA** qui partagent un design system et se
  parallélisent bien. La cascade V2 touche `bot.py` et son état conversationnel — ce sont des US qui
  s'enchaînent, pas qui se groupent.
- **US-140 et US-164 comportent un travail éditorial**, qui n'accélère pas avec Claude Code.
  Rédiger dix fiches agronomiques relues par quelqu'un qui jardine se compte en soirées, pas en
  prompts.
- US-092 exige un **audit attestant qu'aucun appel direct au client Groq ne subsiste**. C'est un
  refactoring transverse sur ~1 300 lignes, avec un fort risque de régression sur les états de
  conversation — l'invariant projet le plus fragile.

**Hypothèse de planification retenue : 2 à 3 US par semaine sur ce périmètre.**
114 points / 19 US → **6 à 10 semaines**, éditorial inclus. 🧪 À réviser après la vague 1, qui sert
de calibrage.

### 4.2 Vague 0 — Préalables sans code (à lancer immédiatement, en parallèle)

Aucune ligne de code. C'est du travail de PO, et il **débloque** trois US.

| Action | Débloque | Effort |
|---|---|---|
| Trancher les 3 amendements du §3 | US-067, US-140, US-098 | 1 h |
| Trancher les 4 arbitrages (`CONCEPTION…CULTURES.md` §7.2) | US-140 / CA2, US-166b | 1 h |
| Lancer les 3 extractions SQL (§7.1) | US-140 / CA1 (les dix cultures), US-165 | 30 min |
| Rattacher le document de conception à US-140 / CA2 | **US-140 entière** | 15 min |
| Constituer le corpus de 30 questions de diagnostic (US-140 / CA11) — **avant** toute rédaction | US-140 / CA11-CA12 | 2 h |
| 🔶 Lire les conditions de `data.eppo.int` | US-162 | 30 min |

⚠️ Le corpus du CA11 doit être constitué **avant** les fiches, US-140 le dit explicitement. Le
constituer après produirait une mesure auto-réalisatrice.

### 4.3 Vague 1 — Rendre la cascade mesurable (V2 uniquement) — 13 pts, 3 US

| Ordre | US | Pts | Pourquoi ici |
|---|---|---|---|
| 1 | **US-092** Passerelle LLM unique | 5 | Conditionne les onze suivantes. Rien de perceptible pour le jardinier, tout pour la suite |
| 2 | **US-093** Routeur règles-first | 5 | Aiguillage de toute la cascade |
| 3 | **US-097** Observabilité + retour 👍/👎 | 3 | **Ne pas la repousser.** Sans point de comparaison *avant*, aucune des vagues suivantes ne pourra démontrer son gain |

🧪 **Jalon de décision.** À l'issue de cette vague, `routage_logs` livre la répartition réelle par
étage, à confronter aux hypothèses 40 / 35 / 20 / 5 du document d'architecture. Si la part des
questions de **savoir** est nettement supérieure à 20 %, l'Épic 6 doit remonter dans la priorité —
et inversement.

### 4.4 Vague 2 — Deux pistes en parallèle — 47 pts, 8 US

C'est le cœur du plan : **la piste B ne dépend d'aucune US de la piste A**. Elles peuvent alterner
selon l'envie et la fatigue — backend le soir, données le week-end.

**Piste A — déterministe sur les données (V2)**

| Ordre | US | Pts | Gain |
|---|---|---|---|
| 4 | **US-096** Gabarits sur agrégats SQL | 5 | Les questions chiffrées sortent du LLM |
| 5 | **US-095** Cache à invalidation événementielle | 5 | Dépend d'US-096 pour le recalcul |
| 6 | **US-094** Parseur déterministe des saisies | 8 | ≥ 50 % des saisies sans LLM. Rend le mode dégradé vivable |

**Piste B — référentiel structuré (Épic 6) — aucune dépendance V2**

| Ordre | US | Pts | Gain |
|---|---|---|---|
| B1 | **US-067 amendée** Famille botanique + délai de retour | 6 | Prérequis d'US-140 et d'US-163 |
| B2 | **US-166b** Import du référentiel structuré + `referentiel_source` | 5 | Wikidata (CC0) et E-Phy (Licence Ouverte) en base |
| B3 | **US-161** Attributs agronomiques de fiche | 5 | Le contenu de la fiche courte |
| B4 | **US-164** `/fiche <culture>` au bot | 5 | **Premier gain visible, 0 jeton.** À placer là, pas plus tard |
| B5 | **US-163** Associations + rotation calculable | 8 | Le graphe |
| B6 | **US-167** Avertissement à la plantation | 5 | L'application prévient *avant* l'erreur |

**Recommandation d'ordonnancement :** intercaler B4 dès que B3 est livrée, même si la piste A est en
cours. Après cinq semaines de plomberie invisible, `/fiche tomate` qui répond instantanément est ce
qui maintient l'envie de continuer. C'est une raison de planification, pas une raison technique —
elle n'en est pas moins sérieuse pour un projet mené seul.

### 4.5 Vague 3 — Le savoir — 34 pts, 5 US

| Ordre | US | Pts | Note |
|---|---|---|---|
| 7 | **US-098** Socle de connaissance + FTS | 8 | Le contenant. Appliquer l'amendement §3.3 |
| 8 | **US-099** Corpus de fonctionnement de l'application | 5 | Éditorial sans risque de licence, sujet parfaitement maîtrisé. **Sert de rodage** au format et à l'outil d'ingestion avant l'agronomie |
| 9 | **US-162** Bioagresseurs + relation culture × bioagresseur | 8 | Épic 6. Structure + import E-Phy |
| 10 | **US-140 amendée** Corpus agronomique, dix cultures | 8 | Éditorial. Allégé par l'amendement §3.2 |
| 11 | **US-165** Pré-diagnostic déterministe par symptômes | 8 | Épic 6. Consomme US-098 (FTS) et US-162 (relations) |

⚠️ US-099 avant US-140 n'est pas une préférence : c'est ce que dit US-099 elle-même, et le motif est
bon — roder l'outil sur un sujet sans aléa avant de l'appliquer au sujet qui en porte un.

⚠️ **US-099 / correction relevée dans son propre texte :** le guide utilisateur que deux documents de
conception citent comme existant **n'est pas dans le dépôt**. Le corpus est donc à écrire, pas à
ingérer. C'est cohérent avec ce que je demandais au §7.3 de la conception — la réponse est : ce
fichier n'existe pas, il faut le produire.

### 4.6 Vague 4 — Raisonnement et capacité — 13 pts, 2 US

| Ordre | US | Pts | Note |
|---|---|---|---|
| 12 | **US-142** Conseil personnalisé multi-sources | 5 | L'étage 3. Devient réellement utile une fois les vagues 2 et 3 livrées : sans elles, il n'a rien à assembler |
| 13 | **US-143** Brancher sa propre clé | 8 | Triviale après US-092. À placer quand un besoin réel apparaît — capacité, pas fonctionnalité |

**Hors périmètre de ce plan mais à ne pas perdre de vue :** US-141 (mémoire du potager, 5 pts) et
l'Épic 5 (US-068 → US-070, 21 pts). US-141 se glisse n'importe où après US-098. L'Épic 5 se glisse
après US-067 amendée, dont il partage la table.

### 4.7 Vue d'ensemble

```
VAGUE 0   préalables sans code ─────────────────────────────────────┐
          (amendements, arbitrages, extractions SQL, corpus CA11)   │
                                                                    ▼
VAGUE 1   US-092 ──► US-093 ──► US-097          13 pts    🧪 JALON DE DÉCISION
          passerelle  routeur   mesure                    la mesure réoriente la suite
                │                                                   │
     ┌──────────┴──────────────────────┐                            │
     ▼ PISTE A (V2)                    ▼ PISTE B (ÉPIC 6)           │
VAGUE 2                                                             │
     US-096 ──► US-095 ──► US-094      US-067' ─► US-166b ─► US-161 │
     gabarits   cache      parseur            └──► US-164  ◄────────┘
                                                    │      premier gain visible
                                              US-163 ──► US-167
     18 pts                                   29 pts
     └──────────────────┬──────────────────────────┘
                        ▼
VAGUE 3   US-098 ──► US-099 ──► US-162 ──► US-140' ──► US-165       34 pts
          socle      doc app    bioagr.    agronomie   diagnostic
                        │
                        ▼
VAGUE 4   US-142 ──► US-143                                          13 pts
          conseil     BYOK

TOTAL : 19 US · 114 points · 🔶 6 à 10 semaines à 2-3 US/semaine
```

---

## 5. Risques de planning

| Risque | Niveau | Traitement |
|---|---|---|
| **US-092 casse les états de conversation** — refactoring transverse de `bot.py`, l'invariant le plus fragile du projet | 🔴 Élevé | La livrer **seule**, sans autre US en vol. Tests de non-régression sur les modes de correction et le mode `ask` **avant** de la fusionner. C'est l'US où le « une seule US à la fois » n'est pas négociable |
| **L'éditorial d'US-140 s'étire** — dix fiches relues, ce n'est pas du développement | 🟡 Moyen | Périmètre déjà réduit par l'US. L'amendement §3.2 l'allège encore. Livrer par lots de trois cultures plutôt que d'attendre les dix |
| **Les amendements du §3 sont arbitrés trop tard** | 🟡 Moyen | Vague 0. Après l'implémentation d'US-067 ou d'US-098, ils deviennent des migrations rejouées |
| **La mesure de la vague 1 invalide les hypothèses** | 🟢 Faible, et c'est le but | Le plan est conçu pour cela : le jalon §4.3 réordonne les vagues 2 et 3 au lieu de les subir |
| **Deux pistes en parallèle → conflits de migration** sur `culture_config` | 🟢 Faible | Piste A ne touche pas `culture_config`. Épic 5 (US-068), si intercalé, doit être séquencé avec US-067 amendée |
| **Le travail de source d'US-140 / CA2 est déjà fait mais non rattaché** | 🟢 Faible | Action de la vague 0, 15 minutes |

---

## 6. À faire dans les 48 heures

1. **Trancher les trois amendements du §3** — c'est la seule chose qui périme.
2. **Rattacher `CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md` à US-140 / CA2** et le référencer
   dans `docs/00_INDEX_NAVIGATION.md`.
3. **Fusionner la branche `docs/backlog-moteur-reponses-us092-143`** si elle est validée — elle est
   ouverte depuis un moment et le reste du backlog évolue sur `main`.
4. **Lancer les trois extractions SQL** — elles conditionnent le CA1 d'US-140 (quelles dix cultures)
   et la table `symptome` d'US-165.
5. **Créer les 7 US de l'Épic 6 renumérotées** via l'Orchestrateur-US, en respectant la note de
   numérotation d'US-140 : la bande 100-133 reste réservée, l'Épic 6 prend **US-160 à US-167**, sans
   collision avec la bande 140+.
6. **Démarrer US-092, seule.**
