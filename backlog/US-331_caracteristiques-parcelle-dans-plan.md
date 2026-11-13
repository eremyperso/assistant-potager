**ID :** US-331
**Titre :** Lire et modifier les caractéristiques d'une parcelle dans le plan
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(numéro à valider)*

**Story :**
En tant que jardinier
Je veux lire et corriger le type, l'exposition, le sol, l'abri, le paillage et le type de pépinière d'une parcelle, sur ordinateur comme sur mon téléphone
Afin de tenir la fiche à jour sans quitter le plan, en sachant que les dimensions se règlent sur le plan lui-même

**Contexte fonctionnel :**
Maquette de référence : `Plan - Pistes.html`, onglet « Caractéristiques » (ordinateur en modification, mobile en lecture et en modification). C'est du **paramétrage, pas un geste** : l'écriture est directe, par le second chemin d'écriture d'US-230, comme aujourd'hui. Les observations d'entretien, elles, passent par « Noter ».

**Champs :**

| Champ | Lecture | Modification |
|---|---|---|
| Nom | valeur | saisie |
| Type | Planche, Bac, Butte, Serre, Châssis | liste (arbitrage **P7**) |
| Superficie, Longueur, Largeur | valeur et « **défini sur le plan** », verrouillées | jamais ici — « Ajuster sur le plan » |
| Nombre de rangs | valeur | saisie (hors pépinière) |
| Exposition | Sud, Est, Ouest, Nord, Mi-ombre | liste |
| Type de sol | Argileux, Limoneux, Sableux, Humifère, Terreau | liste |
| Abri | Aucun, Serre, Tunnel, Voile, Châssis vitré | liste |
| Paillage | Oui / Non | liste |
| Pépinière | Non, Froide, Chaude | liste (fusionne `est_pepiniere` et `type_pepiniere` d'US-208) |
| Statut | Active / Inactive, « se change avec Gaston » | jamais ici (US-332) |

**Règles :**
- Lecture par défaut ; « Modifier » passe la grille en saisie sur place ; **Annuler** ou **Enregistrer**
- Un champ manquant est signalé « Non renseigné · Compléter » et passe en saisie d'un toucher
- Sous la grille : « Les dimensions se règlent sur le plan. Ou dites à Gaston : `sol argileux pour planche centrale` », copiable
- Sous la grille, en lecture : le bouton « **Rendre inactive ou supprimer…** » (US-332)

**Critères d'acceptance :**
- [ ] CA1 : Les champs du tableau s'affichent et se modifient selon leur colonne ; superficie, longueur, largeur et statut ne sont jamais modifiables dans cet onglet
- [ ] CA2 : L'enregistrement passe par `PATCH /parcelles/{id}` (US-230) ; un membre en lecture seule ne voit pas « Modifier »
- [ ] CA3 : « Non renseigné · Compléter » ouvre la saisie sur ce champ, le focus dessus
- [ ] CA4 : Quitter l'onglet en cours de modification demande confirmation (comportement d'US-230)
- [ ] CA5 : La modification fonctionne au téléphone, dans la feuille plein écran d'une parcelle
- [ ] CA6 : Le champ « Pépinière » écrit les deux colonnes existantes de façon cohérente (Non → pas pépinière ; Froide / Chaude → pépinière et son type)
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375 px / 768 px / desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation et paramétrage
- Migration BDD requise : non, sauf si l'arbitrage **P7** crée le champ « type » (alors porté par US-326)
- Dépendances : **US-330** (détail de parcelle), **US-326** (géométrie verrouillée) ; US-229 / US-230 (livrées)
- Modèle / effort conseillé : Sonnet 5.5, `medium`

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Compléter le type de sol
  Given le type de sol de la planche centrale n'est pas renseigné
  When je touche "Non renseigné · Compléter"
  Then la grille passe en modification, le focus sur "Type de sol"
  When je choisis "Argileux" et j'enregistre
  Then "Type de sol : Argileux" s'affiche en lecture

Scénario: Dimensions verrouillées
  Given la planche centrale est posée sur le plan en 12 × 5 m
  When je passe en modification
  Then longueur, largeur et superficie restent en lecture, "défini sur le plan"
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `plan`
