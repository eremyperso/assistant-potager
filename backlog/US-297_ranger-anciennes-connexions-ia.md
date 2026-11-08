**ID :** US-297
**Titre :** Ranger les anciennes connexions d'assistants IA sous un lien repliable
**Épic :** ÉPIC 16 — Potager dans les assistants IA (MCP) *(numéro à valider, voir `docs/EPIC 16 - POTAGER DANS LES ASSISTANTS IA/ETUDE_MCP_POTAGER.md`)*

**Story :**
En tant que jardinier
Je veux que l'écran « Assistants connectés » ne me montre d'emblée que les connexions encore actives
Afin de voir d'un coup d'œil qui a accès à mes potagers aujourd'hui, sans être noyé sous les connexions révoquées ou expirées qui s'accumulent à chaque reconnexion

**Contexte fonctionnel :**
Retour de recette d'US-294 (08/11/2026) : changer la portée ou les potagers d'un connecteur impose de le révoquer puis de le reconnecter ; chaque reconnexion laisse une ligne « Révoquée » de plus, et la liste devient vite illisible. Cette US range ces lignes sans rien effacer : l'historique reste consultable (traçabilité, « Activité »). La suppression définitive et la purge automatique sont hors périmètre (US à venir, liée à US-132).

**Critères d'acceptance :**
- [ ] CA1 : La section « Connexions » ne liste d'emblée que les connexions au statut « Active », la plus récente d'abord.
- [ ] CA2 : Sous la liste, un lien « Anciennes connexions (n) » apparaît dès qu'il existe au moins une connexion révoquée ou expirée ; `n` est leur nombre. Sans ancienne connexion, le lien n'apparaît pas.
- [ ] CA3 : Un clic sur le lien déplie les connexions révoquées et expirées (la plus récente d'abord), avec leurs informations habituelles et le bouton « Activité » ; le lien devient « Masquer les anciennes connexions ». Un second clic les replie.
- [ ] CA4 : Rien n'est effacé : aucune requête de suppression, l'« Activité » d'une connexion ancienne reste consultable.
- [ ] CA5 : Quand aucune connexion n'est active mais qu'il en existe d'anciennes, un message « Aucun assistant n'a accès à vos potagers en ce moment. » remplace la liste vide, et le lien reste affiché.
- [ ] CA6 : Révoquer une connexion la fait passer immédiatement dans les anciennes connexions (le compteur `n` augmente de 1) sans recharger l'écran.
- [ ] CA7 : La fiche du corpus `assistants-ia-mcp.md` (section « Comment voir et révoquer mes assistants connectés ») mentionne le lien « Anciennes connexions » (US-099 / CA9).
- [ ] CA type : Le rendu reste cohérent avec l'écran « Assistants connectés » d'US-294 à 375px/768px/desktop (aucune nouvelle maquette).

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation, compte (PWA)
- Migration BDD requise : non (le statut de chaque connexion est déjà rendu par `GET /mcp/connexions`)
- Dépendances : US-294
- Hors périmètre : suppression définitive d'une connexion, purge automatique (US-132)

**Estimation :** 1 point

**Scénario Gherkin :**
```gherkin
Given le jardinier a une connexion Claude active, un jeton personnel actif et une connexion Claude révoquée
When il ouvre « Assistants connectés »
Then il voit les deux connexions actives
And il voit le lien « Anciennes connexions (1) »
And la connexion révoquée n'est pas affichée
When il clique sur « Anciennes connexions (1) »
Then la connexion révoquée s'affiche avec son bouton « Activité »
When il révoque le jeton personnel
Then le lien indique « Anciennes connexions (2) » ou la liste dépliée montre le jeton révoqué
```

**Labels GitHub :** `us`, `mcp`, `pwa`
