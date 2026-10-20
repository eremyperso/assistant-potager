**ID :** INC-015
**Titre :** Une question de semis datée dans le passé n'est plus routée vers « /confiance » mais traitée comme un geste
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-10-19

**Reproduction (jeu de test réalisé) :**
Bot Telegram, le 19/10/2026, potager possédant une parcelle `SERRE FROIDE`.
Quatre questions envoyées, seule la date change :
1. « est ce que je peux semer des poivrons dans serre froide ? »
2. « est-ce que je peux semer des poivrons dans serre froide le 10 février ? »
3. « est-ce que je peux semer des poivrons dans serre froide le 10/02/2027 ? »
4. « est-ce que je peux semer des poivrons dans serre froide le 10/02/2026 ? »

**Résultat obtenu :**
- (1) Routée vers `/confiance poivrons semis serre froide` : fiche ★★ évaluée au 19 octobre. Conforme.
- (2) « le 10 février », sans année : **aucune réponse du bot** (message suivant de l'utilisateur 3 h plus tard).
- (3) « le 10/02/2027 » : routée vers `/confiance poivrons semis 2027-02-10 serre froide`, fiche ★★ évaluée au 10 février 2027. Conforme.
- (4) « le 10/02/2026 » (date passée) : pas de `/confiance` ; le bot répond
  « ❓ Aucune parcelle ne porte exactement ce nom. Vouliez-vous dire SERRE FROIDE ? »,
  réponse du flux d'enregistrement d'un geste (résolution de parcelle), alors que la
  parcelle existe et que le message est une question.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
Seule l'année change : la question (« est-ce que je peux… ? ») doit recevoir le même
traitement, une évaluation de confiance, et jamais partir dans le flux d'enregistrement
d'un geste. La question sans année (2) doit recevoir une réponse.
Point à trancher par le PO : la réponse attendue pour une date passée (évaluation
rétrospective ou signalement « date passée »).

**Analyse grosse maille (premier niveau, pas un diagnostic) :**
- Zone(s) impactée(s) : Bot Telegram / routage LLM (classification de la nature du message).
- Nature probable : régression logique. Piste à vérifier : une date passée pourrait faire
  lire la phrase comme le récit d'un geste (ACTION) plutôt que comme une question
  (COMMANDE `/confiance`). C'est le symptôme inverse d'INC-011 (plantation dictée routée
  vers `/confiance`), d'où un possible effet de bord de sa correction. La non-réponse
  sur « le 10 février » est à investiguer à part (date sans année).
- Fichiers probablement concernés : `llm/routeur.py` (`_regle_par_geste`, classification
  modèle), probablement la résolution de parcelle du flux geste dans `app/bot/` pour le
  message « Aucune parcelle ne porte exactement ce nom » avec une parcelle pourtant existante.
- Corpus de connaissance concerné : non.

**Labels :** incident, bot, routeur
