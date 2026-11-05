**ID :** INC-020
**Titre :** Renommer une parcelle en « Ouest » refusé : « nom déjà utilisé » alors qu'aucune parcelle active ne porte ce nom
**Type :** Incident
**Priorité :** Mineur

**Signalé le :** 2026-11-05

**Reproduction (jeu de test réalisé) :**
Potager 33, dans le bot Telegram, en dictée libre :
1. « renomme la planche est » → l'agent demande « Tu veux lui donner quel nom ? »
2. « ouest » → l'agent propose `/parcelle renommer Est Ouest`, le jardinier confirme.

**Résultat obtenu :**
L'exécution de la commande échoue (journal : `Action retenue : id=60 commande echouee`)
et le bot répond « ❌ Ce nom est déjà utilisé par une autre parcelle ».
La liste des parcelles en cours ne montre aucune parcelle « Ouest ». L'export de la table
`parcelles` montre pourtant la ligne id 83, « Ouest » (`nom_normalise = ouest`),
potager 33, `actif = False` : une parcelle désactivée, reste d'essais précédents
(comme « Nord », « Sud », « essai B »), qui garde ses événements via `parcelle_id`.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
Le message d'erreur doit nommer la parcelle en conflit et dire qu'elle est désactivée,
pour que le jardinier comprenne pourquoi le nom est refusé alors qu'il ne la voit pas.
Il doit pouvoir s'en sortir sans toucher à la base, par exemple en archivant l'ancienne
parcelle (renommage « Ouest (archivée) ») qui libère le nom. Dans tous les cas, l'historique
rattaché à la parcelle inactive ne doit être ni écrasé ni fusionné avec celui de « Est ».

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : Bot Telegram (message d'erreur), services/utils parcelles (contrôle d'unicité).
- Nature probable : régression logique / UX. Le contrôle d'unicité de `rename_parcelle`
  inclut les parcelles inactives, ce qui est cohérent avec la contrainte unique
  (`potager_id`, `nom_normalise`, migration v23). Le défaut tient surtout au message,
  qui ignore le nom de la parcelle en conflit pourtant présent dans l'exception.
- Fichiers probablement concernés : `utils/parcelles.py` (`rename_parcelle`, contrôle de conflit),
  `app/bot/commandes_parcelle.py` (bloc `except ValueError` du sous-commande `renommer`),
  probablement le chemin d'exécution de la commande dictée (`app/bot/interpretation.py`).
- Corpus de connaissance concerné : probablement oui, à vérifier au moment de la correction
  (fiches `data/connaissance/doc_app/` sur les parcelles ou le renommage ; voir CLAUDE.md,
  section « Corpus de connaissance »).
- Point de vigilance : ne pas ignorer les parcelles inactives dans le contrôle sans traiter
  `resolve_parcelle` (résolution par nom) et les affichages de l'historique, sous peine de
  mélanger les historiques de deux parcelles homonymes.

**Labels :** incident, bot-telegram, parcelles
