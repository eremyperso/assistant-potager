# Le carnet du compagnon — paragraphe destiné à la politique de confidentialité

**Produit par US-265 (CA6). À intégrer par US-132 (RGPD & conformité), avec le paragraphe de la
connexion Google (`RGPD_FEDERATION_GOOGLE.md`).**

Le carnet retient ce que le jardinier a **dit** à son compagnon de lui-même (« j'arrose le soir »,
« aucun traitement, même bio »). Cette fiche dit ce qui est stocké, qui le voit, et comment l'effacer.

---

## Paragraphe à insérer — « Ce que votre compagnon retient de vous »

> ### Le carnet de votre compagnon
>
> Quand vous lui dites une habitude, une contrainte ou un objectif, votre compagnon peut vous proposer
> de la retenir pour ne plus vous suggérer ce qui ne vous correspond pas. **Rien n'est retenu sans votre
> accord** : il vous montre ce qu'il veut retenir, et vous confirmez ou refusez.
>
> | Donnée | Usage | Conservation |
> |---|---|---|
> | Des faits courts (200 caractères au plus, 30 au plus par potager), avec leur date et la phrase qui les a fait naître | Adapter les conseils du compagnon | Jusqu'à ce que vous les effaciez |
> | Votre niveau (débutant ou confirmé), que le compagnon vous propose d'après votre activité et que vous confirmez | Régler la longueur des explications et le vocabulaire | Jusqu'à ce que vous l'effaciez |
> | Jusqu'à trois objectifs de saison, écrits par vous | Orienter les suggestions | Jusqu'à ce que vous les effaciez |
>
> **Qui y a accès.** Vous seul. Le carnet est personnel : il n'est pas partagé avec les autres membres
> d'un potager, et chaque potager a le sien. Les faits ne servent qu'à répondre à vos propres phrases ; ils
> sont transmis au service de langage qui rédige les réponses, au même titre que vos autres messages, comme
> des **données** et jamais comme des consignes.
>
> **Données sensibles.** Le compagnon ne vous demande jamais votre état de santé, vos opinions, votre vie
> privée ni aucune autre catégorie particulière de données. Le carnet n'a pas de champ prévu pour cela, et
> les faits sont courts. Si vous écrivez malgré tout une information de ce type dans un fait, vous pouvez
> l'effacer à tout moment.
>
> **Vos droits.**
>
> - **Droit d'accès** : la commande `/carnet` dans Telegram et l'écran « Mon compagnon » (menu du compte,
>   dans l'application) listent tout ce qui est retenu, avec la date de chaque fait.
> - **Droit de rectification** : chaque fait se modifie, depuis `/carnet` (« Modifier ») ou depuis l'écran
>   « Mon compagnon ».
> - **Droit d'effacement** : chaque fait s'oublie un par un (« Oublier un point »), ou tous à la fois
>   (« Tout oublier »), ce qui efface aussi le niveau et les objectifs de saison. L'effacement est
>   immédiat et définitif.
> - Quitter un potager ou supprimer son compte retire le carnet qui s'y rattache.

---

## Pour l'équipe

- **Table** : `carnet_faits` (migration v64), rangée par `(user_id, potager_id)`, **RLS stricte** par potager.
  Niveau et objectifs : colonnes `niveau_compagnon` et `objectifs_saison` de `potager_membres` (profil).
- **Aucune catégorie sensible n'est demandée** : le compagnon ne pose jamais de question dans ce sens, et le
  prompt n'incite pas à en retenir.
- **Écriture** : uniquement après la confirmation d'une proposition (R9). Le modèle ne peut pas écrire au carnet.
- **Code** : `app/services/carnet_compagnon.py` ; Telegram `app/bot/commandes_carnet.py` ; PWA
  `frontend/src/components/ModalMonCompagnon.jsx` ; API `/compagnon/carnet`.
- **À vérifier sur PostgreSQL** : la sortie d'un potager efface le carnet (`carnet_compagnon.effacer_du_membre`, appelé par `potagers._supprimer_appartenance`) ; la RLS stricte exige que le potager soit armé au moment de la suppression.
