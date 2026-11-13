**ID :** US-309
**Titre :** Chiffrer chaque appel d'après une grille tarifaire versionnée
**Épic :** ÉPIC 18 — Pilotage LLM

**Story :**
En tant qu'administrateur de la plateforme
Je veux que chaque appel porte son coût estimé, figé au tarif en vigueur le jour de l'appel
Afin de piloter un budget et de connaître le coût réel d'un jardinier avant de fixer un prix

**Contexte fonctionnel :**
Décisions D5 et D6. US-188 (ÉPIC 7, non livrée) prévoit déjà le coût en micro-euros entiers, le fournisseur et la version du tarif figée à l'écriture, pour le relevé BYOK. Cette US livre ces colonnes et cette règle en avance, pour les appels sur la clé de la plateforme ; US-188 s'appuiera dessus et gardera l'origine de la clé, l'identifiant de requête du fournisseur et la réconciliation avec une facture tierce.

**Critères d'acceptance :**
- [ ] CA1 : La migration v75 ajoute à `conso_tokens` : `fournisseur` (texte, nul), `cout_micro_eur` (entier, nul), `tarif_version` (texte, nul), avec son `rollback_v75.sql`.
- [ ] CA2 : `data/tarifs/tarifs_llm.json` décrit, par fournisseur et par modèle : unité, prix par million de jetons d'entrée, de sortie et en cache, ou prix par minute d'audio, ou par million de caractères ; devise ; date de relevé ; adresse de la page source ; identifiant de version de la grille.
- [ ] CA3 : La grille est lue au démarrage, jamais en ligne à l'appel ; une grille mal formée arrête le démarrage.
- [ ] CA4 : Le coût est calculé par la passerelle à l'écriture de la ligne, en entiers ; les jetons en cache sont comptés à leur tarif propre et retirés des jetons d'entrée au plein tarif.
- [ ] CA5 : Une ligne en échec sans jeton a un coût de 0 ; un modèle absent de la grille donne un coût nul (NULL) et une `tarif_version` renseignée, jamais un coût inventé.
- [ ] CA6 : Changer la grille ne modifie aucune ligne déjà écrite ; un test le vérifie.
- [ ] CA7 : Le coût est calculé au tarif public même si l'appel est servi par un palier gratuit ; la grille le dit en clair.
- [ ] CA8 : `tools/chiffrer_historique.py` rejoue le coût des lignes existantes d'après une grille donnée, en mode simulation par défaut, et marque les lignes rejouées par leur `tarif_version` ; il ne touche jamais une ligne déjà chiffrée.
- [ ] CA9 : Un test échoue si un modèle par défaut de `app/config.py` est absent de la grille.
- [ ] CA10 : Aucun prix n'est écrit de mémoire : chaque entrée de la grille porte sa source et sa date de relevé.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (passerelle LLM, données de référence)
- Cadrage : `docs/EPIC 18 - PILOTAGE LLM/CADRAGE_PILOTAGE_LLM.md` (numéro d'épic à valider)
- Migration BDD requise : oui (v75, numéro à confirmer)
- Dépendances : US-307 (unité)
- Décisions liées : D5, D6
- Le backlog d'US-188 est annoté : ses CA1 (colonnes de coût) et CA3 sont livrés ici.
- Conversion de devise : un taux fixe daté dans la grille ; pas d'appel à un service de change.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given la grille "2026-11" donne pour un modèle 0,10 € par million de jetons d'entrée, 0,30 € en sortie et 0,01 € en cache
When un appel consomme 8 000 jetons d'entrée dont 6 000 en cache et 50 jetons de sortie
Then cout_micro_eur vaut 275
And tarif_version vaut "2026-11"
When la grille "2026-12" double les prix
Then la ligne garde 275 et "2026-11"
```

**Labels GitHub :** `us`, `llm`, `cout`, `migration`
