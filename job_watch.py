#!/usr/bin/env python3
"""
Veille quotidienne des offres "data" chez une liste de sociétés,
définie dans companies.json (à côté de ce script).

- Interroge l'API publique de chaque société (Greenhouse / Lever / Ashby /
  SmartRecruiters / Workable /
  Teamtailor) ou une page générique en repli.
- Filtre les intitulés de poste contenant un mot-clé data, hors stages et
  alternances.
- Maintient jobs_feed.json : la liste de toutes les offres jamais vues,
  chacune avec un statut :
    - "new"     : détectée, pas encore triée
    - "saved"   : marquée comme intéressante depuis l'app mobile
    - "applied" : candidature envoyée (app mobile)
    - "deleted" : écartée depuis l'app mobile
    - "expired" : n'apparaît plus sur le site, jamais triée entre-temps
  Seules les offres "new" et "expired" sont modifiées automatiquement
  ("new" -> "expired" quand l'offre disparaît, "expired" -> "new" quand elle
  revient), et jamais pour une société dont la récupération a échoué.
- Envoie une notification push via ntfy.sh pour toute offre nouvellement
  détectée (statut "new").

jobs_feed.json est aussi le fichier lu par l'app mobile (web app) pour
afficher les offres à trier.

Usage :
    python job_watch.py               met à jour le feed et notifie
    python job_watch.py --no-notify   met à jour le feed, écrit new_entries.json
    python job_watch.py --notify-only notifie les offres de new_entries.json

GitHub Actions (voir .github/workflows/daily.yml) utilise les deux dernières
formes : la notification n'est envoyée qu'une fois le feed poussé.
"""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

HERE = Path(__file__).parent
COMPANIES_FILE = HERE / "companies.json"
FEED_FILE = HERE / "jobs_feed.json"
# Offres détectées au dernier run, pour notifier après l'enregistrement du feed.
NEW_ENTRIES_FILE = HERE / "new_entries.json"

KEYWORDS = ["data", "données"]

# Intitulé "data" : mot qui commence par data (data, dataops, database…) ou
# "données", mais pas les postes de datacenter / datacentre.
DATA_PATTERN = re.compile(r"\bdata(?!cent)|données", re.IGNORECASE)

# Contrats étudiants : exclus même si l'intitulé contient un mot-clé data.
# Mots entiers uniquement, pour ne pas écarter "International" ou "Internal".
EXCLUDED_PATTERN = re.compile(
    r"\b(intern|internship|stage|stagiaire|apprenti|apprentie|apprentissage"
    r"|apprentice|apprenticeship|alternance|alternant|alternante)\b",
    re.IGNORECASE,
)

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
    return [
        {"title": j["title"], "url": j["absolute_url"], "location": j.get("location", {}).get("name", "")}
        for j in data.get("jobs", [])
    ]


def fetch_lever(token: str):
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return [
        {"title": j["text"], "url": j["hostedUrl"], "location": j.get("categories", {}).get("location", "")}
        for j in data
    ]


def fetch_ashby(token: str):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return [
        {"title": j["title"], "url": j.get("jobUrl", j.get("applyUrl", "")), "location": j.get("location", "")}
        for j in data.get("jobs", [])
    ]


def fetch_smartrecruiters(token: str):
    """API publique SmartRecruiters, paginée par 100 offres."""
    jobs = []
    offset = 0
    while True:
        url = f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100&offset={offset}"
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        for p in data.get("content", []):
            jobs.append({
                "title": p["name"],
                "url": f"https://jobs.smartrecruiters.com/{token}/{p['id']}",
                "location": p.get("location", {}).get("fullLocation", ""),
            })
        offset += 100
        if offset >= data.get("totalFound", 0):
            return jobs


def fetch_workable(token: str):
    """API publique du widget Workable."""
    url = f"https://apply.workable.com/api/v1/widget/accounts/{token}"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return [
        {"title": j["title"], "url": j["url"], "location": f"{j.get('city', '')}, {j.get('country', '')}"}
        for j in data.get("jobs", [])
    ]


def fetch_successfactors_rss(base_url: str, cities: list):
    """Sites carrières SAP SuccessFactors : flux RSS de recherche, une requête par ville.

    Le flux renvoie au plus 20 offres par requête (les plus récentes) ; filtrer sur
    "data" et sur une ville garde chaque requête sous cette limite. L'intitulé
    du flux contient le lieu entre parenthèses : "Data Engineer (ROUBAIX, FR, 59100)".
    """
    jobs = {}
    for city in cities:
        url = f"{base_url}/services/rss/job/?locale=fr_FR&keywords=(data) AND ({city})"
        resp = requests.get(url, timeout=20, headers=BROWSER_HEADERS)
        resp.raise_for_status()
        for item in ElementTree.fromstring(resp.content).iter("item"):
            raw_title = item.findtext("title", "")
            title, _, location = raw_title.rpartition(" (")
            link = item.findtext("link", "").split("?")[0]  # sans les paramètres de suivi
            jobs[link] = {"title": title or raw_title, "url": link, "location": location.rstrip(")")}
    return list(jobs.values())


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
    """Renvoie la liste des offres, ou None si la récupération a échoué.

    None et [] ne veulent pas dire la même chose : [] signifie "aucune offre en
    ligne" (les offres "new" de la société peuvent expirer), None signifie "on ne
    sait pas" (on ne touche à rien pour cette société).
    """
    try:
        if company["type"] == "greenhouse":
            return fetch_greenhouse(company["token"])
        if company["type"] == "lever":
            return fetch_lever(company["token"])
        if company["type"] == "ashby":
            return fetch_ashby(company["token"])
        if company["type"] == "smartrecruiters":
            return fetch_smartrecruiters(company["token"])
        if company["type"] == "workable":
            return fetch_workable(company["token"])
        if company["type"] == "successfactors_rss":
            return fetch_successfactors_rss(company["url"], company["cities"])
        if company["type"] == "teamtailor_html":
            return fetch_teamtailor_html(company["url"])
        return fetch_generic(company["url"])
    except Exception as e:
        print(f"[WARN] Échec récupération pour {company['name']}: {e}", file=sys.stderr)
        return None


def matches_keywords(title: str) -> bool:
    if EXCLUDED_PATTERN.search(title):
        return False
    return bool(DATA_PATTERN.search(title))


# Communes de la métropole lilloise, et télétravail, pour les sociétés marquées
# "lille_only" dans companies.json (groupes avec de nombreux sites ailleurs).
LILLE_AREA = [
    "lille", "villeneuve-d'ascq", "villeneuve d'ascq", "lesquin", "hem", "marcq", "croix",
    "roubaix", "tourcoing", "lezennes", "ronchin", "wasquehal", "lambersart", "seclin",
    "remote", "télétravail", "teletravail",
]


def in_lille_area(location: str) -> bool:
    words = re.findall(r"[\w'-]+", location.lower())
    text = " ".join(words)
    return any(re.search(rf"\b{re.escape(place)}\b", text) for place in LILLE_AREA)


def is_relevant(job: dict, company: dict) -> bool:
    if not matches_keywords(job["title"]):
        return False
    if company.get("lille_only"):
        # Certains job boards laissent le lieu vide et le mettent dans l'intitulé
        # ("Lead Data Engineer Lille") : on regarde les deux.
        return in_lille_area(f"{job.get('location', '')} {job['title']}")
    return True


# ---------------------------------------------------------------------------
# FEED / NOTIFICATION
# ---------------------------------------------------------------------------

def load_feed():
    if FEED_FILE.exists():
        return json.loads(FEED_FILE.read_text(encoding="utf-8"))
    return []


def save_feed(feed):
    FEED_FILE.write_text(json.dumps(feed, indent=2, ensure_ascii=False), encoding="utf-8")


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

def update_feed(feed, companies, fetch=fetch_jobs, today=None):
    """Met à jour le feed à partir des offres en ligne.

    Renvoie (feed mis à jour, offres nouvellement détectées).
    """
    feed_by_id = {entry["id"]: entry for entry in feed}
    today = today or date.today().isoformat()
    new_entries = []

    for company in companies:
        name = company["name"]
        jobs = fetch(company)
        if jobs is None:
            # Récupération en échec : on ne sait pas ce qui est en ligne,
            # donc on n'ajoute ni n'expire rien pour cette société.
            continue
        matching = [j for j in jobs if is_relevant(j, company)]
        current_ids = {j["url"] for j in matching}  # l'URL sert d'identifiant unique

        # Ajoute les offres jamais vues ; remet à trier une offre expirée qui
        # est de nouveau en ligne (sans renotifier : elle l'a déjà été).
        for j in matching:
            existing = feed_by_id.get(j["url"])
            if existing and existing["status"] == "expired":
                existing["status"] = "new"
            elif not existing:
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

    return list(feed_by_id.values()), new_entries


def main():
    parser = argparse.ArgumentParser(description="Veille quotidienne des offres data.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--no-notify",
        action="store_true",
        help="met à jour le feed sans notifier (les nouvelles offres sont écrites dans new_entries.json)",
    )
    group.add_argument(
        "--notify-only",
        action="store_true",
        help="notifie les offres de new_entries.json sans interroger les sociétés",
    )
    args = parser.parse_args()

    if args.notify_only:
        new_entries = json.loads(NEW_ENTRIES_FILE.read_text(encoding="utf-8"))
    else:
        companies = json.loads(COMPANIES_FILE.read_text(encoding="utf-8"))
        feed, new_entries = update_feed(load_feed(), companies)
        save_feed(feed)
        NEW_ENTRIES_FILE.write_text(json.dumps(new_entries, indent=2, ensure_ascii=False), encoding="utf-8")
        if args.no_notify:
            print(f"[INFO] {len(new_entries)} nouvelle(s) offre(s), notification différée.")
            return

    if new_entries:
        send_ntfy(new_entries)
    else:
        print("[INFO] Aucune nouvelle offre aujourd'hui.")


if __name__ == "__main__":
    main()
