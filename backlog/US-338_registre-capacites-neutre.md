**ID :** US-338
**Titre :** Extraire le registre de capacités en couche neutre, le serveur MCP devenant un adaptateur
**Épic :** ÉPIC 20 — Compagnon client des capacités

**Story :**
En tant que jardinier
Je veux que le compagnon de l'application et mes assistants extérieurs (Claude, Le Chat) s'appuient sur les mêmes capacités
Afin qu'une amélioration profite aux deux et que les deux me donnent la même réponse

**Contexte fonctionnel :**
Lot 1, principe P1 et §4.2 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`. Le registre existe déjà (`REGISTRE`, rempli par les lectures d'US-291, les propositions d'US-292 et les commandes d'US-293), mais il est attaché au serveur MCP. Il devient une couche que le compagnon peut appeler sans passer par OAuth ni JSON-RPC. Le serveur MCP garde ce qui lui est propre : authentification, quotas, portée, journal des appels.

**Règles d'une capacité :**

| # | Règle |
|---|---|
| R1 | Son nom et sa description sont ceux d'une **question de jardinier**, jamais d'une commande |
| R2 | Elle rend un **verdict** et les données qui le fondent, pas des données brutes à interpréter |
| R3 | Le verdict sort du **service qui sert l'écran** de la PWA : une seule source de vérité |
| R4 | Les textes saisis par le jardinier restent marqués comme données (`avertissement_donnees`) |
| R5 | Elle est testée une fois, pour les deux clients |

**Critères d'acceptance :**
- [ ] CA1 : Le registre et ses capacités vivent dans une couche indépendante du serveur MCP ; le compagnon peut les lister et les appeler pour un jardinier et un potager donnés
- [ ] CA2 : Le contrat externe du MCP est inchangé : mêmes outils, mêmes noms, mêmes schémas, mêmes réponses ; les tests d'US-290 à US-297 restent verts sans modification
- [ ] CA3 : Le serveur MCP n'ajoute que l'authentification, les quotas, la portée et le journal `mcp_appels`
- [ ] CA4 : Un test de parité vérifie que les deux clients voient les mêmes capacités, avec les mêmes descriptions
- [ ] CA5 : La règle d'écriture d'une capacité (R1 à R5) est documentée dans le dossier de l'épic, avec un exemple de verdict
- [ ] CA6 : Aucun comportement du compagnon actuel ne change (il n'utilise pas encore le registre)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (compagnon et assistants IA)
- Migration BDD requise : non
- Dépendances : US-290, US-291, US-292, US-293 (livrées, non commitées pour certaines), US-297
- Modèle / effort conseillé : **Sonnet 5.5, `medium`**

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le jardinier a connecté Claude au potager par le MCP
When Claude lit le plan du potager
Then il reçoit exactement la même réponse qu'avant l'extraction du registre
And le compagnon de l'application peut appeler la même capacité pour le même potager
And le test de parité confirme que les deux voient la même liste de capacités
```

**Labels GitHub :** `us`, `sprint-X`, `compagnon`, `mcp`, `backend`
