"""Dessin du médaillon-bulle et des logotypes — source unique de tous les exports.

Le médaillon (repère 200 × 200) : une pousse sur des sillons de terre cuite, dans un contour
qui se prolonge en queue de bulle de dialogue (en bas à droite).
"""
import io

VERT = "#1F4D3A"      # vert potager
POUSSE = "#5B8F3A"    # vert pousse
TERRE = "#9E4524"     # terre cuite
LIN = "#F6F1E4"       # lin
KRAFT = "#D8C3A0"     # kraft
POUSSE_CLAIR = "#A8D072"
TERRE_CLAIR = "#E8A583"
ENCRE = "#141413"

PALETTES = {
    "couleur":   dict(anneau=VERT, fa=VERT, fb=POUSSE, sillon=TERRE, texte=VERT),
    "inverse":   dict(anneau=LIN, fa=LIN, fb=POUSSE_CLAIR, sillon=TERRE_CLAIR, texte=LIN),
    "mono-vert": dict(anneau=VERT, fa=VERT, fb=VERT, sillon=VERT, texte=VERT),
    "mono-blanc": dict(anneau="#FFFFFF", fa="#FFFFFF", fb="#FFFFFF", sillon="#FFFFFF", texte="#FFFFFF"),
    "mono-noir": dict(anneau=ENCRE, fa=ENCRE, fb=ENCRE, sillon=ENCRE, texte=ENCRE),
}

# Contour : on part du bas de la queue, on fait presque tout le tour (arc de 338°), puis la queue.
CONTOUR = "M160.4 172 A94 94 0 1 1 183 144.1 L186 192 Z"

# Étendue réelle du dessin (contour compris) dans le repère 200 : utile pour cadrer.
BBOX = (3.5, 3.5, 188.5, 194.5)


def medaillon_interieur(c, simplifie=False):
    """Éléments SVG du médaillon dans le repère 200 × 200 (sans balise <svg>)."""
    a, fa, fb, s = c["anneau"], c["fa"], c["fb"], c["sillon"]
    if not simplifie:
        return (
            f'<path d="{CONTOUR}" fill="none" stroke="{a}" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="100" cy="100" r="85" fill="none" stroke="{a}" stroke-width="1.6"/>'
            f'<path d="M44 142 Q100 124 156 142" fill="none" stroke="{s}" stroke-width="5" stroke-linecap="round"/>'
            f'<path d="M54 158 Q100 142 146 158" fill="none" stroke="{s}" stroke-width="5" stroke-linecap="round"/>'
            f'<path d="M68 172 Q100 160 132 172" fill="none" stroke="{s}" stroke-width="5" stroke-linecap="round"/>'
            f'<path d="M100 130 C100 112 100 98 100 86" fill="none" stroke="{fa}" stroke-width="5" stroke-linecap="round"/>'
            f'<path d="M100 104 C80 104 64 92 62 70 C84 70 98 82 100 104 Z" fill="{fa}"/>'
            f'<path d="M100 90 C100 64 118 46 144 44 C146 70 128 90 100 90 Z" fill="{fb}"/>'
        )
    # Version simplifiée (≤ 48 px) : traits épaissis, un sillon de moins, plus de filet intérieur.
    return (
        f'<path d="{CONTOUR}" fill="none" stroke="{a}" stroke-width="9" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<path d="M44 144 Q100 126 156 144" fill="none" stroke="{s}" stroke-width="9" stroke-linecap="round"/>'
        f'<path d="M58 164 Q100 150 142 164" fill="none" stroke="{s}" stroke-width="9" stroke-linecap="round"/>'
        f'<path d="M100 132 C100 112 100 98 100 86" fill="none" stroke="{fa}" stroke-width="9" stroke-linecap="round"/>'
        f'<path d="M100 104 C80 104 64 92 62 70 C84 70 98 82 100 104 Z" fill="{fa}"/>'
        f'<path d="M100 90 C100 64 118 46 144 44 C146 70 128 90 100 90 Z" fill="{fb}"/>'
    )


def svg(inner, w, h, vb=None, titre=None, extra=""):
    vb = vb or f"0 0 {w} {h}"
    t = f'<title>{titre}</title>' if titre else ""
    role = f' role="img" aria-label="{titre}"' if titre else ' aria-hidden="true"'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" width="{w}" height="{h}"{role}{extra}>{t}{inner}</svg>\n'


def medaillon_svg(palette="couleur", simplifie=False, titre="Médaillon de la marque"):
    return svg(medaillon_interieur(PALETTES[palette], simplifie), 200, 200, titre=titre)


def avatar_interieur():
    """Avatar du compagnon (repère 100 × 100) : disque vert, queue de bulle, pousse sur deux sillons."""
    return (
        f'<circle cx="50" cy="50" r="48" fill="{VERT}"/>'
        f'<path d="M92.4 72.5 L96 98 L75.4 90.7 Z" fill="{VERT}"/>'
        f'<path d="M32 80 Q50 74 68 80" fill="none" stroke="{TERRE_CLAIR}" stroke-width="4" stroke-linecap="round"/>'
        f'<path d="M50 74 V48" fill="none" stroke="{LIN}" stroke-width="4" stroke-linecap="round"/>'
        f'<path d="M50 62 C40 62 32 55 31 44 C41 44 49 51 50 62 Z" fill="{LIN}"/>'
        f'<path d="M50 54 C50 40 60 32 72 31 C73 43 66 54 50 54 Z" fill="{POUSSE_CLAIR}"/>'
    )


def avatar_svg():
    return svg(avatar_interieur(), 100, 100, titre="Avatar de la marque, en bulle")


def fond_icone_interieur(echelle, fond=VERT, taille=512, simplifie=False, arrondi=0):
    """Médaillon inversé centré (anneau au centre) sur un carré plein : icônes d'appli."""
    c = PALETTES["inverse"]
    t = taille / 2 - 100 * echelle
    rect = f'<rect width="{taille}" height="{taille}" rx="{arrondi}" fill="{fond}"/>'
    return rect + f'<g transform="translate({t:.2f} {t:.2f}) scale({echelle})">{medaillon_interieur(c, simplifie)}</g>'


def favicon_svg():
    s = 0.28
    # centre du dessin (et non de l'anneau) au centre de la grille, pour équilibrer la queue
    cx, cy = (BBOX[0] + BBOX[2]) / 2, (BBOX[1] + BBOX[3]) / 2
    inner = (f'<rect width="64" height="64" rx="14" fill="{VERT}"/>'
             f'<g transform="translate({32 - cx * s:.2f} {32 - cy * s:.2f}) scale({s})">'
             f'{medaillon_interieur(PALETTES["inverse"], True)}</g>')
    return svg(inner, 64, 64, titre="Icône de la marque")


# ── Texte en contours (aucune police requise pour afficher les logos exportés) ─────────────────────

def charger_police(chemin, axes):
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    f = TTFont(chemin)
    if "fvar" in f:
        f = instancer.instantiateVariableFont(f, axes, inplace=False)
    buf = io.BytesIO()
    f.save(buf)
    data = buf.getvalue()
    return TTFont(io.BytesIO(data)), data


def texte_en_chemin(police, taille, texte, suivi=0.0):
    """Renvoie (d, largeur, hauteur_capitale) du texte en contours, ligne de base à y = 0, départ x = 0."""
    import uharfbuzz as hb
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    fonte, data = police
    hbfont = hb.Font(hb.Face(data))
    buf = hb.Buffer()
    buf.add_str(texte)
    buf.guess_segment_properties()
    hb.shape(hbfont, buf, {"kern": True, "liga": True})
    upem = fonte["head"].unitsPerEm
    k = taille / upem
    gs = fonte.getGlyphSet()
    ordre = fonte.getGlyphOrder()
    ntos = lambda v: ("%.2f" % v).rstrip("0").rstrip(".")
    x = 0.0
    parts = []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        nom = ordre[info.codepoint]
        pen = SVGPathPen(gs, ntos=ntos)
        gs[nom].draw(TransformPen(pen, (k, 0, 0, -k, x + pos.x_offset * k, -pos.y_offset * k)))
        d = pen.getCommands()
        if d:
            parts.append(d)
        x += pos.x_advance * k + suivi * taille
    largeur = x - suivi * taille
    cap = getattr(fonte["OS/2"], "sCapHeight", 0.7 * upem) * k
    return " ".join(parts), largeur, cap


def logo_empile(police, nom, palette="couleur", taille_texte=64, marge=16):
    c = PALETTES[palette]
    d, tw, cap = texte_en_chemin(police, taille_texte, nom, suivi=-0.01)
    med = 220
    echelle = med / 200
    largeur = max(tw, med) + 2 * marge
    # médaillon centré sur son anneau (x = 100), texte centré
    x_med = (largeur - med) / 2
    y_med = marge
    y_base = marge + med + 26 + cap
    hauteur = y_base + marge
    inner = (f'<g transform="translate({x_med:.2f} {y_med}) scale({echelle})">{medaillon_interieur(c)}</g>'
             f'<path transform="translate({(largeur - tw) / 2:.2f} {y_base:.2f})" d="{d}" fill="{c["texte"]}"/>')
    return svg(inner, round(largeur), round(hauteur), vb=f"0 0 {largeur:.1f} {hauteur:.1f}", titre=nom)


def logo_horizontal(police, nom, palette="couleur", taille_texte=60, marge=16):
    c = PALETTES[palette]
    d, tw, cap = texte_en_chemin(police, taille_texte, nom, suivi=-0.01)
    med = 132
    echelle = med / 200
    ecart = 26
    largeur = marge + med + ecart + tw + marge
    hauteur = med + 2 * marge
    cy = marge + 100 * echelle                # centre de l'anneau
    y_base = cy + cap / 2
    inner = (f'<g transform="translate({marge} {marge}) scale({echelle})">{medaillon_interieur(c)}</g>'
             f'<path transform="translate({marge + med + ecart:.2f} {y_base:.2f})" d="{d}" fill="{c["texte"]}"/>')
    return svg(inner, round(largeur), round(hauteur), vb=f"0 0 {largeur:.1f} {hauteur:.1f}", titre=nom)
