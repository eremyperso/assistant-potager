# Identité visuelle — « Les bons gestes »

Médaillon-bulle (piste A, « Le Geste ») : une pousse sur des sillons de terre cuite, dans un contour
qui se prolonge en queue de bulle de dialogue. Produit avec Claude Design, **intégré à l'appli**.

## Où vit quoi

| Élément | Emplacement |
|---|---|
| Composants `MedaillonBulle`, `LogoMark`, `AvatarBulle` | `frontend/src/components/brand/` |
| Variables `--logo-*` et palette de marque | `frontend/src/brand.css` (importé dans `main.jsx`) |
| Favicon, icône Apple, icônes 192 / 512 / masquable | `frontend/public/brand/` (servies sous `/brand` par `app/api/main.py`) |
| Logos et médaillon à usage externe (SVG, PNG) | `export/` (ce dossier) |
| Palette pour d'autres outils | `tokens/brand.json` |
| Script qui régénère tout | `source/` |

Les logotypes exportés (`logo-*.svg`) ont le nom **en contours** : aucune police à installer. Le
médaillon, les icônes et l'avatar ne contiennent aucun texte.

## État de l'intégration

- `LogoMark` (médaillon + nom) sert sur les écrans de connexion, d'accueil et d'activation du
  compagnon ; `MedaillonBulle` (variante `inverse`) sert dans le bandeau supérieur.
- Le nom affiché est **« Les bons gestes »** (défaut de `LogoMark`, titre de page, e-mails, bot, API).
- Pas de PWA (retirée, US-274) : `icon-192`, `icon-512` et `icon-maskable` sont copiées mais non
  référencées, et le `manifest.webmanifest` n'a pas été repris. À brancher le jour où l'installation
  sur l'écran d'accueil est voulue (lien `<link rel="manifest">` + manifeste adapté).
- `AvatarBulle` (queue de bulle sur l'avatar de Gaston) n'est pas utilisé : optionnel.
- La palette de l'interface n'est pas changée : les verts du logo (`#1F4D3A`, `#5B8F3A`) restent
  proches mais distincts de `--brand` / `--brand-deep`.

## Telegram

`export/png/avatar-bulle-512.png` (disque vert, pousse, queue de bulle) convient pour la photo du
bot. Le nom du bot se change dans BotFather.

## Gaston

Gaston, la carotte, garde son dessin et son rôle : il est la voix du compagnon. La bulle est la
signature de la marque, pas sa remplaçante.

## Changer le nom

```
pip install fonttools uharfbuzz
python source/generer_identite.py --nom "Nouveau nom" --polices <dossier avec Fraunces[SOFT,WONK,opsz,wght].ttf> --sortie .
```

Fraunces est sous licence libre (OFL), téléchargeable sur Google Fonts. Les PNG et l'ICO demandent
aussi `rsvg-convert` et ImageMagick (`--sans-png` pour ne produire que les SVG).

Le script recrée un dossier `a-copier/` (composants, `brand.css`, icônes) : le recopier dans
`frontend/` puis le supprimer. Changer aussi le défaut de `nom` dans `LogoMark.jsx`.

## Règles d'usage

- **Zone de protection** : au moins la largeur de la queue de bulle (≈ 1/8 du médaillon) tout autour.
- **Taille minimale** : médaillon 16 px (version simplifiée automatique jusqu'à 48 px) ; logotype
  horizontal 120 px de large.
- **Fonds** : version couleur sur lin ou blanc ; version inversée sur le vert `#1F4D3A` ou en mode
  sombre ; mono quand une seule couleur est possible (tampon, gravure, fax).
- **À ne pas faire** : recolorer les feuilles ou les sillons, retirer ou déplacer la queue de bulle,
  étirer le médaillon, poser la version couleur sur un fond vert moyen.
