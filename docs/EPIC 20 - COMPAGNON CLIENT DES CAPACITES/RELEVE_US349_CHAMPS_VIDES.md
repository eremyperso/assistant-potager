# Relevé US-349 — champs du référentiel vides pour les 20 cultures à fiche (14/11/2026 → relevé du 18/11/2026)

Sources lues : `wind_river_attributs.json` (calendriers + attributs), `attributs_redaction_interne.json`. « — » = vide, affiché « non renseigné ».

| Culture | Exposition | Besoin en eau | Plantation (par climat renseigné) | Entrée calendrier |
|---|---|---|---|---|
| tomate | plein soleil | élevé | — | oui |
| haricot | plein soleil | — | — | oui |
| courgette | plein soleil | élevé | — | oui |
| chou | plein soleil | élevé | — | oui |
| carotte | plein soleil | moyen | — | oui |
| concombre | plein soleil | élevé | — | oui |
| cornichon | plein soleil | — | — | oui |
| poivron | plein soleil | — | — | oui |
| ail | plein soleil | moyen | — | absente |
| blette | — | — | — | absente |
| salade | — | — | — | oui |
| mâche | — | — | — | absente |
| radis | — | — | — | oui |
| épinard | — | — | — | absente |
| poireau | — | — | — | oui |
| oignon | — | — | — | oui |
| betterave | — | — | — | oui |
| pomme de terre | — | — | — | absente |
| petit pois | — | — | — | oui |
| fraise | — | — | — | absente |

À renseigner : tout « — ». Les cultures semées en place gardent `plantation` à null (règle du gabarit) ; seules salade, poireau, chou, tomate, poivron, fraise, oignon (bulbilles), ail, pomme de terre sont concernées. Méthode : skill `potager-calendrier-culture` (Cyril) pour le calendrier, relecture humaine pour exposition et eau.
