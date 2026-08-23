#!/usr/bin/env python3
"""
Veille quotidienne des offres "data" chez une liste de sociétés,
définie dans companies.json (à côté de ce script).

- Interroge l'API publique de chaque société (Greenhouse / Lever / Ashby)
  ou une page générique en repli.
- Filtre les intitulés de poste contenant un mot-clé data.
- Compare avec le snapshot de la veille (snapshot.json).
- Envoie une notification push via ntfy.sh si du nouveau est détecté.

Conçu pour tourner via GitHub Actions (voir .github/workflows/daily.yml),
mais fonctionne aussi en local : `python3 job_watch.py`
"""

import json
import os
import sys
from pathlib import Path

import requests

HERE = Path(__file__).parent
COMPANIES_FILE = HERE / "companies.json"
SNAPSHOT_FILE = HERE / "snapshot.json"

# Mots-clés qui doivent apparaître dans l'intitulé du poste pour matcher
KEYWORDS = ["data", "données"]

# Topic ntfy.sh : choisis une chaîne unique et difficile à deviner
# (n'importe qui connaissant le topic peut voir tes notifications,
# donc évite "lionel-jobs" et préfère un truc comme "lionel-jw-8f2k1q").
# Défini comme variable d'environnement NTFY_TOPIC (voir workflow GitHub).
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")


# ---------------------------------------------------------------------------
# RÉCUPÉRATION DES OFFRES PAR PLATEFORME
# ---------------------------------------------------------------------------

def fetch_greenhouse(token: str):
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return [
        {"title": j["title"], "url": j["absolute_url"], "id": str(j["id"])}
        for j in data.get("jobs", [])
    ]


def fetch_lever(token: str):
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return [{"title": j["text"], "url": j["hostedUrl"], "id": j["id"]} for j in data]


def fetch_ashby(token: str):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return [
        {
            "title": j["title"],
            "url": j.get("jobUrl", j.get("applyUrl", "")),
            "id": j["id"],
        }
        for j in data.get("jobs", [])
    ]


def fetch_generic(url: str):
    """
    Repli générique et volontairement prudent : télécharge la page et
    signale juste si des mots-clés data apparaissent, sans lien précis
    vers l'offre. À remplacer par greenhouse/lever/ashby dès que tu as
    identifié la vraie plateforme de la société (voir README.md).
    """
    resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    html = resp.text.lower()
    found = any(k in html for k in KEYWORDS)
    if found:
        return [{"title": "mot-clé data détecté (page générique, à vérifier manuellement)", "url": url, "id": url}]
    return []


def fetch_jobs(company: dict):
    try:
        if company["type"] == "greenhouse":
            return fetch_greenhouse(company["token"])
        if company["type"] == "lever":
            return fetch_lever(company["token"])
        if company["type"] == "ashby":
            return fetch_ashby(company["token"])
        return fetch_generic(company["url"])
    except Exception as e:
        print(f"[WARN] Échec récupération pour {company['name']}: {e}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# FILTRAGE / DIFF / NOTIFICATION
# ---------------------------------------------------------------------------

def matches_keywords(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in KEYWORDS)


def load_companies():
    return json.loads(COMPANIES_FILE.read_text())


def load_snapshot():
    if SNAPSHOT_FILE.exists():
        return json.loads(SNAPSHOT_FILE.read_text())
    return {}


def save_snapshot(snapshot):
    SNAPSHOT_FILE.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))


def send_ntfy(new_jobs_by_company: dict):
    total = sum(len(v) for v in new_jobs_by_company.values())
    lines = []
    for company, jobs in new_jobs_by_company.items():
        lines.append(f"{company} :")
        for j in jobs:
            lines.append(f"  - {j['title']}\n    {j['url']}")
    body = "\n".join(lines)

    if not NTFY_TOPIC:
        print("[INFO] NTFY_TOPIC non défini, affichage console uniquement :")
        print(body)
        return

    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers={
                "Title": f"{total} nouvelle(s) offre(s) data".encode("utf-8"),
                "Priority": "default",
                "Tags": "briefcase",
            },
            timeout=20,
        )
        print("[INFO] Notification ntfy envoyée.")
    except Exception as e:
        print(f"[WARN] Échec envoi ntfy: {e}", file=sys.stderr)
        print(body)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    companies = load_companies()
    snapshot = load_snapshot()
    new_snapshot = {}
    new_jobs_by_company = {}

    for company in companies:
        name = company["name"]
        jobs = fetch_jobs(company)
        matching = [j for j in jobs if matches_keywords(j["title"])]

        seen_ids = set(snapshot.get(name, []))
        current_ids = {j["id"] for j in matching}
        new_ids = current_ids - seen_ids

        if new_ids:
            new_jobs_by_company[name] = [j for j in matching if j["id"] in new_ids]

        new_snapshot[name] = list(current_ids)

    if new_jobs_by_company:
        send_ntfy(new_jobs_by_company)
    else:
        print("[INFO] Aucune nouvelle offre aujourd'hui.")

    save_snapshot(new_snapshot)


if __name__ == "__main__":
    main()
