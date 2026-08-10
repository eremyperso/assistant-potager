**ID :** US-054
**Titre :** Transformer le sélecteur de potager en menu de bascule et d'adhésion
**Épic :** ÉPIC 2 — Identité & accès

**Story :**
En tant qu'utilisateur membre d'un ou plusieurs potagers
Je veux retrouver la liste de mes potagers, en changer et rejoindre un nouveau potager depuis un seul menu déroulant
Afin de ne pas chercher cette fonction ailleurs que là où elle a toujours été, à côté du nom du potager dans le bandeau

**Contexte fonctionnel :**
Aujourd'hui (`PotagerSelector.jsx`, déclenché depuis `TopBar.jsx`), le nom du potager actif est un bouton texte qui ouvre une modale plein écran de sélection/adhésion — fonctionnalité déjà complète et fonctionnelle (logique portée par US-046 et US-048, toutes deux déjà implémentées côté services/API). Cette US ne change **aucune logique métier** : elle refond uniquement la présentation en un menu déroulant contextuel (`PotagerMenu` de la maquette), avec pour chaque potager listé son rôle, son nombre de parcelles et de membres. Voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §5.6.

**Critères d'acceptance :**
- [ ] CA1 : Le nom du potager actif dans le bandeau ouvre désormais un menu déroulant (et non plus une modale plein écran) listant tous les potagers de l'utilisateur, chacun avec son rôle, son nombre de parcelles et son nombre de membres, avec une coche/indicateur sur le potager actif
- [ ] CA2 : Le menu propose toujours, en bas de liste, « Rejoindre un potager » (saisie de code d'invitation) et « Tous mes potagers » — cette dernière option ouvrant la vue complète de bascule/comparaison quand l'utilisateur a plus d'un potager
- [ ] CA3 : Le nom du potager actif reste toujours visible dans le bandeau, y compris pour un utilisateur qui n'a qu'un seul potager — non-régression : c'est aussi le seul accès permanent à « rejoindre un potager par code » (cf. commentaire `[US-048 / CA4]` déjà présent dans `TopBar.jsx`)
- [ ] CA4 : Basculer vers un autre potager depuis ce menu recharge les données affichées sur le potager choisi, sans rechargement de page complet, avec le même comportement qu'aujourd'hui côté `PotagerContext`
- [ ] CA5 : Sur un écran étroit (mobile), le nom du potager actif se contraint à sa boîte disponible (troncature en ellipse) plutôt que de déborder ou de pousser les autres éléments du bandeau hors cadre
- [ ] CA type (US avec impact visuel/UI) : Le rendu du menu (fermé et ouvert) correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (portage UI d'une fonctionnalité existante, aucune nouvelle règle métier)
- Migration BDD requise : non
- Dépendances : US-052 (design system), US-053 (coquille applicative), US-046 (sélection potager actif — logique déjà implémentée), US-048 (rejoindre un potager par code — logique déjà implémentée)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Ouverture du menu potager
  Given un utilisateur membre de 2 potagers
  When il clique sur le nom du potager actif dans le bandeau
  Then un menu déroulant liste ses 2 potagers avec rôle, parcelles et membres, le potager actif étant coché

Scénario: Un seul potager reste visible
  Given un utilisateur membre d'un seul potager
  When il consulte le bandeau
  Then le nom de ce potager est affiché et reste cliquable pour ouvrir "Rejoindre un potager"

Scénario: Bascule de potager depuis le menu
  Given un utilisateur avec le menu potager ouvert
  When il sélectionne un autre potager que l'actif
  Then ce potager devient le potager actif et les écrans affichent ses données
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `multi-tenant`
