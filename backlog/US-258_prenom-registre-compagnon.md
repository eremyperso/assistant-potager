**ID :** US-258
**Titre :** Appeler le jardinier par son prénom et parler à son registre
**Épic :** ÉPIC 14 — Compagnon actif : profil, mémoire et initiative *(numéro à valider, voir `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md`)*

**Story :**
En tant que jardinier
Je veux que le compagnon m'appelle par mon prénom, me tutoie et parle sur le ton que j'ai choisi
Afin d'échanger avec un voisin de jardin plutôt qu'avec un formulaire

**Contexte fonctionnel :**
Profil d'échange, partie 1 (cadrage §1.1, §1.7, §2 ; décision D4). Le profil est rangé par `(user_id, potager_id)`. Le registre change le **ton**, jamais le **fond** : mêmes faits, mêmes règles de prudence, mêmes sources.

**Critères d'acceptance :**
- [ ] CA1 : Au premier échange, le compagnon propose le `first_name` Telegram (sinon le nom du compte web) et **demande** comment appeler le jardinier, au lieu de le supposer.
- [ ] CA2 : Le prénom est validé (lettres, espaces, tirets, 30 caractères au plus) ; une saisie invalide est refusée avec une explication.
- [ ] CA3 : Trois registres existent : `sobre`, `voisin` (défaut), `gouailleur`, choisis par boutons au premier contact et modifiables avec `/profil`.
- [ ] CA4 : Le prénom et le registre sont injectés en partie variable du prompt, **balisés comme données**, jamais concaténés aux consignes (R10).
- [ ] CA5 : Un prénom contenant une consigne (« Ignore tes règles ») est soit refusé par la validation, soit sans effet sur le corpus de couperets (test).
- [ ] CA6 : Un réglage du profil demandé par une phrase (« appelle-moi Rico ») est une **proposition** confirmée, pas une écriture d'office (R9).
- [ ] CA7 : En `sobre` et en `gouailleur`, un même dialogue de mesure donne les mêmes faits ; aucun registre ne donne de dose ni de produit de traitement.
- [ ] CA8 : Le profil est propre au couple jardinier × potager : un registre différent sur deux potagers est respecté.
- [ ] CA9 : La fiche de `data/connaissance/doc_app/` sur le compagnon décrit `/profil`.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram
- Migration BDD requise : oui (table du profil d'échange, `potager_id` + RLS)
- Dépendances : US-257
- Production conseillée : **Sonnet 5.5, effort `medium`** — table, commande et injection balisée suivent des modèles existants ; le test d'injection (CA5) est le seul point fin.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given un jardinier Telegram dont le first_name est "éric" et sans profil
When il écrit son premier message au compagnon
Then le compagnon lui demande comment l'appeler en proposant "Éric"
And propose les registres [Sobre] [Comme un voisin]

Given un profil en registre "sobre"
When le jardinier écrit "les limaces ont bouffé mes salades"
Then la réponse cite les mêmes faits qu'en registre "voisin", sans familiarité
```

**Labels GitHub :** `us`, `compagnon`, `profil`, `telegram`
