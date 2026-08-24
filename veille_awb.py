#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Veille Attijariwafa bank -> Telegram
100% gratuit : GitHub Actions (cron) + RSS + Telegram Bot API.

Etat persistant : seen.json, commit dans le depot a chaque run.
"""

import os, json, time, hashlib, html, re, sys
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
import urllib.request
import feedparser

# ----------------------------------------------------------------------
# 1. DICTIONNAIRE D'ENTITES  -> a completer/elaguer selon vos priorites
# ----------------------------------------------------------------------
ENTITES = {
    # requete Google News              : poids (score de pertinence)
    '"Attijariwafa bank"'              : 10,
    '"Attijariwafa"'                   : 8,
    '"التجاري وفا بنك"'                 : 10,
    '"Attijari bank" Tunisie'          : 9,
    '"Attijariwafa bank Europe"'       : 7,
    '"Wafa Assurance"'                 : 6,
    '"Wafasalaf"'                      : 5,
    '"Wafacash"'                       : 5,
    '"Attijari bank Egypt" OR "Attijariwafa Egypt"' : 6,
    '"CBAO" Attijariwafa'              : 6,
    '"Societe Ivoirienne de Banque" OR "SIB" Attijariwafa' : 5,
    '"Union Gabonaise de Banque" OR "UGB" Attijariwafa'    : 5,
    '"BIA Gabon"'                      : 4,
    '"Mohamed El Kettani"'             : 9,   # PDG - signal dirigeant
}

# Locales interrogees (un meme mot-cle donne des resultats differents par pays)
LOCALES = [
    ("fr", "MA", "MA:fr"),   # Maroc francophone
    ("fr", "TN", "TN:fr"),   # Tunisie
    ("fr", "FR", "FR:fr"),   # France / presse Afrique basee a Paris
    ("ar", "MA", "MA:ar"),   # Maroc arabophone
    ("en", "US", "US:en"),   # presse anglophone / agences
]

# ----------------------------------------------------------------------
# 2. FLUX RSS NATIFS  -> a completer. Testez chaque URL avant de l'ajouter.
#    (voir README : commande de test)
# ----------------------------------------------------------------------
FLUX_NATIFS = [
    # ("Nom affiche", "url du flux"),
    # ex : ("Medias24", "https://medias24.com/feed/"),
    # ex : ("Le Boursier", "https://www.leboursier.ma/feed"),
    # ex : ("Financial Afrik", "https://financialafrik.com/feed/"),
]

# ----------------------------------------------------------------------
# 3. ANTI-BRUIT
# ----------------------------------------------------------------------
BRUIT = [
    r"offre d.emploi", r"recrutement", r"recrute", r"stage rémunéré",
    r"horaires d.ouverture", r"code promo", r"jeu concours", r"tombola",
    r"agence la plus proche", r"guichet automatique",
    r"وظائف", r"توظيف",
]
BRUIT_RE = re.compile("|".join(BRUIT), re.IGNORECASE)

# Mots qui remontent le score : c'est la que se trouve l'info a valeur
SIGNAUX_FORTS = {
    r"résultat|bénéfice|PNB|RBE|coût du risque|dividende" : 5,
    r"AMMC|note d.information|émission obligataire|augmentation de capital|OPA|OPV" : 6,
    r"Fitch|Moody.s|S&P|notation|rating|outlook" : 6,
    r"acquisition|cession|prise de participation|filiale|rachat" : 5,
    r"nomination|conseil d.administration|directoire|démission" : 4,
    r"Bank Al-Maghrib|BCT|BCEAO|régulateur|sanction|amende" : 5,
    r"cyber|fraude|litige|procès|enquête" : 6,
}
SIGNAUX_RE = [(re.compile(p, re.IGNORECASE), w) for p, w in SIGNAUX_FORTS.items()]

# ----------------------------------------------------------------------
SEUIL_SCORE = int(os.environ.get("SEUIL_SCORE", "8"))
FENETRE_H   = int(os.environ.get("FENETRE_H", "48"))   # ignorer plus vieux que X h
SEEN_FILE   = "seen.json"
MAX_SEEN    = 4000
TG_TOKEN    = os.environ.get("TELEGRAM_TOKEN")
TG_CHAT     = os.environ.get("TELEGRAM_CHAT_ID")


def gnews_url(query, hl, gl, ceid):
    return (f"https://news.google.com/rss/search?q={quote_plus(query)}+when:2d"
            f"&hl={hl}&gl={gl}&ceid={ceid}")


def norm_titre(t):
    """Normalisation agressive pour deduplication inter-sites."""
    t = html.unescape(t or "").lower()
    t = re.sub(r"\s*[-|–—]\s*[^-|–—]{2,40}$", "", t)   # retire " - Nom du site"
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def cle(titre):
    return hashlib.sha1(norm_titre(titre).encode("utf-8")).hexdigest()[:16]


def score(titre, resume, poids_base):
    txt = f"{titre} {resume}"
    s = poids_base
    for rx, w in SIGNAUX_RE:
        if rx.search(txt):
            s += w
    return s


def charger_seen():
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def sauver_seen(seen):
    if len(seen) > MAX_SEEN:
        seen = dict(sorted(seen.items(), key=lambda kv: kv[1])[-MAX_SEEN:])
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False)


def envoyer(texte):
    if not TG_TOKEN or not TG_CHAT:
        print("[DRY-RUN]", texte[:200].replace("\n", " | "))
        return True
    data = json.dumps({
        "chat_id": TG_CHAT, "text": texte,
        "parse_mode": "HTML", "disable_web_page_preview": False,
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200
    except Exception as e:
        print("Erreur Telegram:", e, file=sys.stderr)
        return False


def collecter():
    items, limite = [], datetime.now(timezone.utc) - timedelta(hours=FENETRE_H)

    sources = []
    for q, poids in ENTITES.items():
        for hl, gl, ceid in LOCALES:
            sources.append((f"GNews {gl}", gnews_url(q, hl, gl, ceid), poids))
    for nom, url in FLUX_NATIFS:
        sources.append((nom, url, 6))

    for nom, url, poids in sources:
        try:
            d = feedparser.parse(url)
        except Exception as e:
            print(f"  ! echec {nom}: {e}", file=sys.stderr)
            continue
        for e in d.entries[:40]:
            titre = html.unescape(getattr(e, "title", "") or "")
            resume = re.sub(r"<[^>]+>", " ", getattr(e, "summary", "") or "")[:400]
            lien = getattr(e, "link", "")
            if not titre or not lien:
                continue

            # filtre pertinence applique a TOUTES les sources, y compris Google News
            if not re.search(r"attijari|التجاري وفا|وفا بنك|wafa", f"{titre} {resume}", re.I):
                continue

            if BRUIT_RE.search(f"{titre} {resume}"):
                continue

            pub = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
            if pub:
                dt = datetime.fromtimestamp(time.mktime(pub), tz=timezone.utc)
                if dt < limite:
                    continue
            else:
                dt = datetime.now(timezone.utc)

            items.append({
                "cle": cle(titre), "titre": titre.strip(), "lien": lien,
                "source": nom, "date": dt, "score": score(titre, resume, poids),
            })
        time.sleep(0.4)   # politesse
    return items


def main():
    seen = charger_seen()
    items = collecter()
    print(f"{len(items)} items bruts collectes")

    # deduplication : on garde la meilleure occurrence par cle
    uniques = {}
    for it in items:
        k = it["cle"]
        if k in seen:
            continue
        if k not in uniques or it["score"] > uniques[k]["score"]:
            uniques[k] = it

    retenus = [it for it in uniques.values() if it["score"] >= SEUIL_SCORE]
    retenus.sort(key=lambda x: (-x["score"], x["date"]))
    print(f"{len(uniques)} uniques nouveaux -> {len(retenus)} au-dessus du seuil {SEUIL_SCORE}")

    if not retenus:
        return

    envoyes = 0
    for it in retenus[:25]:
        etoiles = "🔴" if it["score"] >= 18 else ("🟠" if it["score"] >= 13 else "⚪️")
        msg = (f"{etoiles} <b>{html.escape(it['titre'])}</b>\n"
               f"<i>{html.escape(it['source'])} · {it['date'].strftime('%d/%m %H:%M')} "
               f"· score {it['score']}</i>\n{it['lien']}")
        if envoyer(msg):
            seen[it["cle"]] = int(time.time())
            envoyes += 1
        time.sleep(1.2)   # limite Telegram ~30 msg/s, on reste tres en dessous

    # on marque aussi comme vus les items sous le seuil, pour ne pas les rescorer
    for it in uniques.values():
        seen.setdefault(it["cle"], int(time.time()))

    sauver_seen(seen)
    print(f"{envoyes} messages envoyes")


if __name__ == "__main__":
    main()
