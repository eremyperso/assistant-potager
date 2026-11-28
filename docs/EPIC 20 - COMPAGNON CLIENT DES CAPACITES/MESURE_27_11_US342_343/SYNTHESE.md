# Synthèse de la relecture humaine — porte G2, mesure du 27/11/2026 (US-342 / US-343)

Relecture terminée le 28/11/2026 : 16 dialogues du passage 3 (boucle à capacités, Mistral Small 4) et 18 cas pas encore
joués. Détail : `verdicts_humains.json`, `A_CORRIGER.md`, `rapport.md` (rapport de la mesure).

## En bref

- **La porte G2 n'est pas franchie.** Le porteur juge utiles et aboutis **11 cas sur 16** (69 %). Sur les 15 cas tirés
  par le rapport, sans B13-F1 ajouté parce qu'il échouait partout : 11 sur 15 (73 %). Seuils : 80 % utile, 85 % abouti.
- **Les chiffres du juge (50 % et 48 %) ne sont pas fiables.** Il ne lit que le début des résultats d'outil et
  s'écarte du porteur 7 fois sur 16 sur l'utilité.
- **L'application bride le compagnon** : au-delà de 6 000 caractères, un résultat d'outil est coupé. 66 dialogues sur
  432 sont concernés, dont 22 des 28 lectures de pépinière.
- Les deux coupures sont à corriger avant toute nouvelle mesure.

## Limites à garder en tête

- 16 dialogues sur 432, un seul passage : un indicateur, pas une mesure.
- Pour plusieurs cas, l'assistant a signalé des faits ou proposé un verdict **avant** la décision du porteur.
- Les verdicts « oui » de B23-F1 et F4 ont été confirmés par le porteur après la découverte de la coupure à 6 000.

## Verdicts

| | Porteur | Juge |
|---|---|---|
| Utile au premier tour | 11 / 16 | 6 / 16 |
| Aboutit en 3 tours | 11 / 16 | 9 / 16 |
| Accord juge / porteur, « utile » | 9 / 16 | |
| Accord juge / porteur, « aboutit » | 12 / 16 | |

Désaccords, « utile » : refusés par le juge et acceptés par le porteur B15-F7, B17-F5, B23-F1, B23-F4, B23-F5, B24-F4 ;
l'inverse B08-F4. « Aboutit » : B17-F5, B23-F1, B23-F4 acceptés par le porteur seul ; B16-F2 par le juge seul.

## Les cinq échecs

| Cas | Remarque du porteur | Cause (premier relevé, à confirmer au classement) |
|---|---|---|
| B13-F1 | n'oriente pas le geste sur la seule culture indiquée | capacité manquante (fin de culture) et jeu sans haricot en place |
| B03-F4 | ne propose pas le semis de haricot en pleine terre | à classer |
| B05-F6 | doit répondre par une recherche web et dire comment compléter la fiche | capacité absente (arbitrage) et attendu faux |
| B08-F4 | doit demander ou vérifier le dernier arrosage | consigne rendue par la météo ignorée |
| B16-F2 | présente des graines semées comme restantes | description de `voir_stock` (probable) |

## Cas relus sans être joués

- **B25** (récolte sur deux parcelles) : justes. **B26** (perte) : justes, la cause de la perte doit être notée.
  Pas de « Sans parcelle » dans ces attendus : il ne désignerait aucune plantation.
- **B27** (semis ou repiqués), nouveau : justes. Non vérifié : les lectures donnent-elles la levée et le repiquage en
  pleine terre ?

## Décisions encore ouvertes

- Culture inconnue : réponse issue d'une recherche web ?
- B16-F3 « stock graines » : l'attendu doit-il dire qu'il n'y a pas de réserve de graines ?
- Écarts Telegram / PWA sur les gestes : feu vert pour cadrer l'US ?

## Suite proposée

1. Classer par cause les échecs de l'ensemble de la campagne.
2. Corriger la coupure du compagnon (alléger les lectures) et celle du juge.
3. Rejuger les traces existantes, puis rejouer le compagnon — volume et coût annoncés, accord avant lancement.
