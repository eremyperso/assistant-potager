#!/usr/bin/env python3
"""Génère les exports de l'identité visuelle (médaillon-bulle) : SVG, PNG, ICO, tokens.

Usage :
    python generer_identite.py --polices <dossier contenant Fraunces[...].ttf> --sortie ..
    python generer_identite.py --nom "Mon vrai nom" ...      # change le nom dans tous les logotypes

Dépendances : fonttools, uharfbuzz ; PNG/ICO : rsvg-convert (librsvg) et ImageMagick (convert).
Le médaillon et les icônes ne contiennent aucun texte : seul le logotype porte le nom.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import identite as I  # noqa: E402

NOM_DEFAUT = "Les Bons Gestes"   # nom de travail — à remplacer par le nom définitif de la marque


def ecrire(chemin, contenu):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)
    return chemin


def png(svg_chemin, png_chemin, largeur, fond=None):
    os.makedirs(os.path.dirname(png_chemin), exist_ok=True)
    cmd = ["rsvg-convert", "-w", str(largeur), "-o", png_chemin, svg_chemin]
    if fond:
        cmd[1:1] = ["-b", fond]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nom", default=NOM_DEFAUT)
    ap.add_argument("--polices", required=True, help="dossier contenant Fraunces[SOFT,WONK,opsz,wght].ttf")
    ap.add_argument("--sortie", required=True, help="dossier identite-visuelle/")
    ap.add_argument("--sans-png", action="store_true")
    a = ap.parse_args()

    out = os.path.abspath(a.sortie)
    svg_dir = os.path.join(out, "export", "svg")
    png_dir = os.path.join(out, "export", "png")
    brand = os.path.join(out, "a-copier", "frontend", "public", "brand")
    tmp = os.path.join(out, ".tmp")
    os.makedirs(tmp, exist_ok=True)

    fraunces = glob.glob(os.path.join(a.polices, "Fraunces[[]*.ttf"))
    fraunces = [p for p in fraunces if "Italic" not in os.path.basename(p)]
    if not fraunces:
        sys.exit("Fraunces[…].ttf introuvable dans --polices")
    police = I.charger_police(fraunces[0], {"wght": 600, "opsz": 60, "SOFT": 0, "WONK": 0})

    # ── Médaillon (sans texte) ──
    for pal, nom in [("couleur", "medaillon"), ("inverse", "medaillon-inverse"),
                     ("mono-vert", "medaillon-mono-vert"), ("mono-blanc", "medaillon-mono-blanc"),
                     ("mono-noir", "medaillon-mono-noir")]:
        ecrire(os.path.join(svg_dir, nom + ".svg"), I.medaillon_svg(pal))
    ecrire(os.path.join(svg_dir, "medaillon-simplifie.svg"), I.medaillon_svg("couleur", True))
    ecrire(os.path.join(svg_dir, "medaillon-simplifie-inverse.svg"), I.medaillon_svg("inverse", True))
    ecrire(os.path.join(svg_dir, "avatar-bulle.svg"), I.avatar_svg())

    # ── Logotypes (nom en contours) ──
    for pal, suffixe in [("couleur", ""), ("inverse", "-inverse"), ("mono-vert", "-mono-vert"),
                         ("mono-blanc", "-mono-blanc"), ("mono-noir", "-mono-noir")]:
        ecrire(os.path.join(svg_dir, f"logo-principal{suffixe}.svg"), I.logo_empile(police, a.nom, pal))
        ecrire(os.path.join(svg_dir, f"logo-horizontal{suffixe}.svg"), I.logo_horizontal(police, a.nom, pal))

    # ── Icônes d'appli (carré vert plein, médaillon inversé) ──
    ecrire(os.path.join(brand, "favicon.svg"), I.favicon_svg())
    icone_any = I.svg(I.fond_icone_interieur(1.85, taille=512), 512, 512, titre="Icône de l'application")
    icone_masque = I.svg(I.fond_icone_interieur(1.55, taille=512), 512, 512, titre="Icône de l'application (masquable)")
    ecrire(os.path.join(brand, "icon.svg"), icone_any)
    ecrire(os.path.join(brand, "icon-maskable.svg"), icone_masque)

    # ── Tokens ──
    tokens = {
        "marque": {"vert-potager": I.VERT, "vert-pousse": I.POUSSE, "terre-cuite": I.TERRE,
                   "lin": I.LIN, "kraft": I.KRAFT},
        "logo": {
            "clair": {"anneau": I.VERT, "feuille-a": I.VERT, "feuille-b": I.POUSSE, "sillon": I.TERRE},
            "sombre": {"anneau": "#E4EDD3", "feuille-a": "#E4EDD3", "feuille-b": "#A9D47A", "sillon": I.TERRE_CLAIR},
        },
        "typographie": {"logotype": "Fraunces 600", "interface": "Lora (titres) + police système (texte)"},
        "nom": a.nom,
    }
    ecrire(os.path.join(out, "tokens", "brand.json"), json.dumps(tokens, ensure_ascii=False, indent=2) + "\n")

    manifest = {
        "name": "Assistant Potager", "short_name": "Potager", "lang": "fr", "display": "standalone",
        "start_url": "/", "background_color": I.LIN, "theme_color": I.VERT,
        "icons": [
            {"src": "/brand/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/brand/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/brand/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    ecrire(os.path.join(brand, "manifest.webmanifest"), json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    if not a.sans_png:
        s = lambda *p: os.path.join(svg_dir, *p)
        png(s("medaillon.svg"), os.path.join(png_dir, "medaillon-512.png"), 512)
        png(s("medaillon-inverse.svg"), os.path.join(png_dir, "medaillon-inverse-512.png"), 512)
        png(s("logo-principal.svg"), os.path.join(png_dir, "logo-principal-1200.png"), 1200)
        png(s("logo-principal-inverse.svg"), os.path.join(png_dir, "logo-principal-inverse-1200.png"), 1200)
        png(s("logo-horizontal.svg"), os.path.join(png_dir, "logo-horizontal-1200.png"), 1200)
        png(s("logo-horizontal-inverse.svg"), os.path.join(png_dir, "logo-horizontal-inverse-1200.png"), 1200)
        png(s("avatar-bulle.svg"), os.path.join(png_dir, "avatar-bulle-512.png"), 512)
        png(os.path.join(brand, "icon.svg"), os.path.join(brand, "icon-512.png"), 512)
        png(os.path.join(brand, "icon.svg"), os.path.join(brand, "icon-192.png"), 192)
        png(os.path.join(brand, "icon.svg"), os.path.join(brand, "apple-touch-icon.png"), 180)
        png(os.path.join(brand, "icon-maskable.svg"), os.path.join(brand, "icon-maskable-512.png"), 512)
        for t in (16, 32, 48):
            png(os.path.join(brand, "favicon.svg"), os.path.join(tmp, f"fav-{t}.png"), t)
        shutil.copy(os.path.join(tmp, "fav-32.png"), os.path.join(brand, "favicon-32.png"))
        subprocess.run(["convert", os.path.join(tmp, "fav-16.png"), os.path.join(tmp, "fav-32.png"),
                        os.path.join(tmp, "fav-48.png"), os.path.join(brand, "favicon.ico")], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print("OK →", out)


if __name__ == "__main__":
    main()
