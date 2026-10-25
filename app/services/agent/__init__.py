"""
app/services/agent — L'agent interpréteur [US-235]
==================================================
L'agent remplace le repli modèle de l'interpréteur de commandes (US-172), à la
même place dans le flux et avec la même sortie : une `CommandeInterpretee`
qui passe par le récapitulatif et la confirmation existants. Il PROPOSE, il
n'exécute jamais.

  catalogue_outils    les outils, générés depuis le catalogue des commandes
  adaptateurs         un appel d'outil typé → les arguments de la commande existante
  validation          l'ancrage selon la nature de la valeur (architecture §2.3, §3.5)
  interpreteur_agent  l'appel au modèle, par la passerelle

Sous `app/services/` et non sous `llm/` : l'agent connaît le métier (commandes,
parcelles), là où `llm/` n'est que l'accès au modèle. Et hors de `app/bot/` :
la PWA pourra le réutiliser sans dépendre de Telegram.

Conception : `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_AGENT_INTERPRETEUR.md`.
"""
