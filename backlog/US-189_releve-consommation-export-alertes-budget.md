**ID :** US-189
**Titre :** Consulter et exporter le relevé de consommation de sa clé, avec alertes de budget
**Épic :** ÉPIC 7 — BYOK : la clé et le modèle du jardinier

**Story :**
En tant que propriétaire d'un potager ayant branché sa clé
Je veux voir dans les paramètres de mon potager ce que ma clé a servi, l'exporter, et être prévenu quand j'approche du budget que je me suis fixé
Afin de rapprocher ma facture, de garder la preuve, et de ne jamais être surpris par le montant

**Contexte fonctionnel :**
Sixième US de l'ÉPIC 7 (document d'épic §2.C et §6.4 ; « US-175 » dans sa numérotation initiale). Elle est la forme visible du journal d'US-188 : l'écran, les exports, et les alertes. Elle ne s'écrit qu'après le jalon de vérification d'US-188 / CA13.

⚖️ **Arbitrage tranché — alertes, pas de blocage (§2.C).** Budget mensuel indicatif saisi à la configuration, alertes à 50 / 80 / 100 %, sans plafond bloquant, sans coupe-circuit, sans limite de débit applicative. Deux conséquences assumées : une alerte a besoin d'un référentiel, donc le budget est un champ obligatoire à l'activation ; et l'application n'a alors **aucun frein dur** — seuls les plafonds du compte fournisseur arrêtent, ce qui fait de la clé dédiée une condition d'activation (US-187 / CA11). Point rouvrable : une fois le journal livré, un plafond bloquant est une condition avant l'appel, peu coûteuse ; cette US est structurée pour qu'il soit un ajout, jamais une reprise.

⚖️ **Le mois de référence est le mois calendaire UTC.** Les fournisseurs facturent en UTC. Afficher en heure locale et totaliser en local produirait chaque mois un écart de quelques appels entre le relevé et la facture — minuscule, systématique, et suffisant pour détruire la confiance. L'écran affiche en heure locale, totalise en UTC, **et l'écrit**.

**Critères d'acceptance :**

*Relevé*
- [ ] CA1 : Une section « Consommation de ma clé » dans les paramètres du potager, accessible au **propriétaire seul**, liste les lignes d'origine `potager` : date et heure (affichée en heure locale), fonction ayant déclenché l'appel, modèle réellement servi, tokens entrée / sortie, coût estimé, issue, référence fournisseur. La référence fournisseur est présente en colonne, jamais reléguée à un détail
- [ ] CA2 : Le relevé est paginé par mois calendaire UTC, avec le total du mois, le nombre d'appels et le nombre d'échecs ; le mois courant s'ouvre par défaut
- [ ] CA3 : La mention suivante figure sur l'écran, en toutes lettres : *« Coût estimé au tarif public de votre fournisseur en vigueur au <date>. Seule la facture émise par votre fournisseur fait foi. Ce relevé recense les appels émis par l'application avec votre clé ; il ne recense pas les appels que vous auriez émis par ailleurs avec la même clé. »* La dernière phrase est la première explication d'un écart légitime, et elle renvoie à la clé dédiée
- [ ] CA4 : Quand le fournisseur n'expose pas d'identifiant de requête, l'écran l'explique et indique que le rapprochement se fait par date, modèle et tokens
- [ ] CA5 : Un potager sans configuration ne voit pas la section ; un potager dont la configuration a été désactivée (US-192) voit encore son relevé passé

*Exports*
- [ ] CA6 : Un export CSV (colonnes brutes, pour tableur, horodatages en UTC ISO 8601) et un export PDF (relevé mensuel présentable) sont proposés par mois. Les deux portent la mention du CA3, la période en UTC, le total et le nombre d'appels
- [ ] CA7 : Un export « tout le relevé » existe, pour l'écran de suppression définitive d'US-192

*Budget et alertes*
- [ ] CA8 : Le budget mensuel de référence (saisi à la configuration, US-187 / CA2) est modifiable depuis cette section. Il est déclaratif et non bloquant, et l'écran le dit
- [ ] CA9 : Une alerte est envoyée à 50 %, 80 % et 100 % du cumul du mois UTC — par Telegram au propriétaire et par bandeau dans la PWA. **Une alerte par seuil et par mois** : le dernier seuil atteint est mémorisé et remis à zéro au changement de mois UTC
- [ ] CA10 : Le message à 100 % rappelle que l'application n'arrête rien et renvoie vers les plafonds du compte fournisseur. **Aucun blocage**, aucun appel refusé pour cause de budget
- [ ] CA11 : Le calcul du cumul se fait au moment de l'écriture de la ligne (US-188), pas par un balayage périodique : l'alerte part dans la minute qui suit le franchissement

*Rendu et tests*
- [ ] CA12 : Le rendu correspond visuellement à la maquette de référence à 375px / 768px / desktop ; le tableau tient dans son propre conteneur défilant en largeur, jamais la page. Composant avec `container-type: inline-size`
- [ ] CA13 : Des tests couvrent : totalisation en UTC (une ligne à 23h30 heure locale le 31 compte dans le bon mois), une alerte par seuil et par mois, remise à zéro au changement de mois, mention légale présente dans les deux exports, accès propriétaire seul, relevé encore visible après désactivation

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (paramètres PWA) | interaction Telegram (alertes)
- Migration BDD requise : **non** — le budget et le dernier seuil d'alerte sont portés par la table d'US-185
- Dépendances : **US-188** (journal, bloquante, jalon CA13 franchi), **US-187** (budget saisi), **US-185**
- Reprend d'US-143 : CA20 (l'écran)
- Impact tokens : zéro
- Conception : maquette à concevoir dans le projet Claude Design « potager 2026 » et à geler avant implémentation
- Point de vigilance : le coût estimé est une **estimation** au tarif figé sur chaque ligne (US-188 / CA3). Un tarif mis à jour dans le dépôt ne change aucun mois clos

**Notes techniques (pour Persona Developer) :**
- Endpoint de relevé paginé par mois UTC ; endpoints d'export CSV et PDF ; l'export PDF est généré côté serveur, sans appel réseau
- Le franchissement de seuil se calcule dans la même transaction que la ligne d'US-188 ; l'envoi Telegram est asynchrone et ne bloque pas la réponse

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Consultation du relevé
  Given un propriétaire dont la clé a servi douze appels ce mois-ci
  When il ouvre la section "Consommation de ma clé"
  Then il voit les douze lignes avec leur référence fournisseur
  And le total du mois en UTC avec la mention "seule la facture fait foi"

Scénario: Totalisation en UTC
  Given un appel émis le 31 à 23h30 en heure de Paris, soit le 31 à 21h30 UTC
  And un appel émis le 1er à 00h30 en heure de Paris, soit le 31 à 22h30 UTC
  When le relevé du mois suivant s'affiche
  Then aucun des deux appels n'y figure
  And l'écran indique que les mois sont comptés en UTC

Scénario: Une alerte par seuil et par mois
  Given un budget de 10 € et un cumul passant de 4,90 € à 5,10 €
  When la ligne est écrite
  Then une alerte "50 %" est envoyée par Telegram et affichée dans la PWA
  And un cumul passant ensuite à 5,30 € n'envoie rien

Scénario: Aucun blocage à 100 %
  Given un cumul dépassant le budget mensuel
  When le jardinier pose une question de raisonnement
  Then l'appel part normalement sur sa clé
  And le message d'alerte a rappelé que seuls les plafonds du fournisseur arrêtent

Scénario: Export mensuel
  Given un mois de relevé
  When le propriétaire exporte en CSV puis en PDF
  Then les deux fichiers portent la période UTC, le total, le nombre d'appels et la mention légale
```

**Labels GitHub :** `us`, `sprint-byok`, `llm`, `pwa`, `rgpd`
