**ID :** US-335
**Titre :** Poser le plan sur une photo du potager vue du dessus
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(numéro à valider)*

**Story :**
En tant que jardinier
Je veux importer une photo de mon potager vu du dessus, la recaler sur trois repères et y poser mes parcelles
Afin que les allées, les haies et la maison apparaissent sans que j'aie à les dessiner

**Contexte fonctionnel :**
Maquette de référence : `Plan - Pistes.html`, « Fond atténué à 60 % », « Mettre en place le plan » et comparatif des pistes (coût de la piste C : **élevé** — import et stockage de la photo, recalage, rotation). La maquette laisse deux points ouverts : la **solution RGPD** de la photo (elle peut montrer la maison) et la **vue aérienne depuis l'adresse**, alternative à confirmer.

**Règles :**

| # | Règle |
|---|---|
| F1 | **Fond** : trois choix dans l'éditeur — Photo importée, Vue aérienne (si l'arbitrage la retient), Sans fond (grille neutre) |
| F2 | **Import** sur ordinateur uniquement ; formats image courants ; taille plafonnée ; la photo est **privée au potager** et visible de ses seuls membres |
| F3 | **Recalage en trois points** : le jardinier touche trois repères visibles sur la photo (coins de la serre, d'une planche) et donne leur position sur le plan ; l'échelle et l'angle du potager en découlent. Tant que trois points ne sont pas posés, l'éditeur l'indique (« 2 points posés sur 3 ») |
| F4 | **Opacité** : 30 %, 60 % (par défaut) ou 100 % ; les parcelles ont un contour blanc pour rester lisibles |
| F5 | **Plan en lecture** : bascule « Fond masqué | Fond 60 % » ; « Fond masqué » retombe sur la grille neutre (US-327) |
| F6 | Mobile : le mini-plan affiche le fond ; l'import n'y est pas proposé |
| F7 | Supprimer la photo retombe sur « Sans fond » sans toucher à la géométrie des parcelles |

**Critères d'acceptance :**
- [ ] CA1 : Un membre éditeur importe une photo, la recale en trois points et l'enregistre ; le plan en lecture la montre à l'opacité choisie
- [ ] CA2 : La photo est stockée selon la solution RGPD retenue, servie uniquement aux membres du potager authentifiés, supprimée avec le potager (purge US-084) et à la demande
- [ ] CA3 : Le recalage donne l'échelle et l'angle du potager (US-326) ; un recalage incohérent (points alignés, échelle aberrante) est refusé avec l'explication
- [ ] CA4 : « Fond masqué » et une photo absente ou illisible retombent sur la grille, jamais sur un écran vide
- [ ] CA5 : L'import n'est proposé ni sur mobile ni à un lecteur
- [ ] CA6 : Les conditions d'usage et la politique de confidentialité mentionnent la photo du potager ; le guide décrit l'import et le recalage ; corpus vert
- [ ] CA7 : Si l'arbitrage retient la vue aérienne : source, licence et coût sont documentés avant implémentation
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence en desktop et à 375 px (mini-plan)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : paramétrage (PWA ordinateur) et stockage de fichiers
- Migration BDD requise : **oui** — source du fond, points de recalage, opacité au niveau du potager
- Dépendances : **US-326**, **US-327**, **US-333**
- **Bloquée** par l'arbitrage **P2** (solution RGPD de la photo, annoncée par le responsable produit) ; la vue aérienne est un arbitrage séparé (P2 bis)
- Point de vigilance : premier stockage de fichier utilisateur de l'application — choix du stockage (disque du serveur Scaleway, objet), sauvegardes et purge à cadrer avec P2
- Modèle / effort conseillé : **Opus 5.5, `high`** — stockage de données personnelles, sécurité d'accès, calcul de recalage

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Recaler la photo du potager
  Given j'ai importé une photo de mon potager vue du dessus
  When je pose trois repères : deux coins de la serre et un coin de la planche centrale
  Then l'éditeur affiche "Recalage : 3 points posés sur 3"
  And le potager prend l'angle de −2,5° qui en découle

Scénario: Masquer le fond
  Given le plan s'affiche sur la photo à 60 %
  When je choisis "Fond masqué"
  Then le plan s'affiche sur la grille neutre
  And les parcelles gardent leur place
```

**Labels GitHub :** `us`, `backend`, `frontend`, `pwa`, `plan`, `rgpd`, `migration`
