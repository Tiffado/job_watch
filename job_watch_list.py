#!/usr/bin/env python3
"""
job_watch_list.py — version simplifiée sans comparaison ni notification.

Interroge chaque société définie dans companies.json et affiche toutes
les offres actuellement ouvertes dont l'intitulé contient un mot-clé data.
Ne lit ni n'écrit aucun snapshot, n'envoie aucune notification.

Usage :
    python3 job_watch_list.py
"""

import json
import sys
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HERE = Path(__file__).parent
COMPANIES_FILE = HERE / "companies.json"

KEYWORDS = ["data", "données"]


def fetch_greenhouse(token: str):
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return [
        {"title": j["title"], "url": j["absolute_url"]}
        for j in data.get("jobs", [])
    ]


def fetch_lever(token: str):
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return [{"title": j["text"], "url": j["hostedUrl"]} for j in data]


def fetch_lever_html(token: str):
    """
    Repli pour les sociétés qui exposent leur page Lever publique
    (jobs.lever.co/TOKEN) mais bloquent l'API JSON. Parse le HTML de la
    page hébergée directement.
    """
    url = f"https://jobs.lever.co/{token}"
    resp = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        },
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    jobs = []
    for a in soup.select("a.posting-title"):
        title_el = a.select_one("h5")
        title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
        href = a.get("href", url)
        jobs.append({"title": title, "url": href})
    return jobs


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
    """
    Sites Teamtailor (ex: ManoMano) : la page /jobs liste les offres en
    HTML statique, pas besoin de JS. On cherche les liens dont l'URL
    contient '/jobs/<id>-<slug>'.
    """
    resp = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        },
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    jobs = []
    seen_urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/jobs/\d+-", href):
            title = a.get_text(strip=True)
            if title and href not in seen_urls:
                full_url = href if href.startswith("http") else f"https://careers.manomano.jobs{href}"
                jobs.append({"title": title, "url": full_url})
                seen_urls.add(href)
    return jobs


def fetch_generic(url: str):
    """
    Repli générique : signale juste la présence du mot-clé sur la page,
    sans lien précis vers l'offre. À remplacer par greenhouse/lever/ashby
    dès que la vraie plateforme est identifiée (voir README.md).
    """
    resp = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        },
    )
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
        if company["type"] == "lever_html":
            return fetch_lever_html(company["token"])
        if company["type"] == "teamtailor_html":
            return fetch_teamtailor_html(company["url"])
        if company["type"] == "ashby":
            return fetch_ashby(company["token"])
        return fetch_generic(company["url"])
    except Exception as e:
        print(f"[WARN] Échec récupération pour {company['name']}: {e}", file=sys.stderr)
        return None  # None = erreur, différent de [] = pas d'offre


def matches_keywords(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in KEYWORDS)


def main():
    companies = json.loads(COMPANIES_FILE.read_text())

    total_matches = 0
    for company in companies:
        name = company["name"]
        jobs = fetch_jobs(company)

        print(f"\n== {name} ==")
        if jobs is None:
            print("  (échec de récupération, voir warning ci-dessus)")
            continue

        matching = [j for j in jobs if matches_keywords(j["title"])]
        if not matching:
            print("  (aucune offre data ouverte actuellement)")
            continue

        for j in matching:
            print(f"  - {j['title']}")
            print(f"    {j['url']}")
        total_matches += len(matching)

    print(f"\nTotal : {total_matches} offre(s) data trouvée(s) sur {len(companies)} société(s).")


if __name__ == "__main__":
    main()
