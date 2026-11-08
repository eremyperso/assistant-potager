# Exemples d'utilisation — le potager dans un assistant IA

> Compagnon de l'[étude](ETUDE_MCP_POTAGER.md). Ces dialogues sont **cibles** : ils
> décrivent le comportement attendu une fois US-290 à US-295 livrées, et servent de base
> aux scénarios de recette d'US-296.
>
> Notation : 👤 le jardinier, 🤖 l'assistant (Claude, ChatGPT ou Le Chat),
> `⚙️ outil(...)` un appel au serveur MCP, `↩️` ce que le serveur rend (résumé).
> Les données sont fictives (potager « Les Mésanges », zone climatique 8a).

---

## 1. Se connecter (une fois)

**Dans Claude** : Paramètres → Connecteurs → Ajouter un connecteur personnalisé →
URL `https://potager.eremy.fr/mcp`.
**Dans ChatGPT** : Paramètres → Connecteurs (mode développeur) → Créer → même URL.
**Dans Le Chat** : Connecteurs → Ajouter un connecteur MCP → même URL.

Puis, dans tous les cas :

1. L'assistant ouvre la page de connexion d'Assistant Potager.
2. Le jardinier se connecte (e-mail ou Google).
3. Page de consentement :
   > **Claude veut accéder à votre potager**
   > ☑ Lire vos potagers, votre carnet, votre pépinière, la météo
   > ☐ Proposer des gestes et des modifications (vous confirmez chacun)
   > Potager : ◉ Les Mésanges ○ Tous mes potagers
   > ⚠️ Ce que Claude lit est envoyé à Anthropic et suit sa politique de confidentialité.
   > [Autoriser] [Refuser]
4. Le connecteur apparaît, avec ses outils, dans l'assistant. Il apparaît aussi dans la
   PWA, menu **Assistants connectés** (US-294).

---

## 2. Consulter : « qu'est-ce que je fais ce week-end ? »

👤 Je vais au jardin samedi matin. Qu'est-ce qui est urgent ?

`⚙️ voir_echeances()`
`↩️ lot 14 tomates Cœur de bœuf : endurcissement depuis 9 j (7 j attendus) — prêt pour le plan ;
lot 17 poireaux : à repiquer depuis 3 j ; rappel « arroser semis carottes » samedi ;
récolte attendue dépassée : radis planche nord (attendue entre le 28/10 et le 02/11)`

`⚙️ voir_meteo()`
`↩️ samedi : 6 °C → 14 °C, sec ; nuit de dimanche à lundi : 1 °C`

🤖 Trois priorités pour samedi :
1. **Radis de la planche nord** : la récolte attendue est dépassée depuis 4 jours,
   ils risquent de devenir creux. À récolter en premier.
2. **Repiquer les poireaux du lot 17**, en retard de 3 jours.
3. **Tomates du lot 14** : l'endurcissement est fait, mais je déconseille de les planter
   maintenant — 1 °C annoncé dans la nuit de dimanche. Gardez-les à l'abri.

Et n'oubliez pas d'arroser les semis de carottes (rappel programmé).

> *Remarque : l'assistant a croisé trois sources sans qu'on le lui demande. C'est la
> valeur principale du canal MCP, en lecture seule.*

---

## 3. Analyser : bilan d'une culture reproductive

👤 Fais-moi le bilan de mes haricots cette saison, avec un graphique.

`⚙️ voir_statistiques(culture="haricot", periode="saison")`
`↩️ haricot nain Contender, planche sud : semis 12/05, 60 graines, 54 pieds levés,
2 pertes (limaces) → 52 pieds actifs ; 11 récoltes du 08/07 au 22/09, cumul 9,4 kg`

`⚙️ consulter_carnet(culture="haricot", type="recolte", periode="saison")`
`↩️ 11 récoltes : 08/07 0,3 kg ; 15/07 0,8 kg ; … ; 22/09 0,2 kg`

🤖 *(tableau + graphique des 11 cueillettes)*
**Haricot nain Contender — planche sud**
- 52 pieds actifs (54 levés, 2 perdus aux limaces) : **les cueillettes n'ont pas fait
  baisser le nombre de pieds**, c'est normal pour une culture reproductive.
- **9,4 kg** en 11 cueillettes, soit environ 180 g par pied.
- Pic fin juillet, puis baisse régulière à partir de mi-août.

---

## 4. Enregistrer un geste : semis puis récoltes successives

### 4.1 Semis en pleine terre (reproducteur)

👤 J'ai semé 40 graines de fèves sur la planche est ce matin.

`⚙️ proposer_geste(type="semis", culture="fève", parcelle="planche est", quantite=40,
unite="graines", mode="pleine_terre", date="2026-11-06")`
`↩️ proposition P-8812 : « Semis fève — planche est — 40 graines en pleine terre — 06/11 ».
Culture reproductive : chaque graine levée donnera un pied qui produira plusieurs récoltes.`

🤖 Je prépare l'enregistrement : **semis de 40 graines de fèves, planche est, en pleine
terre, aujourd'hui**. Je confirme ?

👤 Oui.

`⚙️ confirmer_proposition(id="P-8812")` *(le client demande l'accord : « Autoriser
Assistant Potager à confirmer_proposition ? » → Autoriser)*
`↩️ ✅ Semis enregistré. Rappel proposé : vérifier la levée vers le 20/11.`

🤖 C'est noté ✅. Je vous propose un rappel pour vérifier la levée vers le 20 novembre ;
vous le recevrez sur Telegram si vous l'acceptez dans l'application.

### 4.2 Première, puis N-ième récolte (reproducteur)

👤 *(en mai)* J'ai cueilli 600 g de fèves.

`⚙️ proposer_geste(type="recolte", culture="fève", quantite=0.6, unite="kg")`
`↩️ proposition P-9930 : « Récolte fève — planche est — 0,6 kg ». Pieds actifs : 37 (inchangé).
Cumul saison : 0,6 kg.`

👤 *(une semaine après)* Encore 1,1 kg de fèves.

`↩️ proposition P-9987 : « Récolte fève — planche est — 1,1 kg ». Pieds actifs : 37 (inchangé).
Cumul saison : 1,7 kg.`

### 4.3 Récolte d'une culture végétative (le pied sort)

👤 J'ai arraché 12 poireaux, 1,8 kg.

`⚙️ proposer_geste(type="recolte", culture="poireau", quantite=1.8, unite="kg", pieds=12)`
`↩️ proposition P-9991 : « Récolte poireau — planche nord — 12 pieds, 1,8 kg ». Stock :
48 → 36 pieds.`

> *Le récapitulatif dit toujours ce que devient le stock : il ne baisse pas pour les fèves,
> il baisse pour les poireaux.*

### 4.4 Fin de vie (reproducteur)

👤 Les limaces ont mangé 5 pieds de fèves.

`⚙️ proposer_geste(type="perte", culture="fève", pieds=5, cause="limaces")`
`↩️ proposition : « Perte fève — planche est — 5 pieds (limaces) ». Pieds actifs : 37 → 32.`

---

## 5. Cas où le serveur refuse ou demande

### 5.1 Parcelle inconnue

👤 Note un semis de radis sur la planche ouest.

`⚙️ proposer_geste(type="semis", culture="radis", parcelle="planche ouest", …)`
`↩️ ❓ parcelle « planche ouest » introuvable. Parcelles proches : « planche est »,
« bordure ouest ». Aucune proposition créée.`

🤖 Je ne trouve pas de « planche ouest ». Vous parlez de la **bordure ouest** ou de la
**planche est** ? Si c'est une nouvelle planche, je peux proposer de la créer.

### 5.2 Quantité manquante en pépinière

👤 J'ai semé des tomates en godets.

`↩️ ❓ quantité obligatoire pour un semis en pépinière : combien de godets, ou de graines ?`

### 5.3 Destruction demandée

👤 Supprime la planche test, elle ne sert plus.

`⚙️ ouvrir_dans_l_application(action="parcelle_supprimer", parcelle="planche test")`
`↩️ 🔒 Une suppression se confirme au bouton dans l'application.
Lien : https://potager.eremy.fr/plan?parcelle=planche-test&action=supprimer`

🤖 Je ne peux pas supprimer une parcelle depuis ici : c'est volontaire, pour éviter une
erreur irréversible. Ouvrez ce lien et confirmez au bouton : *(lien)*.

### 5.4 Lecteur sur un potager partagé

👤 Note que j'ai arrosé les courges du jardin de Paul.

`↩️ 🔒 Vous êtes lecteur sur « Jardin de Paul » : rien ne peut être enregistré.`

### 5.5 Question agronomique

👤 Je peux planter de l'ail maintenant ?

`⚙️ voir_calendrier(culture="ail", geste="plantation", date="2026-11-06")`
`↩️ zone 8a : plantation ail d'automne 15/10 → 30/11 ; niveau ★★★ (dans la fenêtre, sol non gelé)`

`⚙️ chercher_connaissance(question="plantation ail automne profondeur espacement")`
`↩️ [agronomie/ail.md] caïeux pointe en haut, 2-3 cm de profondeur, 10-15 cm entre caïeux…`

🤖 Oui, c'est le bon moment dans votre zone (★★★, fenêtre jusqu'au 30/11). Plantez les
caïeux pointe en haut, à 2-3 cm de profondeur, tous les 10 à 15 cm.
*Source : fiche « ail » de l'Assistant Potager.*

---

## 6. Planifier puis accepter geste par geste

👤 Propose-moi un plan de semis en pépinière pour février, avec ce que j'ai en graines.

`⚙️ voir_stock()` · `⚙️ voir_calendrier(mois="2026-02")` · `⚙️ voir_plan()`

🤖 Voici un plan pour février *(tableau : culture, date conseillée, godets, parcelle visée
au printemps, raison)*. Voulez-vous que je prépare les semis ? Je vous les présenterai un
par un.

> *L'assistant planifie librement ; rien n'est écrit tant que le jardinier n'a pas
> confirmé chaque proposition. Le plan reste dans la conversation de l'assistant, pas
> dans l'application (limitation L4).*

---

## 7. Même proposition, trois fenêtres

1. Dans ChatGPT : « J'ai planté 6 courgettes sur la butte » → proposition P-1201.
2. La carte apparaît aussi dans la PWA (panneau du compagnon) et dans Telegram (US-272).
3. Le jardinier confirme au bouton dans Telegram, depuis le jardin.
4. Plus tard, ChatGPT appelle `confirmer_proposition("P-1201")` →
   `↩️ Déjà confirmé depuis Telegram à 18:42.` Rien n'est écrit deux fois.

---

## 8. Ce qu'on ne peut pas faire (et ce que dit l'assistant)

| Demande | Réponse attendue | Limitation |
|---|---|---|
| « Préviens-moi quand il gèlera » | « Je ne peux pas vous écrire de moi-même. Les alertes gel arrivent dans Telegram ou l'application. » | L1 |
| *(photo d'une feuille tachée)* « C'est quoi ? » | L'assistant peut répondre de lui-même, mais rien n'est enregistré ni rapproché du carnet | L3, L9 |
| « Invite ma sœur sur le potager » | Lien vers « Membres » dans l'application | L5 |
| « Annule le dernier semis » | Lien vers la carte, annulation au bouton | L7 |
| « Retiens que je jardine en sol argileux » | Rien n'est retenu par l'application ; c'est la mémoire de l'assistant | L4 |
