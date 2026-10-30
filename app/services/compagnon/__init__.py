"""
app/services/compagnon — Ce que le compagnon retient, commun à Telegram et à la PWA.

[US-259] Deux mémoires en base, une seule de chaque :

* `propositions`  — ce qui attend la réponse du jardinier (geste préparé par la
                    PWA, commande ou plan proposés en conversation), avec sa
                    consommation atomique ;
* `conversations` — les derniers échanges, par jardinier et par potager.

Les canaux n'en sont que des fenêtres : rien ici ne dépend de Telegram.
"""
