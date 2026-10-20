**ID :** US-233
**Titre :** Ouvrir la passerelle aux appels d'outils et mesurer le modèle de l'agent
**Épic :** ÉPIC 13 — Agent interpréteur *(numéro à valider, voir `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`)*

**Story :**
En tant qu'administrateur
Je veux savoir, chiffres à l'appui, si le modèle Groq retenu comprend une demande en français quand on lui décrit les commandes sous forme d'outils typés
Afin de décider de lancer l'agent interpréteur sur une mesure réelle, avant d'avoir construit tout le reste

**Contexte fonctionnel :**
Regroupe le spike S0 et la phase 1 de l'architecture (§6). Le spike se fait **avec** la vraie passerelle plutôt qu'avec un script jetable : la fonction d'appel d'outils sert de toute façon aux US suivantes, et la mesure porte ainsi sur le chemin réel (journalisation, consommation, repli 429).

Aucun comportement du bot ne change. Le jardinier ne voit rien.

**Critères d'acceptance :**

*Passerelle*
- [ ] CA1 : La passerelle expose un appel qui accepte une liste d'outils et un `tool_choice`, et renvoie le texte et les appels d'outils. Elle reste le seul point de sortie vers le modèle (audit `tools/audit_appels_llm.py` à jour)
- [ ] CA2 : Un type d'appel `agent` existe, avec son modèle réglable par `GROQ_MODEL_AGENT`, distinct de `GROQ_MODEL_CLASSIFICATION`. Le réglage est documenté dans `.env.example`
- [ ] CA3 : Journalisation, comptage des jetons (dont la part en cache) et repli en cas de 429 sont identiques à ceux des autres types d'appel
- [ ] CA4 : Un modèle (clé BYOK comprise) qui ne gère pas les appels d'outils est détecté au premier appel ; le résultat est mémorisé et l'appelant reçoit un échec propre, jamais une exception
- [ ] CA5 : `AGENT_MODE` (`off` par défaut, `ombre`, `actif`) et `AGENT_MAX_TOURS` sont lus depuis la configuration, sans effet tant qu'aucun agent ne les utilise

*Mesure*
- [ ] CA6 : Un outil d'évaluation lance le modèle réel sur un échantillon d'au moins 30 phrases du corpus US-172, enrichi de négations, de paires déclaration / question et de demandes ambiguës, avec un catalogue d'outils provisoire écrit pour l'occasion (une demi-douzaine d'outils, dont `parcelle_modifier` et les outils terminaux)
- [ ] CA7 : Le rapport donne, par catégorie : bon outil choisi, bons paramètres, précision demandée quand il le fallait, latence p50 / p95, jetons et part en cache
- [ ] CA8 : Le rapport conclut par un **go / no-go** argumenté et le modèle retenu. Il est versé dans `docs/EPIC - AGENT INTERPRETEUR/`

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (couche d'accès au modèle)
- Migration BDD requise : non
- Dépendances : aucune
- Le catalogue provisoire de CA6 est jetable : le catalogue généré arrive avec US-235
- Corpus : aucune fiche à mettre à jour (aucun comportement visible)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le modèle de l'agent est réglé dans GROQ_MODEL_AGENT
When je lance l'évaluation sur l'échantillon du corpus
Then le rapport indique pour "Ma serre extérieure n'est plus une pépinière" l'outil parcelle_modifier avec est_pepiniere à false
And il indique la latence p95 et le nombre moyen de jetons par phrase
And il conclut par un go ou un no-go
```

**Labels GitHub :** `us`, `agent-interpreteur`, `llm`
