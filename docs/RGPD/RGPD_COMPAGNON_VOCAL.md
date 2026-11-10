# Le compagnon vocal de la PWA — paragraphe destiné à la politique de confidentialité

**Produit par US-299 (CA10, étude ÉPIC 17 §7). À intégrer par US-132 (RGPD & conformité), avec
`RGPD_CARNET_COMPAGNON.md`, `RGPD_ASSISTANTS_IA_MCP.md` et `RGPD_FEDERATION_GOOGLE.md`.**

Dans la PWA, le jardinier peut dicter un message à son compagnon et écouter sa réponse. Cette
fiche dit où part la voix, ce que nous gardons, et ce que nous ne savons pas encore.

---

## Paragraphe à insérer — « Parler à votre compagnon »

> Quand vous dictez un message dans l'application, l'enregistrement de votre voix est envoyé à
> **Mistral AI**, qui le transforme en texte. Ce prestataire traite déjà les messages écrits
> du compagnon. Nous ne gardons pas l'enregistrement : il n'est jamais écrit dans notre base de
> données. Si le serveur doit changer le format du fichier avant l'envoi, la copie de travail est
> supprimée juste après, même en cas d'erreur.
>
> Le texte obtenu est traité comme un message écrit : il suit les règles du carnet et de
> l'historique du compagnon.
>
> Quand le compagnon vous répond à voix haute, le texte de sa réponse est envoyé à Mistral AI,
> qui le transforme en voix. Le son reçu est joué puis oublié : nous ne le gardons pas.
>
> **Hébergement de l'audio** : Mistral AI propose des serveurs en Europe, mais sa documentation ne
> dit pas que l'audio y est traité. Nous ne pouvons donc pas vous garantir que votre voix reste en
> Europe. La durée pendant laquelle Mistral AI garde les fichiers audio n'est pas non plus décrite
> dans les pages que nous avons lues.
>
> Les voix du compagnon sont des voix de synthèse proposées par Mistral AI. Votre voix n'est
> jamais copiée ni imitée : aucune donnée biométrique n'est créée.
>
> Si vous ne voulez pas que votre voix quitte l'application, écrivez vos messages : le compagnon
> fonctionne de la même façon.

---

## Pour l'équipe

- **Traitement** : dictée (audio → texte, type d'appel `dictee`) et synthèse (texte → MP3, type
  d'appel `voix`), par `app/services/voix/` et `llm/passerelle.py`. Le bot Telegram n'est pas
  concerné : il garde Groq Whisper et gTTS.
- **Sous-traitant** : Mistral AI (`api.mistral.ai`), déjà sous-traitant du chat. Hébergement
  européen de l'audio **non confirmé** (étude §3.3, contrainte C5) : à revoir si Mistral publie
  la liste des modèles audio servis par `api.eu.mistral.ai`.
- **Ce qui est conservé chez nous** : une ligne `conso_tokens` par appel (type, modèle, durée de
  l'audio en secondes ou nombre de caractères, latence, issue). Jamais l'audio, jamais le texte
  dans les journaux.
- **Fichiers temporaires** : seulement pour une conversion FFmpeg (`VOIX_FORMATS_A_CONVERTIR`),
  dans un dossier supprimé à la sortie de la conversion, erreur comprise.
- **Base légale** : exécution du service demandé par le jardinier (il appuie sur le micro ou sur
  ▶). Le choix d'une voix (US-300) est une préférence du compte, supprimée avec lui.
- **Pas de clonage de voix** (décision D2 de l'étude) : aucune donnée biométrique.
