"""
DigiBest Apollo Targeting Runner

Zweck:
- liest Suchprofile aus digibest_apollo_steuerdatei.xlsx
- fragt später die Apollo API ab
- bewertet Treffer mit einfacher DigiBest-Scoringlogik
- exportiert Ergebnisse als CSV

Vorbereitung:
1) pip install requests python-dotenv pandas openpyxl
2) Datei .env im gleichen Ordner anlegen:
   APOLLO_API_KEY=Ihr_Apollo_API_Key
3) Steuerdatei anpassen
4) Skript starten:
   python apollo_targeting_runner.py

Hinweis:
Die API-Endpunkte/Parameter können je nach Apollo-Plan variieren.
Dieses Skript ist bewusst defensiv gebaut: erst kleine Suchmengen testen.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
CONTROL_FILE = BASE_DIR / "digibest_apollo_steuerdatei.xlsx"
OUTPUT_FILE = BASE_DIR / "apollo_digibest_ergebnisse.csv"
APOLLO_BASE_URL = "https://api.apollo.io/api/v1"


@dataclass
class SearchProfile:
    name: str
    country: str
    industry_keywords: list[str]
    plus_keywords: list[str]
    minus_keywords: list[str]
    role_profile: str
    employee_min: int
    employee_max: int
    max_companies: int
    max_people_per_company: int


def split_keywords(value: Any) -> list[str]:
    if pd.isna(value) or value is None:
        return []
    return [x.strip() for x in str(value).split(",") if x.strip()]


def load_profiles(path: Path) -> list[SearchProfile]:
    df = pd.read_excel(path, sheet_name="01_Suchprofile")
    df = df[df["aktiv"].astype(str).str.lower().str.strip() == "ja"]
    profiles: list[SearchProfile] = []
    for _, row in df.iterrows():
        profiles.append(
            SearchProfile(
                name=str(row["suchprofil"]),
                country=str(row.get("land", "Deutschland")),
                industry_keywords=split_keywords(row.get("branche_keywords")),
                plus_keywords=split_keywords(row.get("firmen_keywords_plus")),
                minus_keywords=split_keywords(row.get("firmen_keywords_minus")),
                role_profile=str(row.get("rollenprofil", "GF_Vertrieb")),
                employee_min=int(row.get("mitarbeiter_min", 20)),
                employee_max=int(row.get("mitarbeiter_max", 1000)),
                max_companies=int(row.get("max_firmen", 25)),
                max_people_per_company=int(row.get("max_personen_je_firma", 3)),
            )
        )
    return profiles


def apollo_headers(api_key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": api_key,
    }


def search_organizations(api_key: str, profile: SearchProfile) -> list[dict[str, Any]]:
    """Apollo Organization Search.

    Je nach Apollo-Plan kann es nötig sein, Parameter anzupassen.
    Falls Apollo einen 400er liefert, zuerst Payload ausgeben und mit Apollo-Doku abgleichen.
    """
    query_terms = profile.industry_keywords + profile.plus_keywords
    payload = {
        "q_organization_keyword_tags": query_terms[:20],
        "organization_locations": [profile.country],
        "organization_num_employees_ranges": [
            f"{profile.employee_min},{profile.employee_max}"
        ],
        "page": 1,
        "per_page": min(profile.max_companies, 100),
    }

    url = f"{APOLLO_BASE_URL}/mixed_companies/search"
    response = requests.post(url, headers=apollo_headers(api_key), json=payload, timeout=45)
    if response.status_code >= 400:
        raise RuntimeError(
            f"Apollo Organization Search fehlgeschlagen ({response.status_code}): {response.text[:1000]}\nPayload: {payload}"
        )
    data = response.json()
    return data.get("organizations") or data.get("accounts") or []


def search_people_for_org(api_key: str, org: dict[str, Any], profile: SearchProfile, role_keywords: list[str]) -> list[dict[str, Any]]:
    org_id = org.get("id")
    domain = org.get("primary_domain") or org.get("website_url") or org.get("domain")

    payload: dict[str, Any] = {
        "page": 1,
        "per_page": min(profile.max_people_per_company, 10),
        "person_titles": role_keywords[:20],
        "person_locations": [profile.country],
    }
    if org_id:
        payload["organization_ids"] = [org_id]
    elif domain:
        payload["q_organization_domains"] = [clean_domain(domain)]
    else:
        return []

    url = f"{APOLLO_BASE_URL}/mixed_people/search"
    response = requests.post(url, headers=apollo_headers(api_key), json=payload, timeout=45)
    if response.status_code >= 400:
        # Keine harte Vollbremsung wegen einzelner Firma.
        print(f"Warnung: People Search für {org.get('name')} fehlgeschlagen: {response.status_code}")
        return []
    data = response.json()
    return data.get("people") or data.get("contacts") or []


def clean_domain(value: str) -> str:
    value = re.sub(r"^https?://", "", str(value).strip(), flags=re.I)
    value = re.sub(r"^www\.", "", value, flags=re.I)
    return value.split("/")[0]


def contains_any(text: str, keywords: list[str]) -> list[str]:
    text_low = text.lower()
    hits = []
    for kw in keywords:
        if kw.lower() in text_low:
            hits.append(kw)
    return hits


def score_organization(org: dict[str, Any], profile: SearchProfile) -> dict[str, Any]:
    text_parts = [
        org.get("name", ""),
        org.get("short_description", ""),
        org.get("seo_description", ""),
        org.get("industry", ""),
        org.get("keywords", ""),
        org.get("website_url", ""),
    ]
    text = " ".join(str(x) for x in text_parts if x)

    plus_hits = contains_any(text, profile.plus_keywords)
    minus_hits = contains_any(text, profile.minus_keywords)

    score = 0
    score += min(len(plus_hits) * 10, 70)
    score -= min(len(minus_hits) * 20, 70)

    employees = org.get("estimated_num_employees") or org.get("num_employees")
    if employees:
        try:
            employees_int = int(employees)
            if profile.employee_min <= employees_int <= profile.employee_max:
                score += 10
        except (TypeError, ValueError):
            pass

    score = max(0, min(score, 100))
    if score >= 80:
        cls = "A"
        rec = "kontaktieren"
    elif score >= 60:
        cls = "B"
        rec = "prüfen/kontaktieren"
    elif score >= 40:
        cls = "C"
        rec = "beobachten/prüfen"
    else:
        cls = "D"
        rec = "ausschließen"

    return {
        "score": score,
        "klasse": cls,
        "positive_signale": "; ".join(plus_hits),
        "negative_signale": "; ".join(minus_hits),
        "empfehlung": rec,
    }


def load_role_keywords(path: Path) -> dict[str, list[str]]:
    df = pd.read_excel(path, sheet_name="03_Rollen")
    result = {}
    for _, row in df.iterrows():
        result[str(row["rollenprofil"])] = split_keywords(row["jobtitel_keywords"])
    return result


def build_result_row(profile: SearchProfile, org: dict[str, Any], person: dict[str, Any] | None, scoring: dict[str, Any]) -> dict[str, Any]:
    return {
        "suchprofil": profile.name,
        "firma": org.get("name"),
        "domain": clean_domain(org.get("website_url") or org.get("primary_domain") or ""),
        "apollo_org_id": org.get("id"),
        "land": profile.country,
        "stadt": org.get("city"),
        "branche": org.get("industry"),
        "mitarbeiter": org.get("estimated_num_employees") or org.get("num_employees"),
        "beschreibung": org.get("short_description") or org.get("seo_description"),
        "personen_name": person.get("name") if person else "",
        "personen_titel": person.get("title") if person else "",
        "linkedin": person.get("linkedin_url") if person else "",
        "email_status": person.get("email_status") if person else "nicht gezogen",
        "score": scoring["score"],
        "klasse": scoring["klasse"],
        "positive_signale": scoring["positive_signale"],
        "negative_signale": scoring["negative_signale"],
        "empfehlung": scoring["empfehlung"],
        "naechster_schritt": "Website prüfen und Ansprechpartner validieren" if scoring["klasse"] in ["A", "B"] else "nicht priorisieren",
        "quelle": "Apollo/API",
    }


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        raise SystemExit("APOLLO_API_KEY fehlt. Bitte .env-Datei im Skriptordner anlegen.")
    if not CONTROL_FILE.exists():
        raise SystemExit(f"Steuerdatei nicht gefunden: {CONTROL_FILE}")

    profiles = load_profiles(CONTROL_FILE)
    role_map = load_role_keywords(CONTROL_FILE)
    results: list[dict[str, Any]] = []

    for profile in profiles:
        print(f"Starte Suchprofil: {profile.name}")
        orgs = search_organizations(api_key, profile)
        print(f"  Firmen gefunden: {len(orgs)}")
        role_keywords = role_map.get(profile.role_profile, [])

        for org in orgs:
            org_score = score_organization(org, profile)
            people = []
            if org_score["klasse"] in ["A", "B", "C"] and role_keywords:
                people = search_people_for_org(api_key, org, profile, role_keywords)
                time.sleep(0.3)

            if people:
                for person in people:
                    results.append(build_result_row(profile, org, person, org_score))
            else:
                results.append(build_result_row(profile, org, None, org_score))

        time.sleep(0.5)

    out = pd.DataFrame(results)
    out.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig", sep=";")
    print(f"Fertig. Ergebnis gespeichert: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
