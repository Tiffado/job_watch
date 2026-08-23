#!/usr/bin/env python3
"""
Veille quotidienne des offres "data" chez une liste de sociétés,
définie dans companies.json (à côté de ce script).

- Interroge l'API publique de chaque société (Greenhouse / Lever / Ashby /
  Teamtailor) ou une page générique en repli.
- Filtre les intitulés de poste contenant un mot-clé data.
- Maintient jobs_feed.json : la liste de toutes les offres jamais vues,
  chacune avec un statut :
    - "new"     : détectée, pas encore triée
    - "saved"   : marquée comme intéressante depuis l'app mobile
    - "deleted" : écartée depuis l'app mobile
    - "expired" : n'apparaît plus sur le site, jamais triée entre-temps
  Les statuts "saved"/"deleted" ne sont jamais modifiés automatiquement.
- Envoie une notification push via ntfy.sh pour toute offre nouvellement
  détectée (statut "new").

jobs_feed.json est aussi le fichier lu par l'app mobile (web app) pour
afficher les offres à trier.

Conçu pour tourner via GitHub Actions (voir .github/workflows/daily.yml),
mais fonctionne aussi en local : `python3 job_watch.py`
"""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HERE = Path(__file__).parent
COMPANIES_FILE = HERE / "companies.json"
FEED_FILE = HERE / "jobs_feed.json"

KEYWORDS = ["data", "données"]

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


# ---------------------------------------------------------------------------
# RÉCUPÉRATION DES OFFRES PAR PLATEFORME
# ---------------------------------------------------------------------------

def fetch_greenhouse(token: str):
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return [{"title": j["title"], "url": j["absolute_url"]} for j in data.get("jobs", [])]


def fetch_lever(token: str):
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return [{"title": j["text"], "url": j["hostedUrl"]} for j in data]


def fetch_ashby(token: str):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return [
        {"title": j["title"], "url": j.get("jobUrl", j.get("applyUrl", ""))}
        for j in data.get("jobs", [])
    ]


def fetch_teamtailor_html(url: str):
    resp = requests.get(url, timeout=20, headers=BROWSER_HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    jobs = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/jobs/\d+-", href):
            title = a.get_text(strip=True)
            if title and href not in seen:
                full_url = href if href.startswith("http") else f"https://careers.manomano.jobs{href}"
                jobs.append({"title": title, "url": full_url})
                seen.add(href)
    return jobs


def fetch_generic(url: str):
    """Repli générique : signale juste la présence du mot-clé sur la page,
    sans lien précis vers l'offre."""
    resp = requests.get(url, timeout=20, headers=BROWSER_HEADERS)
    resp.raise_for_status()
    html = resp.text.lower()
    if any(k in html for k in KEYWORDS):
        return [{"title": "mot-clé data détecté sur la page (à vérifier manuellement)", "url": url}]
    return []


def fetch_jobs(company: dict):
    try:
        if company["type"] == "greenhouse":
            return fetch_greenhouse(company["token"])
        if company["type"] == "lever":
            return fetch_lever(company["token"])
        if company["type"] == "ashby":
            return fetch_ashby(company["token"])
        if company["type"] == "teamtailor_html":
            return fetch_teamtailor_html(company["url"])
        return fetch_generic(company["url"])
    except Exception as e:
        print(f"[WARN] Échec récupération pour {company['name']}: {e}", file=sys.stderr)
        return []


def matches_keywords(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in KEYWORDS)


# ---------------------------------------------------------------------------
# FEED / NOTIFICATION
# ---------------------------------------------------------------------------

def load_feed():
    if FEED_FILE.exists():
        return json.loads(FEED_FILE.read_text())
    return []


def save_feed(feed):
    FEED_FILE.write_text(json.dumps(feed, indent=2, ensure_ascii=False))


def send_ntfy(new_entries):
    total = len(new_entries)
    lines = [f"{e['company']} : {e['title']}\n  {e['url']}" for e in new_entries]
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
    companies = json.loads(COMPANIES_FILE.read_text())
    feed = load_feed()
    feed_by_id = {entry["id"]: entry for entry in feed}

    today = date.today().isoformat()
    new_entries = []

    for company in companies:
        name = company["name"]
        jobs = fetch_jobs(company)
        matching = [j for j in jobs if matches_keywords(j["title"])]
        current_ids = {j["url"] for j in matching}  # l'URL sert d'identifiant unique

        # Ajoute les offres jamais vues
        for j in matching:
            if j["url"] not in feed_by_id:
                entry = {
                    "id": j["url"],
                    "company": name,
                    "title": j["title"],
                    "url": j["url"],
                    "first_seen": today,
                    "status": "new",
                }
                feed_by_id[j["url"]] = entry
                new_entries.append(entry)

        # Marque comme "expired" les offres "new" qui ne sont plus en ligne
        for entry in feed_by_id.values():
            if entry["company"] == name and entry["status"] == "new" and entry["id"] not in current_ids:
                entry["status"] = "expired"

    updated_feed = list(feed_by_id.values())
    save_feed(updated_feed)

    if new_entries:
        send_ntfy(new_entries)
    else:
        print("[INFO] Aucune nouvelle offre aujourd'hui.")


if __name__ == "__main__":
    main()
