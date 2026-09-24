**ID :** INC-009
**Titre :** Une récolte supérieure au stock en place est enregistrée sans contrôle
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-09-24

**Reproduction (jeu de test réalisé) :**
Bot Telegram, potager 26, culture `salade` (organe de récolte végétatif, donc
récolte destructive), parcelle `planche_salade` (id 67). Au moment du geste, la
vue Stocks de ce potager annonçait **23 plants en place** pour cette ligne
(53 installés, 30 déjà récoltés en pièces le 24/09 — relevé effectué avant le
geste ci-dessous, cf. INC-008).

Message dicté en texte au bot :

```
récolte de 50 salades
```

Le routeur classe le message en ACTION (origine=regle, confiance 1.00), le
parseur déterministe le reconnaît sans modèle
(`geste=recolte culture=salade qte=50.0 plants parcelle=None`), la parcelle est
auto-détectée (`[US-021] Parcelle auto-détectée : 'planche_salade'`), une
confirmation est demandée puis reçue par l'utilisateur.

**Résultat obtenu :**
La récolte de 50 plants est acceptée et enregistrée telle quelle, sans erreur
ni avertissement, alors que 23 plants seulement étaient en place :

```
2026-09-24 11:01:09 │ INFO │ [US-021] Confirmation demandée — user_id=8063902186, 1 item(s)
2026-09-24 11:01:11 │ INFO │ [US-021] Confirmation reçue — user_id=8063902186, 1 item(s)
2026-09-24 11:01:11 │ INFO │ 💾 DB SAVE : id=543 | action=recolte | culture=salade | qte=50.0 plants | parcelle=67 | date=2026-09-24 00:00:00 | contexte_semis=None
```

Aucun message de refus, aucune mention du stock disponible dans le récapitulatif
de confirmation. L'événement 543 existe en base. Le déclarant indique qu'une
vérification de ce type était en place sur les versions précédentes ; le libellé
exact du contrôle d'alors n'est pas connu.

Signalement fourni sous forme de journal d'exécution, sans capture d'écran : le
défaut n'est pas visuel.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
Une récolte destructive (culture végétative) ne devrait pas pouvoir porter sur
plus de pieds qu'il n'en reste en place pour cette culture/variété dans ce
potager. La saisie devrait être refusée, ou à tout le moins signalée avec le
stock réellement disponible avant la confirmation — et non enregistrée en
silence, ce qui fausse ensuite le stock en place et le plan.

Le traitement retenu (blocage dur comme pour une perte, ou avertissement puis
confirmation explicite) et le sort du stock résultant restent à arbitrer. Le cas
des cultures à récolte non destructive (reproducteur : tomate, courgette…), dont
les récoltes ne consomment pas le pied, n'est pas concerné par ce contrôle.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : API/Backend (`app/services/evenements.py`), Bot Telegram
  (récapitulatif de confirmation).
- Nature probable : garde-fou manquant ou d'assiette trop étroite — un contrôle
  de stock existe, il ne semble pas couvrir la récolte.
- Fichiers probablement concernés : `app/services/evenements.py`
  (`StockInsuffisantError` et `_stock_disponible_perte`, confirmés présents, dont
  la documentation ne mentionne que la perte — jardin ou godet) ; `utils/stock.py`
  (calcul du stock en place d'une culture végétative).
- Corpus de connaissance concerné : à vérifier par le Developer — une fiche de
  `data/connaissance/doc_app/` décrit les contrôles de quantité et le stock ; elle
  devra être mise en cohérence si un nouveau refus apparaît.

**Labels :** incident, backend, bot
