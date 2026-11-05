**ID :** INC-021
**Titre :** « affiche moi les rappels ? » n'ouvre pas /rappels et renvoie de fausses « mémoires du potager » datées de 2023
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-11-05

**Reproduction (jeu de test réalisé) :**
Potager 33, bot Telegram, le 05/11/2026 :
1. Dictée « je veux semer en pépinière des 10 graines de courgettes jaunes » → semis enregistré
   (événement 665), rappel proposé puis programmé : « voir où en est la levée des courgette » le 2026-11-15.
2. Message libre « affiche moi les rappels ? ».
3. Pour comparaison : « mon carnet » puis la commande `/rappels`.

**Résultat obtenu :**
- « affiche moi les rappels ? » : le journal indique `phrase interrogative → cascade des questions`,
  puis classement `QUESTION_DATA`, `AGENT SQL … geste 'observation' absent de la question`,
  remontée au raisonnement du modèle. Le bot répond « Voici les rappels enregistrés pour ton potager »
  et liste quatre « MÉMOIRE DU POTAGER » datées de juin à septembre 2023 (limaces sur les salades,
  buttage des tomates, semis de radis, récolte des courges). Le rappel du 15 novembre n'y figure pas.
  Ces entrées n'apparaissent ni dans « mon carnet » ni dans `/rappels` ; leur origine est inconnue
  (probablement reconstruites par le modèle).
- « mon carnet » : liste les habitudes et objectifs du jardinier (arrosage, engrais bio, objectif tomate…),
  cohérent avec ce que fait cette commande.
- `/rappels` : « Voici tes rappels à venir : • 15 novembre — voir où en est la levée des courgette », correct.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
« affiche moi les rappels ? » doit être reconnu comme une demande de liste des rappels et produire le même
résultat que `/rappels` (le rappel du 15 novembre, avec son bouton d'annulation). Le bot ne doit jamais présenter
comme « rappels enregistrés » des notes de mémoire du potager, ni des contenus que le modèle n'a pas lus
dans la liste des rappels.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : Bot Telegram / routage des phrases libres vers les commandes.
- Nature probable : régression logique ou lacune de routage. Une règle `rappel_lister`
  existe pourtant (US-268) ; la forme « affiche moi les rappels » avec point d'interrogation n'est
  probablement pas reconnue, ou la phrase interrogative est déviée vers les questions avant que la règle
  ne s'applique. À investiguer. Même famille que INC-019 (question non routée vers l'agent).
- Fichiers probablement concernés : `app/services/interpreteur_commandes.py` (règle `rappel_lister`,
  tests de la phrase interrogative), `app/bot/messages.py` (aiguillage « phrase interrogative → cascade
  des questions »), `app/bot/questions.py` (repli `_ask_question` qui produit la réponse trompeuse).
- Corpus de connaissance concerné : probablement oui, à vérifier à la correction
  (fiche `data/connaissance/doc_app/` sur les rappels et la mémoire ; voir CLAUDE.md,
  section « Corpus de connaissance »).

**Labels :** incident, bot-telegram, routage
