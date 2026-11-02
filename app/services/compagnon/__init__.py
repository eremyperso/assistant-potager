"""
app/services/compagnon — Ce que le compagnon retient, commun à Telegram et à la PWA.

[US-259] Deux mémoires en base, une seule de chaque :

* `propositions`  — ce qui attend la réponse du jardinier (geste préparé par la
                    PWA, commande ou plan proposés en conversation), avec sa
                    consommation atomique ;
* `conversations` — les derniers échanges, par jardinier et par potager.

Les canaux n'en sont que des fenêtres : rien ici ne dépend de Telegram.

[US-266] L'initiative, sans modèle (R7) :

* `veilleur`          — les détecteurs purs (état du potager → signaux) ;
* `veilleur_passage`  — la lecture de l'état et le passage, potager par potager ;
* `signaux`           — les signaux en base, dédoublonnés par `cle_unique`.

[US-267] La parole, sans harceler — le distributeur règle le moment et la forme :

* `distributeur`      — les règles pures (thème coupé, silence, point du matin,
                        demi-heure, bascule après trois messages sans réaction) ;
* `distribution`      — le passage en base, l'envoi dans Telegram, la réponse ;
* `redaction_signal`  — l'agent rédige sans décider, le gabarit du code en repli ;
* `reponse_signal`    — boutons et réponse courte → phrase de geste à confirmer ;
* `proactivite`       — les réglages par thème, le silence, le point du matin.

[US-268] Les rappels de suivi :

* `rappels`           — proposition datée depuis le référentiel, programmation après
                        confirmation, liste, annulation, échéance (signal « rappels »).
"""
