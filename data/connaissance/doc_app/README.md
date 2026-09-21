# Corpus `doc_app` — l'application expliquée avec les mots du jardinier

Ce dossier est le **premier contenu** versé dans le socle de connaissance
d'US-098, et il n'a rien d'un guide utilisateur linéaire : chaque section
répond à **une question qu'un jardinier pose réellement**, et se suffit à
elle-même. C'est ce découpage, et lui seul, qui rend une réponse servable telle
quelle, sans passer par un modèle et donc sans consommer un jeton.

Le format des fiches est celui d'US-098 — en-tête, `## ` par idée, ligne
« On parle aussi de » dans **chaque** section : voir `../README.md`, et
`docs/RUNBOOK_ALIMENTATION_SOCLE_CONNAISSANCE.md` pour la procédure complète.

```bash
python tools/ingerer_connaissance.py --racine data/connaissance --strict --dry-run
python tools/ingerer_connaissance.py --racine data/connaissance
python tools/controler_aide_corpus.py --detail          # cohérence /help ↔ corpus (CA7)
python tools/mesurer_corpus_savoir.py \
    --corpus tests/corpus/us099_questions_fonctionnement.csv \
    --racine data/connaissance/doc_app --detail          # classement (CA11)
```

## Ce qui vaut pour ces fiches et pas pour les autres

* **Niveau de confiance `verifie`, sans exception.** Le sujet est notre propre
  application : chaque phrase se vérifie contre le code, il n'y a aucune raison
  d'écrire `a-valider`. C'est ce qui autorise à servir le texte mot pour mot.
* **Aucune donnée de potager, aucun `potager_id`.** Ces fiches sont partagées
  par tous les jardins, et aucun exemple n'est tiré d'un potager réel.
* **Le vocabulaire est celui du jardinier.** Ni nom de table, ni nom d'écran
  technique, ni numéro d'US dans le texte servi : ce n'est pas une coquetterie,
  le texte part tel quel dans un message.
* **Pas de chiffre agronomique ici.** Les délais, profondeurs et températures
  relèvent du référentiel et des fiches `agronomie`.

## Ce qui rend une fiche fausse — table de relecture

C'est le cœur du CA9 : **une évolution qui rend une fiche fausse impose sa mise
à jour dans la même livraison.** Sans cette table, personne ne saurait quelles
fiches relire en touchant à un calcul, et le corpus deviendrait un mensonge
documenté en quelques mois — d'autant plus crédible qu'il est servi comme
vérifié. La colonne de droite se lit à l'envers : *je touche à ceci, donc je
relis cette fiche avant de livrer.*

| Fiche | À relire dès qu'on touche à… |
|---|---|
| `stock-plants-calcul.md` | le calcul de stock (`utils/stock.py`), la règle d'unité dominante, la prise en compte de la date de référence |
| `recoltes-et-pertes.md` | le type d'organe récolté (`culture_config`), la déduction de stock à la récolte, le rendement en poids, la vente de plants |
| `semis-godet-plantation.md` | le chaînage semis → godet → plantation, le calcul des graines soldées, la déduction des godets à la plantation, la filière d'un semis — pépinière ou pleine terre : reconnaissance, proposition, reprise de l'existant (`app/services/contexte_semis.py`, `migrations/migration_v47.sql`) |
| `pepiniere-par-lot.md` | la lecture par lot (`calcul_lots_pepiniere`), les états de germination, le signalement d'incohérence de saisie |
| `parcelles-et-plan.md` | les parcelles (renommage, suppression logique, `est_pepiniere`, abri et paillage déclarés — US-181), le plan d'occupation, la **phase du moment** d'une culture en place (`recalage_calendrier.phase_de_serie`, US-194), ce que l'interpréteur de commandes rend dictable sur les parcelles (`app/services/interpreteur_commandes.py`) |
| `enregistrer-un-geste.md` | le référentiel d'actions (`utils/actions.py`), le parsing d'une phrase, l'étape de validation, la datation (dont la règle « jamais dans le futur » au moment du DÉPÔT d'un geste lancé depuis un écran, et la date du dépôt conservée à la confirmation — US-224), les façons de COMMENCER un geste — dictée, texte, bouton d'un écran, la durée de vie d'un geste en attente et ce qui l'en retire (`app/services/file_gestes.py` — US-224), l'interprétation d'une phrase en COMMANDE et ce qu'elle relit avant d'écrire (`app/services/interpreteur_commandes.py`, `app/services/menu_commandes.FORMES_DICTABLES`) |
| `journal-et-corrections.md` | l'écran Journal (filtres, pagination, export), le parcours de correction et de suppression (dont la correction de la filière d'un semis), les façons de l'ouvrir (commande tapée, phrase dictée) |
| `potager-cycle-de-vie.md` | l'archivage, la suppression logique, le délai de grâce et la purge |
| `potager-partage-et-roles.md` | les rôles et leurs droits, les invitations, le changement de rôle et la règle du dernier propriétaire (`app/services/potagers.py` — US-085), le retrait d'un membre, le départ volontaire (US-086), l'adhésion par code depuis Telegram, commande `/rejoindre` (`app/bot/liaison.py` — US-087), l'isolation entre potagers |
| `compagnon-telegram.md` | l'activation Telegram, la liaison de compte, la synthèse vocale, la dissociation, la **file de gestes en attente** et tout ce qui la gouverne — dépôt depuis la PWA, lien profond `/start` réutilisable, durée de vie de trois jours par geste, présentation à deux niveaux, commande `/gestes`, issues *Confirmer / Plus tard / Abandonner*, motifs de refus, cadence et arrêt des relances, coupure des rappels, avertissement et notification de purge (`app/services/file_gestes.py`, `app/services/relances_file.py`, `app/bot/file_gestes.py`, `app/services/telegram_notify.py` — US-224) |
| `statistiques-et-bilans.md` | le contenu de `/stats` (dont les totaux de semis par filière, `contexte_semis.semis_par_contexte`), le détail par variété, les agrégats mensuels |
| `notes-et-observations.md` | les catégories de note (`utils/notes.py`) et leur enregistrement, la mémoire du potager (`app/services/memoire_potager.py`) : ce qui y entre, la restitution d'une note, l'isolation entre potagers, le devenir d'une note corrigée ou supprimée, ainsi que la façon dont un carnet volumineux est présenté — repères par année et par saison (`app/services/reponses_chiffrees.py`, familles `notes_culture` / `notes_parcelle`) |
| `cultures-familles-et-rotation.md` | la famille botanique et son délai de retour, le calcul de rotation, l'avertissement à la plantation, les associations |
| `calendrier-et-zone-climatique.md` | le calendrier cultural (itinéraires, fenêtres de semis et de récolte, durées), la zone climatique du potager et sa déduction depuis la localisation, la portée d'une correction au bot, la frise des mois de l'écran Plan (quatre phases dont la plantation, priorité quand deux phases partagent un mois, zone et mode dégradé — US-176), la frise recalée d'une culture en place (origine réelle, en croissance, récolte attendue et reste à courir, séries échelonnées, cas sans recalage — US-070) , le niveau de confiance avant de semer ou de planter : règles, pondérations, seuils d'étoiles, dernière gelée moyenne par zone, et ce que la réponse du bot propose comme suite (`app/services/confiance_semis.py`, `app/bot/commandes_confiance.py` — US-178, US-179), la pastille de confiance des tuiles de l'écran Plan (geste retenu, « pas de calendrier », « Pourquoi ce niveau ? » — `frontend/src/lib/confiance.js`, `frontend/src/components/FicheConfiance.jsx` — US-180), la fiche calendrier d'une culture ouverte depuis Plan et Stocks (gestes proposés, séries en terre, frise conseillée ou recalée, enregistrement — `frontend/src/lib/ficheCalendrier.js`, `frontend/src/components/FicheCalendrier.jsx` — US-183), le bouton d'enregistrement de la fiche et le geste qu'il dépose dans la file (`frontend/src/components/BoutonGeste.jsx`, `frontend/src/lib/gestes.js` — US-224) |

Toute fiche ajoutée ici entre dans cette table **dans le même commit** :
`tests/test_us099_corpus_fonctionnement.py` échoue tant que ce n'est pas fait.

## Les domaines de `/help`

L'en-tête `domaines_aide:` relie une fiche aux domaines de l'aide ciblée
(`bot._HELP_DOMAINES`). C'est la seule chose que `tools/controler_aide_corpus.py`
regarde : un domaine annoncé par `/help` sans aucune fiche fait échouer
l'intégration continue. Une fiche peut n'en déclarer aucun — toutes les
questions du jardinier ne correspondent pas à un mot-clé d'aide.

`/help` reste le **sommaire** : il énumère les commandes et renvoie vers le
contenu, il ne le recopie pas. Le jour où une fiche se met à répéter le texte
de `/help`, c'est le signe qu'elle a changé de nature.

## Ce que la mesure a appris sur ce corpus

65 questions de fonctionnement (`tests/corpus/us099_questions_fonctionnement.csv`),
mesurées sur le repli SQLite : **65/65 dans les trois premiers résultats**, dont
58 en tête. Deux enseignements pratiques, tirés des échecs rencontrés en cours
de rédaction :

* une section ne se retrouve que par les mots qu'elle porte — « comment dicter
  ce que j'ai fait au jardin ? » ne trouvait rien tant que la ligne
  « On parle aussi de » ne disait pas « au jardin », le mot manquant à l'index ;
* la question posée décide de la fiche attendue, pas le plan qu'on avait en
  tête : « combien de temps ai-je pour revenir en arrière ? » est répondue par
  la section sur la suppression, pas par celle sur la purge.

⚠️ Cette mesure vaut pour le repli SQLite. Celle qui conditionne l'activation en
production se rejoue contre PostgreSQL, comme le rappelle le runbook.
