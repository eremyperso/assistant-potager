**ID :** US-322
**Titre :** Ouvrir le suivi d'une culture depuis le plan
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(numéro à valider)*

**Story :**
En tant que jardinier
Je veux toucher une culture du plan et lire son histoire : d'où elle vient, ses étapes, ses notes, ce qui est attendu
Afin de suivre une culture de la graine à la récolte sans passer d'un écran à l'autre

**Contexte fonctionnel :**
Maquette de référence : `Plan - Pistes.html`, panneau de droite (ordinateur), écrans mobiles « 3 · Toucher une culture » et « 6 · Fiche culture ». C'est le **suivi d'une culture en place** — cette culture, sur ce rang. Il ne remplace pas la fiche culture d'US-207, qui reste la fiche **référentiel** d'une espèce.

**Contenu du suivi :**

| # | Bloc | Contenu |
|---|---|---|
| S1 | En-tête | emoji, nom, variété, quantité ; bouton Fermer (ordinateur) |
| S2 | Localisation | « Planche centrale, rang 3 — Voir la parcelle → », ou « pas encore placée » |
| S3 | Ligne de place | pieds, mètres occupés sur la longueur du rang, espacement, mètres libres ou « ⚠ +N » en dépassement ; absente si la place n'est pas calculable (lecture des places d'US-227) |
| S4 | Étape courante | étiquette d'étape (US-321) et sa date, « prévue le … » si prévue |
| S5 | Bandeau à confirmer | « Levée prévue aujourd'hui : à confirmer en notant », si l'étape est à confirmer |
| S6 | Action | un seul bouton **« Noter »** (« Noter la levée » sur mobile quand une étape est à confirmer) ; il ouvre Gaston (US-324) |
| S7 | Récolté | cumul de la saison (« 2,9 kg récoltés ») si la culture a été récoltée |
| S8 | Étapes | frise verticale : étapes passées datées, étape courante, prochaine étape avec sa date prévue ou son horizon (« vers fin novembre ») |
| S9 | Origine | **Pépinière · lot #18** (semé le…, godets, plantés) avec « Voir le lot → » vers sa fiche (US-216) ; **Achat** (texte libre) ; **Semis direct** (semé en place le …) |
| S10 | Notes | notes datées, les plus récentes d'abord, icône micro pour une note dictée |

**Dispositions :**
- **Ordinateur** : panneau de droite du plan ; un retour « ‹ Planche centrale » quand on y est venu depuis une parcelle (US-330)
- **Mobile** : feuille basse (S1, S2 + S3, S4, S5, S6, « Photo · bientôt disponible » désactivé, « Fiche », dernière note) ; « Fiche » ouvre le suivi complet en plein écran, comme la fiche calendrier (US-183)

**Critères d'acceptance :**
- [ ] CA1 : Toucher un segment de culture sur le plan, sur la liste mobile ou dans le détail d'une parcelle ouvre son suivi ; Échap ou Fermer le referme et rend le focus au segment
- [ ] CA2 : Les blocs S1 à S10 sont affichés dans cet ordre, chacun absent plutôt que vide quand sa donnée manque
- [ ] CA3 : L'origine distingue les trois cas ; le lien de lot ouvre « Ma pépinière » sur ce lot (US-195)
- [ ] CA4 : Une seule lecture serveur alimente le suivi (étapes, origine, notes, cumul, place) ; aucune règle n'est recalculée à l'écran
- [ ] CA5 : Le bouton Photo est visible, désactivé, annoncé « bientôt disponible » aux lecteurs d'écran
- [ ] CA6 : Un membre en lecture seule lit le suivi sans bouton « Noter »
- [ ] CA7 : Feuille mobile : cibles de 44 px, aucun défilement horizontal à 375 px
- [ ] CA8 : La fiche `data/connaissance/doc_app/parcelles-et-plan.md` décrit le suivi ; `pytest tests/test_us099_corpus_fonctionnement.py` reste vert
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375 px / 768 px / desktop ; vérification chrome-devtools à 375 px

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non (les liens geste → lot existent : `numero_lot`, `origine_graines_id`, `source_evenement_ids`) ; l'origine « Achat » est déduite d'une plantation sans lot
- Dépendances : **US-320** (étapes), **US-321** (étiquette d'étape) ; US-216 (fiche lot, livrée), US-227 (places, livrée)
- Modèle / effort conseillé : Sonnet 5.5, `medium`

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Suivre un chou de Bruxelles venu de la pépinière
  Given le chou de Bruxelles du rang 3 vient du lot #18
  When je touche son segment sur le plan
  Then le suivi affiche "Pépinière · lot #18" et "Voir le lot →"
  And l'étape "En récolte" depuis le 20 octobre
  And "2,9 kg récoltés"
  And ses trois notes, la plus récente en premier

Scénario: Une culture à confirmer sur mobile
  Given la levée des fèves est prévue aujourd'hui
  When je touche la fève dans la liste
  Then la feuille affiche le bandeau "à confirmer"
  And un seul bouton "Noter la levée"
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `plan`
