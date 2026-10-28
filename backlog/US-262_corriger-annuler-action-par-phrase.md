**ID :** US-262
**Titre :** Corriger ou annuler par une phrase ce qui vient d'être fait
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant que jardinier
Je veux dire « en fait c'était 3 rangs » ou « annule le dernier semis » juste après une action
Afin de réparer une erreur sans créer un second geste ni aller dans l'historique

**Contexte fonctionnel :**
Lot 2 du cadrage, §16.1 et C11 de l'étude d'articulation. Aujourd'hui, « en fait c'était 3 rangs » est pris pour un nouveau geste annoncé.

**Critères d'acceptance :**
- [ ] CA1 : Les outils `corriger_action(ref, champs)` et `annuler_action(ref)` existent et sont classés en écriture : ils produisent une **proposition** avec un récapitulatif avant → après.
- [ ] CA2 : L'exécution d'une correction passe par `evenements.corriger_evenement` (ou le service existant de la nature concernée).
- [ ] CA3 : Pendant 10 min après une action, l'agent passe **avant** le filtre « geste annoncé », pour qu'une phrase de correction ne devienne pas un nouveau geste.
- [ ] CA4 : Quand deux actions sont candidates, le compagnon demande laquelle en les nommant.
- [ ] CA5 : Un geste sans culture n'est jamais enregistré d'office.
- [ ] CA6 : Mesure du lot 2 : bonne action désignée ≥ 95 % ; 0 second geste créé sur une phrase de correction.
- [ ] CA7 : La fiche de `data/connaissance/doc_app/` sur la correction d'un geste est mise à jour.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement
- Migration BDD requise : non
- Dépendances : US-261, US-260
- Production conseillée : **Opus 5.5, effort `high`** — modifie l'ordre des étages de `handle_text` (zone qui a déjà régressé) et la frontière geste / correction.

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given le jardinier vient de confirmer "semis radis planche Sud 2 rangs"
When il écrit "en fait c'était 3 rangs"
Then le compagnon propose "Semis radis : 2 rangs → 3 rangs" à confirmer
And aucun nouveau semis n'est créé

When il écrit "annule le dernier semis"
Then le compagnon propose l'annulation de ce semis, exécutée seulement après confirmation
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `correction`
