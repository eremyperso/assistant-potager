**ID :** US-360
**Titre :** Passer le Plan sur le socle
**Épic :** ÉPIC 21 — Socle commun des vues

**Story :**
En tant que jardinier
Je veux lire le plan avec les mêmes repères que le reste du carnet, et voir d'un coup ce qui est à confirmer ou à libérer
Afin de savoir où en est chaque parcelle sans légende à décoder

**Contexte fonctionnel :**
Vague 2 de l'ÉPIC 21, détachée d'US-356 quand la Pépinière est passée à trois onglets. La référence est la maquette (Mobile : Plan · règle des temps ouverte ; Ordinateur : Plan).
Le plan vu du dessus est livré par l'ÉPIC 19 (US-326 → US-333) et suit déjà le découpage de la piste C. **On ne le refait pas**, on le pose sur le socle.

**Critères d'acceptance :**
- [ ] CA1 : **En-tête** : « Plan des parcelles », onglets **Plan** et **Rotation · à venir** (désactivé). Ils reviennent dans l'en-tête, US-330 CA1 est révisé. Barre d'outils du socle (recherche « Parcelle ou culture »)
- [ ] CA2 : **Bandeau** « **Au 23 novembre** · fond photo · 25 × 15 m », qui suit la règle des temps (« Au 12 novembre » quand on remonte la saison)
- [ ] CA3 : **Plan mobile** :
  - le plan réduit avec sa rose des vents, puis « ? Légende ⌄ » repliable (US-352) et « Appui long sur un rang ou une pastille : son étape »
  - deux raccourcis, « ● 3 à confirmer » et « 3 à libérer », qui ouvrent la fiche de la première culture concernée
  - « **Dans l'ordre du chemin** » : une carte par parcelle (« Planche centrale · 8 rangs · Détail »), un rang par ligne (R1, pastille, emoji, nom, état · variété, « À confirmer » en orange) et les rangs libres en pointillé
  - la carte d'une pépinière (« Châssis · pépinière froide ») liste ses lots et renvoie à Ma pépinière
- [ ] CA4 : **Plan ordinateur** : plan à l'échelle (rangs proportionnels, fond photo atténué, plus sombre en mode sombre, rose des vents, échelle « 5 m ») et légende complète sous le plan (sept étapes, hachuré « prévu », point « à confirmer », rang libre). Toucher un rang ouvre la fiche commune (US-355) dans le panneau droit et réduit le plan
- [ ] CA5 : **Mot de Gaston du Plan** : rangs à libérer et engrais vert encore possible → « **3 rangs à libérer** : tomates cerises (serre), pommes de terre, haricots. Un engrais vert de seigle peut encore y être semé cette semaine. » → *Voir les rangs*, *Noter*
- [ ] CA6 : L'éditeur du plan (US-333), le détail de parcelle (US-330) et le retrait ou la création de parcelles avec Gaston (US-332) restent joignables. « Détail » sur une carte ouvre le détail de parcelle
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-353 ; US-327/US-329 (plan vu du dessus et mobile), US-330 (détail de parcelle), US-333 (éditeur)
- Modèle / effort conseillé : **Sonnet 5.5, `low`** — habillage d'une vue livrée qui suit déjà la maquette ; ni Opus ni Fable ne sont requis

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given la fève de la planche centrale a une levée prévue aujourd'hui
When le jardinier ouvre le Plan sur mobile
Then il voit "3 à confirmer" et "3 à libérer" sous le plan
And la carte "Planche centrale" montre au rang 6 la fève avec "À confirmer"
When il fait un appui long sur le rang de la fève dans le plan réduit
Then l'étape "Fève · Levé, prévu" s'affiche sans ouvrir la fiche
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `plan`, `socle`
