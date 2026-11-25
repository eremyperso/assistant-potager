**ID :** US-357
**Titre :** Refaire l'écran de Gaston : plein écran mobile, panneau droit, carnet en Kalam, carte « À enregistrer »
**Épic :** ÉPIC 21 — Socle commun des vues

**Story :**
En tant que jardinier
Je veux parler à Gaston dans un écran clair, où ce que je dis apparaît comme dans mon carnet et où tout ce qui sera enregistré tient dans une seule carte à confirmer
Afin de vérifier d'un regard ce que Gaston a compris avant de valider

**Contexte fonctionnel :**
Vague 2 de l'ÉPIC 21. La référence est la maquette (Gaston via Noter, Ajouter une culture), détaillée au §3 de `docs/EPIC 21 - SOCLE COMMUN DES VUES/01_ANALYSE.md`.
`PanneauCompagnon` (US-271) est construit sur l'ancienne maquette `Compagnon.html`. Le fil, les propositions, la dictée (US-302), l'écoute (US-304), le contexte d'écran (US-323) et la file des gestes restent en place : **cette US change la forme, pas le moteur ni le chemin d'écriture.**

**Critères d'acceptance :**
- [ ] CA1 : **Ouverture** : sur mobile, Gaston occupe **tout l'écran** (feuille pleine hauteur, × pour fermer). Sur ordinateur, il s'ouvre dans le **panneau droit de 400 px** (US-353 CA12), à la place de la fiche, et le bouton Noter flottant est masqué
- [ ] CA2 : **En-tête** : visage de 38 px cerclé `brand`, « Gaston » en Lora 17 px, sous-titre « connaît votre potager et la météo » en `brand-text`, ×. Plus de Kalam dans l'en-tête (US-352 CA6)
- [ ] CA3 : **Contexte** : un bandeau `alt` sous l'en-tête (« 🫘 Fève · Planche centrale · rang 6 », × pour le retirer) remplace le style actuel d'US-323. Sans contexte, il n'est pas affiché
- [ ] CA4 : **Bulles** : celle de Gaston sur fond `alt`, avec le coin bas-gauche à 5 px et 88 % de large au plus. Celle du jardinier sur **papier crème, texte en Kalam**, avec le coin bas-droit à 5 px et la méta « 🎤 Dicté · 0:06 » (durée de la dictée) ou « ✎ Écrit ». Les messages déjà au fil (US-343) gardent leur origine dictée ou écrite
- [ ] CA5 : **Carte « À enregistrer »** : bord vert de 1,5 px, titre « À enregistrer » sur fond `brand-soft`. **Les propositions d'un même tour s'y affichent ligne par ligne** : pastille d'étape (hachurée si l'événement est prévu), « **Levée** · Fève, Planche centrale · rang 6 · aujourd'hui », et pour une note au carnet sa citation en Kalam. Boutons **Corriger** et **Confirmer** de 40 px
- [ ] CA6 : **Confirmer** confirme chaque proposition de la carte **par le chemin existant** (`POST /compagnon/propositions/{id}/confirmer`), une par une et dans l'ordre. Un échec partiel est dit sur la ligne concernée, et les lignes confirmées le restent. **Corriger** rend la main au champ de saisie, avec la carte toujours visible. Une destruction ne se confirme qu'au bouton (US-344). Aucune écriture sans Confirmer (test)
- [ ] CA7 : **Suggestions** : rangée de pilules de 34 px au-dessus de la saisie (le contenu vient d'US-358). Toujours en dernier : « Photo · bientôt », désactivé
- [ ] CA8 : **Saisie** : champ pilule de 44 px « Écrire à Gaston… » et **micro rond de 54 px** en dégradé `#5E9A2E → brand-deep`. Dictée (US-302), notes de dictée (empêchement ou information) et ligne « Écouter » (US-304) gardent leur comportement, au nouveau style
- [ ] CA9 : Les états existants restent rendus au nouveau style : réflexion en cours, fournisseur indisponible, mode Support, messages spontanés (US-267), commandes à confirmer
- [ ] CA10 : L'ancien style (`CarteProposition` à titre Kalam et bord pointillé, bulle à avatar) est retiré. `CarteProposition` devient la ligne de la carte « À enregistrer »
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction (compagnon PWA)
- Migration BDD requise : non
- Dépendances : US-353 ; US-271 (panneau compagnon), US-272 (état et messages spontanés), US-302/US-304 (dictée, écoute), US-323 (contexte), US-343 (fil complet), US-344 (écritures et cartes)
- Hors périmètre : le moteur du compagnon (actuel ou `COMPAGNON_MOTEUR=capacites`) ne change pas
- Modèle / effort conseillé : **Sonnet 5.5, `high`** — on retouche l'affichage du chemin de confirmation, et une carte mal reliée confirmerait la mauvaise proposition ; ni Opus ni Fable ne sont requis (le chemin lui-même ne change pas)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given Gaston est ouvert sur la fève, sur mobile
When le jardinier dicte "Les fèves pointent sur tout le rang, terre encore humide."
Then sa bulle s'affiche en Kalam sur papier crème avec "Dicté · 0:06"
And Gaston répond par une carte "À enregistrer" à deux lignes : "Levée · Fève, Planche centrale · rang 6 · aujourd'hui" et "Note au carnet"

When il touche "Confirmer"
Then les deux propositions sont confirmées l'une après l'autre par le chemin existant
And rien n'a été écrit avant ce geste

Given la confirmation de la note au carnet échoue
Then la ligne "Note au carnet" dit l'échec
And la levée reste enregistrée
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `compagnon`, `socle`
