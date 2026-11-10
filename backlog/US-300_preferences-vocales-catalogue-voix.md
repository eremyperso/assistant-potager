**ID :** US-300
**Titre :** Mémoriser les préférences vocales et lister les voix françaises
**Épic :** ÉPIC 17 — Compagnon vocal dans la PWA *(numéro à valider, voir `docs/EPIC 17 - COMPAGNON VOCAL PWA/ANALYSE_ET_SOLUTION_COMPAGNON_VOCAL.md`)*

**Story :**
En tant que jardinier
Je veux que mon choix de voix et mes réglages vocaux me suivent d'un appareil à l'autre
Afin de retrouver la même voix de Gaston sur mon PC, ma tablette et mon téléphone

**Contexte fonctionnel :**
Préférence **de la personne**, pas du potager : un jardinier membre de deux potagers garde sa voix (étude §5.3). La liste des voix est lue sur l'API Mistral (D2), avec repli sur les quatre voix françaises connues : Marie `voice_592`, Manon `voice_3137`, Léa `voice_589`, Camille `voice_3141`.

**Critères d'acceptance :**
- [ ] CA1 : La migration v71 crée `preferences_voix` (`user_id` clé, `mode_vocal` faux par défaut, `voix_id` nul, `lecture_auto` vrai par défaut, `maj_le`) avec son `rollback_v71.sql` ; un jardinier ne lit et n'écrit que sa propre ligne.
- [ ] CA2 : `GET /compagnon/voix/preferences` rend les réglages ; sans ligne, il rend les valeurs par défaut (mode vocal éteint, voix par défaut de la configuration `VOIX_PAR_DEFAUT`, lecture automatique active) sans rien écrire.
- [ ] CA3 : `PUT /compagnon/voix/preferences` enregistre les réglages ; une voix absente du catalogue est refusée (422) avec la liste des voix valides.
- [ ] CA4 : `GET /compagnon/voix/catalogue` rend les voix françaises (identifiant, nom, genre s'il est fourni) lues sur l'API Mistral et gardées en cache 24 h ; une nouvelle voix française publiée par Mistral apparaît sans redéploiement.
- [ ] CA5 : Si l'API des voix ne répond pas, le catalogue rend les quatre voix connues, marquées « liste de secours » ; aucune erreur n'est montrée au jardinier.
- [ ] CA6 : `GET /compagnon/voix/catalogue/{voix_id}/extrait` rend un MP3 court de la voix : l'extrait fourni par Mistral, sinon la phrase « Bonjour, je suis Gaston, votre compagnon du potager » synthétisée une seule fois puis gardée en cache ; un deuxième appel ne coûte rien.
- [ ] CA7 : Une voix choisie puis retirée par Mistral retombe sur `VOIX_PAR_DEFAUT` à la lecture, sans erreur ; la préférence est corrigée au prochain enregistrement.
- [ ] CA8 : La suppression du compte supprime ses préférences vocales.
- [ ] CA9 : Aucune logique dans les routes ; tout passe par `app/services/voix/`.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation et réglages (API)
- Migration BDD requise : oui (v71, `preferences_voix`)
- Dépendances : US-299
- Décisions liées : D2
- Fiche du corpus : aucune tant que l'écran n'existe pas (voir US-301)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given le jardinier n'a jamais réglé la voix
When la PWA lit GET /compagnon/voix/preferences
Then le mode vocal est éteint, la lecture automatique active et la voix celle de VOIX_PAR_DEFAUT
When il enregistre la voix "voice_3137" (Manon) depuis son PC
And ouvre la PWA sur son téléphone
Then la voix lue est "voice_3137"
Given l'API des voix de Mistral ne répond pas
When la PWA lit le catalogue
Then elle reçoit Marie, Manon, Léa et Camille marquées "liste de secours"
```

**Labels GitHub :** `us`, `voix`, `api`, `migration`
