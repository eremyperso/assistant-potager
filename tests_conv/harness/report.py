"""Rapports d'une campagne : JSON archivé, HTML lisible, JUnit XML pour la CI."""
import html
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from .runner import ECHEC, REUSSI, SURVEILLER, ResultatScenario


def _git() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              timeout=5).stdout.strip() or "?"
    except Exception:  # noqa: BLE001
        return "?"


def meta(racine: Path, jetons: dict) -> dict:
    version = (racine / "VERSION").read_text(encoding="utf-8").strip() if (racine / "VERSION").exists() else "?"
    from app import config  # le bot de test tourne avec ce même .env.test
    return {
        "date": datetime.now().isoformat(timespec="seconds"), "version_bot": version, "commit": _git(),
        "agent_mode": config.AGENT_MODE, "modele_agent": config.GROQ_MODELE_PAR_TYPE.get("agent", "?"),
        "jetons": jetons,
    }


def _dict(r: ResultatScenario) -> dict:
    sc = r.scenario
    return {
        "id": sc.id, "titre": sc.titre, "tags": list(sc.tags), "fichier": sc.fichier.name,
        "statut": r.statut, "taux": r.taux, "seuil": sc.seuil,
        "passages": [{
            "numero": p.numero, "ok": p.ok, "erreur": p.erreur,
            "tours": [{
                "numero": t.tour.numero, "ok": t.ok, "erreur": t.erreur,
                "jardinier": t.tour.message or f"[clic] {t.tour.clic}",
                "reponses": t.observation.messages, "boutons": t.observation.boutons,
                "latence_s": round(t.observation.latence_s, 2), "silence": t.observation.silence,
                "outils": list(t.observation.outils), "evenements": t.observation.evenements,
                "verifications": [{"verification": x.verification.libelle, "bloquante": x.verification.bloquante,
                                   "ok": x.ok, "detail": x.detail} for x in t.resultats],
            } for t in p.tours],
        } for p in r.passages],
    }


def ecrire(dossier: Path, resultats: list[ResultatScenario], infos: dict) -> dict[str, Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    donnees = {"meta": infos, "scenarios": [_dict(r) for r in resultats]}
    chemins = {"json": dossier / "rapport.json", "html": dossier / "rapport.html", "junit": dossier / "junit.xml"}
    chemins["json"].write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")
    chemins["html"].write_text(_html(donnees), encoding="utf-8")
    ET.ElementTree(_junit(resultats)).write(chemins["junit"], encoding="utf-8", xml_declaration=True)
    return chemins


def _junit(resultats: list[ResultatScenario]) -> ET.Element:
    racine = ET.Element("testsuite", name="conversations", tests=str(len(resultats)),
                        failures=str(sum(r.statut == ECHEC for r in resultats)))
    for r in resultats:
        cas = ET.SubElement(racine, "testcase", classname="tests_conv", name=f"{r.scenario.id} {r.scenario.titre}")
        if r.statut == ECHEC:
            echecs = [f"passage {p.numero}: {p.erreur or ' ; '.join(x.detail or x.verification.libelle for t in p.tours for x in t.resultats if x.ok is False and x.verification.bloquante) or 'tour sans réponse'}"
                      for p in r.passages if not p.ok]
            ET.SubElement(cas, "failure", message=f"taux {r.taux:.0%} < seuil {r.scenario.seuil:.0%}").text = "\n".join(echecs)
    return racine


_COULEUR = {REUSSI: "ok", SURVEILLER: "warn", ECHEC: "ko"}

_CSS = """
:root{--fond:#fff;--texte:#1b1f1d;--doux:#5d6762;--trait:#d9dfdb;--ok:#1d7a3f;--warn:#a86400;--ko:#b3261e;--carte:#f6f8f6}
@media (prefers-color-scheme:dark){:root{--fond:#141816;--texte:#e6ebe8;--doux:#9aa6a0;--trait:#33403a;--ok:#5fd18a;--warn:#f0b455;--ko:#ff8a80;--carte:#1c2220}}
body{font:15px/1.5 system-ui,sans-serif;background:var(--fond);color:var(--texte);margin:0 auto;max-width:960px;padding:16px}
h1{font-size:1.4rem}h2{font-size:1.1rem;margin:0}section{border:1px solid var(--trait);border-radius:8px;margin:12px 0;padding:12px;background:var(--carte)}
.ok{color:var(--ok)}.warn{color:var(--warn)}.ko{color:var(--ko)}.doux{color:var(--doux);font-size:.9em}
details{margin:6px 0}summary{cursor:pointer}pre{white-space:pre-wrap;background:var(--fond);border:1px solid var(--trait);border-radius:6px;padding:8px}
li.ko,li.ok,li.warn{list-style:none}
"""


def _html(d: dict) -> str:
    e = html.escape
    m = d["meta"]
    comptes = {s: sum(x["statut"] == s for x in d["scenarios"]) for s in (REUSSI, SURVEILLER, ECHEC)}
    lignes = [f"<!doctype html><html lang='fr'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
              f"<title>Rapport conversations</title><style>{_CSS}</style><body>",
              "<h1>Rapport des scénarios conversationnels</h1>",
              f"<p class='doux'>{e(m['date'])} · bot v{e(m['version_bot'])} ({e(m['commit'])}) · agent {e(m['agent_mode'])} · "
              f"modèle {e(str(m['modele_agent']))} · jetons {e(json.dumps(m['jetons']))}</p>",
              f"<p><b class='ok'>{comptes[REUSSI]} réussis</b> · <b class='warn'>{comptes[SURVEILLER]} à surveiller</b> · "
              f"<b class='ko'>{comptes[ECHEC]} en échec</b></p>"]
    for s in d["scenarios"]:
        lignes.append(f"<section><h2><span class='{_COULEUR[s['statut']]}'>{e(s['statut'])}</span> {e(s['id'])} — {e(s['titre'])}</h2>"
                      f"<p class='doux'>{s['taux']:.0%} de passages réussis (seuil {s['seuil']:.0%}) · {e(', '.join(s['tags']))}</p>")
        for p in s["passages"]:
            lignes.append(f"<details {'open' if not p['ok'] else ''}><summary class='{'ok' if p['ok'] else 'ko'}'>"
                          f"Passage {p['numero']} — {'réussi' if p['ok'] else 'échec'}</summary>")
            if p["erreur"]:
                lignes.append(f"<p class='ko'>{e(p['erreur'])}</p>")
            for t in p["tours"]:
                lignes.append(f"<h3 class='{'ok' if t['ok'] else 'ko'}'>Tour {t['numero']}</h3>"
                              f"<pre>Jardinier : {e(t['jardinier'])}\n\nBot ({t['latence_s']} s) :\n{e(chr(10).join(t['reponses']) or '— aucune réponse —')}"
                              f"\n\nBoutons : {e(', '.join(t['boutons']) or '—')}\nOutils : {e(', '.join(t['outils']) or '—')}"
                              f"\nÉvénements écrits : {e(json.dumps(t['evenements'], ensure_ascii=False))}</pre>")
                if t["erreur"]:
                    lignes.append(f"<p class='ko'>{e(t['erreur'])}</p>")
                lignes.append("<ul>")
                for v in t["verifications"]:
                    classe = "warn" if v["ok"] is None else ("ok" if v["ok"] else ("ko" if v["bloquante"] else "warn"))
                    signe = "—" if v["ok"] is None else ("✔" if v["ok"] else "✘")
                    lignes.append(f"<li class='{classe}'>{signe} {e(v['verification'])}"
                                  f"{'' if v['bloquante'] else ' (informative)'} <span class='doux'>{e(v['detail'])}</span></li>")
                lignes.append("</ul>")
            lignes.append("</details>")
        lignes.append("</section>")
    lignes.append("</body></html>")
    return "\n".join(lignes)
