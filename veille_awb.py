#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Veille -> Telegram (canal unique, articles tagues par sujet)

  AWB   : Attijariwafa bank et filiales
  TN    : secteur bancaire tunisien
  SOUV  : risque souverain, macro et politique monetaire (FR / EN / AR)
  TECH  : use cases technologiques internationaux dans la banque/finance

Les articles non francophones sont traduits (titre + lien proxy translate.goog).
Etat persistant : seen.json, recommit a chaque run.
"""

import os, json, time, hashlib, html, re, sys
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
import urllib.request
import feedparser

# ======================================================================
# LOCALES
# ======================================================================
L_MA    = [("fr", "MA", "MA:fr"), ("ar", "MA", "MA:ar"), ("fr", "FR", "FR:fr"),
           ("fr", "TN", "TN:fr"), ("en", "US", "US:en")]
L_TN    = [("fr", "TN", "TN:fr"), ("ar", "TN", "TN:ar"), ("fr", "FR", "FR:fr")]
L_SOUV  = [("fr", "FR", "FR:fr"), ("en", "US", "US:en")]
L_AR    = [("ar", "EG", "EG:ar"), ("ar", "TN", "TN:ar")]
L_TECH  = [("en", "US", "US:en"), ("en", "GB", "GB:en"), ("fr", "FR", "FR:fr")]

# ======================================================================
# SUJETS
#   motif      : condition necessaire (OU interne)
#   motif_et   : seconde condition necessaire, optionnelle
#   seuil      : score minimal pour declencher un envoi
#   flux       : flux RSS natifs a ajouter au sujet (optionnel)
# ======================================================================
SUJETS = [
    # ------------------------------------------------------------------
    {
        "tag": "🟦 AWB",
        "locales": L_MA,
        "motif": r"attijari|التجاري وفا|وفا بنك|wafasalaf|wafacash|wafa assurance|el kettani",
        "requetes": {
            '"Attijariwafa bank"': 10,
            '"Attijariwafa"': 8,
            '"التجاري وفا بنك"': 10,
            '"Attijari bank" Tunisie': 9,
            '"Attijariwafa bank Europe"': 7,
            '"Wafa Assurance"': 6,
            '"Wafasalaf"': 5,
            '"Wafacash"': 5,
            '"CBAO" Attijariwafa': 6,
            '"Mohamed El Kettani"': 9,
        },
        "flux": [],
    },
    # ------------------------------------------------------------------
    {
        "tag": "🟨 TN",
        "locales": L_TN,
        "motif": (r"\bbiat\b|amen bank|banque de tunisie|\bbna\b|banque nationale agricole|"
                  r"\bstb\b|societe tunisienne de banque|\bbh bank\b|banque de l.habitat|"
                  r"\buib\b|\bubci\b|arab tunisian|\batb\b|zitouna|al ?baraka|wifak|qnb|"
                  r"banque centrale de tunisie|\bbct\b|secteur bancaire tunisien|aptbef|بنك|البنك"),
        "requetes": {
            '"BIAT" Tunisie': 8,
            '"Amen Bank"': 8,
            '"Banque de Tunisie"': 8,
            '"Banque Nationale Agricole" OR "BNA Bank" Tunisie': 8,
            '"Societe Tunisienne de Banque" OR "STB Bank"': 8,
            '"BH Bank" OR "Banque de l\'Habitat" Tunisie': 8,
            '"UIB" Tunisie': 7,
            '"UBCI" Tunisie': 7,
            '"Arab Tunisian Bank"': 7,
            '"Banque Zitouna" OR "Zitouna Bank"': 7,
            '"Al Baraka Bank" Tunisie': 6,
            '"Wifak Bank"': 6,
            '"QNB Tunisie"': 6,
            '"Banque Centrale de Tunisie"': 9,
            '"secteur bancaire tunisien"': 8,
            '"البنك المركزي التونسي"': 9,
        },
        "flux": [],
    },
    # ------------------------------------------------------------------
    # SOUVERAIN - volet latin
    # ------------------------------------------------------------------
    {
        "tag": "🟩 SOUV",
        "locales": L_SOUV,
        "seuil": 13,
        "motif": (r"tunisi|maroc|moroc|égypt|egypt|algéri|algeri|liby|mauritani|"
                  r"côte d.ivoire|ivoir|cameroun|cameroon|sénégal|senegal|gabon|"
                  r"turqu|turkey|türkiye"),
        "motif_et": (r"fitch|moody|s&p|standard & poor|notation|rating|outlook|"
                     r"\bfmi\b|\bimf\b|eurobond|sukuk|obligation souveraine|sovereign|"
                     r"spread|\bcds\b|taux directeur|policy rate|politique monétaire|"
                     r"monetary policy|banque centrale|central bank|inflation|"
                     r"déficit budgétaire|budget deficit|dette publique|public debt|"
                     r"défaut|default|restructuration|restructuring|"
                     r"balance des paiements|réserves de change|foreign reserves|dévaluation"),
        "requetes": {
            'Tunisie notation souveraine OR FMI OR eurobond': 9,
            'Maroc notation souveraine OR "taux directeur" OR eurobond': 8,
            'Egypte notation souveraine OR FMI OR eurobond': 8,
            'Algérie "dette publique" OR "déficit budgétaire" OR inflation': 7,
            'Libye "banque centrale" OR "réserves de change"': 6,
            'Mauritanie FMI OR "dette publique" OR notation': 6,
            '"Côte d\'Ivoire" eurobond OR notation OR FMI': 8,
            'Cameroun FMI OR "dette publique" OR notation': 7,
            'Sénégal eurobond OR FMI OR notation OR "dette publique"': 8,
            'Gabon eurobond OR notation OR "dette publique"': 7,
            'Turquie "taux directeur" OR "politique monétaire" OR inflation': 8,
            'Egypt sovereign rating OR IMF programme': 7,
            'Turkey central bank policy rate': 7,
            'Senegal OR Gabon OR Cameroon sovereign rating': 7,
        },
        "flux": [],
    },
    # ------------------------------------------------------------------
    # SOUVERAIN - volet arabophone
    # ------------------------------------------------------------------
    {
        "tag": "🟩 SOUV",
        "locales": L_AR,
        "seuil": 13,
        "motif": (r"تونس|مغرب|\bمصر\b|مصري|جزائر|ليبي|موريتاني|"
                  r"ساحل العاج|كوت ديفوار|كاميرون|سنغال|غابون|تركي"),
        "motif_et": (r"التصنيف السيادي|التصنيف الائتماني|صندوق النقد|"
                     r"سندات دولية|سندات سيادية|صكوك|"
                     r"السياسة النقدية|سعر الفائدة|نسبة الفائدة|البنك المركزي|"
                     r"التضخم|الدين العام|عجز الميزانية|احتياطي النقد|"
                     r"العملة الصعبة|تخفيض قيمة|فيتش|موديز"),
        "requetes": {
            'تونس "التصنيف السيادي" OR "صندوق النقد الدولي"': 9,
            'المغرب "التصنيف الائتماني" OR "السياسة النقدية"': 8,
            'مصر "صندوق النقد الدولي" OR "سندات دولية"': 8,
            'الجزائر "الدين العام" OR "التضخم"': 7,
            'ليبيا "البنك المركزي" OR "احتياطي النقد"': 6,
            'موريتانيا "صندوق النقد الدولي" OR "الدين العام"': 6,
            'تركيا "سعر الفائدة" OR "السياسة النقدية"': 8,
            'السنغال OR الكاميرون OR الغابون "صندوق النقد الدولي"': 6,
        },
        "flux": [],
    },
    # ------------------------------------------------------------------
    # TECH - use cases internationaux
    # ------------------------------------------------------------------
    {
        "tag": "🟪 TECH",
        "locales": L_TECH,
        "seuil": 12,
        "motif": (r"bank|banking|finance|financial|payment|paiement|fintech|"
                  r"insurance|assurance|lending|credit|treasury|capital market|"
                  r"banque|crédit|marché|deposit|dépôt|transaction|wallet|"
                  r"settlement|clearing|custody|tokeni[sz]|stablecoin|\bcbdc\b|\bmnbc\b|"
                  r"blockchain|ledger|core banking|\bkyc\b|\baml\b|fraud|fraude|"
                  r"trading|exchange|remittance|virement|compensation|"
                  r"\bpix\b|\bupi\b|swift|iso ?20022|neobank|néobanque|"
                  r"jpmorgan|goldman|citigroup|\bhsbc\b|\bbnp\b|santander|\bdbs\b|"
                  r"\becb\b|\bbce\b|\bfed\b|\bboe\b|\bbis\b|\bmas\b|\bfca\b|\bocc\b"),
        "motif_et": (r"deploy(?:s|ed|ment)?|roll(?:s|ed)? out|go(?:es)? live|went live|"
                     r"in production|pilot|proof of concept|\bpoc\b|case study|"
                     r"processed \d|handles \d|migrat(?:e|es|ed|ion)|implementation|"
                     r"results show|reduced .{0,25} by \d|cut .{0,25} by \d|\d+ ?% |"
                     r"lessons|post-?mortem|benchmark|outage|failure|abandon(?:s|ed)?|"
                     r"scrap(?:s|ped)?|mandate|regulat(?:ion|or|ory)|licen[cs]e|"
                     r"approv(?:e|es|ed|al)|greenlight|authoris|authoriz|adopts|"
                     r"consultation|directive|ban(?:s|ned)|fine[sd]?|"
                     r"acquir(?:e|es)|acquisition|merger|shut(?:s)? down|discontinue|"
                     r"déploie|mise en production|pilote|retour d.expérience|"
                     r"agrément|autorisation|sanction"),
        "requetes": {
            'bank deploys AI production': 8,
            'bank core banking migration': 8,
            'tokenized deposits bank live': 9,
            'CBDC pilot central bank': 9,
            'instant payments rollout': 8,
            'open banking regulation': 8,
            'stablecoin bank licence': 9,
            'agentic AI bank pilot': 8,
            'bank AI project failure OR abandoned': 9,
            'ISO 20022 migration bank': 7,
            'fraud detection AI bank results': 8,
            'quantum computing bank pilot': 7,
            'digital identity bank rollout': 7,
            'embedded finance platform bank': 7,
            'banque déploiement intelligence artificielle': 7,
            'banque migration système information': 7,
        },
        # Flux natifs a haute valeur : testez chaque URL avant de l'activer
        #   curl -s "https://www.finextra.com/rss/headlines.aspx" | head -20
        "flux": [
            # ("Finextra", "https://www.finextra.com/rss/headlines.aspx", 9),
            # ("The Paypers", "https://thepaypers.com/rss", 8),
            # ("Banking Dive", "https://www.bankingdive.com/feeds/news/", 8),
        ],
    },
]

# ======================================================================
# FILTRES TRANSVERSES
# ======================================================================
BRUIT = [
    r"offre d.emploi", r"recrutement", r"recrute", r"stage rémunéré",
    r"horaires d.ouverture", r"code promo", r"jeu concours", r"tombola",
    r"agence la plus proche", r"guichet automatique",
    r"coupe du monde", r"championnat", r"demi-finale",
    r"cours du bitcoin", r"prix du bitcoin", r"bitcoin atteint",
    r"meilleures cryptos", r"comment investir", r"guide d.achat", r"parrainage",
    r"وظائف", r"توظيف", r"كأس العالم", r"مباراة",
]
BRUIT_RE = re.compile("|".join(BRUIT), re.IGNORECASE)

# Fils de communiques de presse et fermes de contenu : rejet sur le nom du media
SRC_EXCLUES = re.compile(
    r"pr ?newswire|business ?wire|globe ?newswire|ein ?presswire|accesswire|prweb|"
    r"openpr|newsfile|issuewire|analytics ?insight|cryptopolitan|bitcoinist|"
    r"coinpedia|ambcrypto|benzinga|zacks|simply ?wall|investing\.com|marketbeat|"
    r"medium\.com|linkedin\.com|substack|blogspot", re.IGNORECASE)

# Sources sectorielles serieuses : bonus de score
SRC_QUALITE = re.compile(
    r"finextra|american banker|banking dive|the banker|financial times|reuters|"
    r"bloomberg|wall street journal|the economist|techcrunch|sifted|rest of world|"
    r"nikkei|mit technology review|ieee|bank for international|fintech futures|"
    r"the paypers|payments dive|central banking|risk\.net", re.IGNORECASE)

# Marqueurs publicitaires / editoriaux sans valeur ajoutee
PUB_RE = re.compile(
    r"\bproud to\b|is pleased to|announces? (?:a )?(?:strategic )?partnership|"
    r"named a leader|magic quadrant|forrester wave|wins? award|award-winning|"
    r"top \d+|best \d+|\d+ ways|\d+ things|\d+ trends|what is |how to |"
    r"the future of|thought leader|sponsored|webinar|white ?paper|ebook|"
    r"register now|join us|unveils new|expands partnership|"
    r"predictions for \d{4}|guide to|publi-?rédactionnel", re.IGNORECASE)

# ======================================================================
# SCORING
# ======================================================================
SIGNAUX_FORTS = {
    r"résultat|bénéfice|PNB|RBE|coût du risque|dividende": 5,
    r"AMMC|CMF|note d.information|émission obligataire|augmentation de capital|OPA|OPV": 6,
    r"Fitch|Moody.s|S&P|notation|rating|outlook|فيتش|موديز|التصنيف": 6,
    r"acquisition|cession|prise de participation|filiale|rachat": 5,
    r"nomination|conseil d.administration|directoire|démission": 4,
    r"Bank Al-Maghrib|BCT|BCEAO|régulateur|sanction|amende": 5,
    r"cyber|fraude|litige|procès|enquête": 6,
    r"\bFMI\b|\bIMF\b|صندوق النقد": 6,
    r"eurobond|sukuk|صكوك|سندات دولية": 6,
    r"taux directeur|policy rate|نسبة الفائدة|سعر الفائدة": 6,
    r"défaut|default|restructuration|restructuring|rééchelonnement": 7,
    r"spread|\bCDS\b|dévaluation|تخفيض قيمة": 6,
    r"levée de fonds|funding round|series [ABCD]\b|licorne|unicorn": 5,
    r"agrément|licen[cs]e|sandbox|cadre réglementaire|regulatory framework": 6,
    r"open banking|\bMNBC\b|\bCBDC\b|paiement instantané|instant payment": 6,
    r"failure|abandoned|scrapped|outage|post-?mortem|lessons": 6,
    r"went live|in production|rolled out|case study": 5,
}
SIGNAUX_RE = [(re.compile(p, re.IGNORECASE), w) for p, w in SIGNAUX_FORTS.items()]

# ======================================================================
SEUIL_SCORE = int(os.environ.get("SEUIL_SCORE", "8"))
FENETRE_H   = int(os.environ.get("FENETRE_H", "48"))
SEEN_FILE   = "seen.json"
MAX_SEEN    = 8000
MAX_ENVOIS  = int(os.environ.get("MAX_ENVOIS", "30"))
TG_TOKEN    = os.environ.get("TELEGRAM_TOKEN")
TG_CHAT     = os.environ.get("TELEGRAM_CHAT_ID")


def gnews_url(query, hl, gl, ceid):
    return (f"https://news.google.com/rss/search?q={quote_plus(query)}+when:2d"
            f"&hl={hl}&gl={gl}&ceid={ceid}")


def source_de(entry, titre):
    """Nom du media : champ <source> du flux, sinon suffixe ' - Media' du titre."""
    s = ""
    try:
        s = getattr(entry.source, "title", "") or ""
    except Exception:
        pass
    if not s and " - " in titre:
        s = titre.rsplit(" - ", 1)[-1]
    return s.strip()


TRADUIRE = os.environ.get("TRADUIRE", "1") == "1"
_CACHE_TRAD = {}


def traduire(texte, source="auto"):
    """Traduit vers le francais. En cas d'echec, renvoie le texte original."""
    if not TRADUIRE or not texte:
        return texte
    if texte in _CACHE_TRAD:
        return _CACHE_TRAD[texte]
    url = ("https://translate.googleapis.com/translate_a/single"
           f"?client=gtx&sl={source}&tl=fr&dt=t&q={quote_plus(texte[:900])}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        out = "".join(seg[0] for seg in data[0] if seg and seg[0])
        _CACHE_TRAD[texte] = out or texte
        return _CACHE_TRAD[texte]
    except Exception as ex:
        print(f"  ! traduction echouee: {ex}", file=sys.stderr)
        _CACHE_TRAD[texte] = texte
        return texte


def lien_traduit(url, src="auto"):
    """Passe l'URL par le proxy translate.goog."""
    m = re.match(r"^https?://([^/?#]+)([^#]*)$", url)
    if not m:
        return url
    host, reste = m.group(1), m.group(2) or "/"
    if not reste.startswith("/"):
        reste = "/" + reste
    host_tr = host.replace("-", "--").replace(".", "-")
    sep = "&" if "?" in reste else "?"
    return (f"https://{host_tr}.translate.goog{reste}{sep}"
            f"_x_tr_sl={src}&_x_tr_tl=fr&_x_tr_hl=fr")


def norm_titre(t):
    t = html.unescape(t or "").lower()
    t = re.sub(r"\s*[-|–—]\s*[^-|–—]{2,40}$", "", t)
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip()


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
        print("[DRY-RUN]", texte[:180].replace("\n", " | "))
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


def traiter_flux(url, sujet, motif, motif_et, poids, etiquette, limite, items, langue="fr"):
    """Parse un flux et empile les entrees retenues dans items."""
    try:
        d = feedparser.parse(url)
    except Exception as ex:
        print(f"  ! echec {etiquette}: {ex}", file=sys.stderr)
        return 0
    n = 0
    for e in d.entries[:40]:
        titre = html.unescape(getattr(e, "title", "") or "")
        resume = re.sub(r"<[^>]+>", " ", getattr(e, "summary", "") or "")[:400]
        lien = getattr(e, "link", "")
        if not titre or not lien:
            continue

        txt = f"{titre} {resume}"
        media = source_de(e, titre)

        if SRC_EXCLUES.search(media):
            continue
        if PUB_RE.search(txt):
            continue
        if not motif.search(txt):
            continue
        if motif_et and not motif_et.search(txt):
            continue
        if BRUIT_RE.search(txt):
            continue

        pub = (getattr(e, "published_parsed", None)
               or getattr(e, "updated_parsed", None))
        if pub:
            dt = datetime.fromtimestamp(time.mktime(pub), tz=timezone.utc)
            if dt < limite:
                continue
        else:
            dt = datetime.now(timezone.utc)

        bonus = 4 if SRC_QUALITE.search(media) else 0
        items.append({
            "cle": cle(titre), "titre": titre.strip(), "lien": lien,
            "tag": sujet["tag"], "source": media or etiquette, "date": dt,
            "score": score(titre, resume, poids) + bonus,
            "seuil": sujet.get("seuil", SEUIL_SCORE),
            "langue": langue,
        })
        n += 1
    return n


def collecter():
    items = []
    limite = datetime.now(timezone.utc) - timedelta(hours=FENETRE_H)

    for sujet in SUJETS:
        motif = re.compile(sujet["motif"], re.IGNORECASE)
        motif_et = (re.compile(sujet["motif_et"], re.IGNORECASE)
                    if sujet.get("motif_et") else None)
        n_sujet = 0

        for q, poids in sujet["requetes"].items():
            for hl, gl, ceid in sujet["locales"]:
                n_sujet += traiter_flux(gnews_url(q, hl, gl, ceid), sujet,
                                        motif, motif_et, poids,
                                        f"GNews {gl}", limite, items, hl)
                time.sleep(0.35)

        for entree in sujet.get("flux", []):
            nom, url = entree[0], entree[1]
            poids = entree[2] if len(entree) > 2 else 7
            n_sujet += traiter_flux(url, sujet, motif, motif_et, poids,
                                    nom, limite, items, "en")
            time.sleep(0.35)

        langue = sujet["locales"][0][0] if sujet["locales"] else "rss"
        print(f"  {sujet['tag']} ({langue}) : {n_sujet} items retenus")
    return items


def main():
    seen = charger_seen()
    items = collecter()
    print(f"{len(items)} items pertinents collectes")

    uniques = {}
    for it in items:
        k = it["cle"]
        if k in seen:
            continue
        if k not in uniques or it["score"] > uniques[k]["score"]:
            uniques[k] = it

    retenus = [it for it in uniques.values() if it["score"] >= it["seuil"]]
    retenus.sort(key=lambda x: (x["tag"], -x["score"], x["date"]))
    print(f"{len(uniques)} uniques nouveaux -> {len(retenus)} au-dessus du seuil")

    if not retenus:
        return

    envoyes = 0
    for it in retenus[:MAX_ENVOIS]:
        alerte = "🔴" if it["score"] >= 20 else ("🟠" if it["score"] >= 15 else "⚪️")
        vo = it["titre"]
        meta = (f"{html.escape(it['source'])} · "
                f"{it['date'].strftime('%d/%m %H:%M')} · score {it['score']}")
        if it.get("langue", "fr") != "fr":
            titre_fr = traduire(vo, it["langue"])
            ligne_vo = f"<i>{html.escape(vo)}</i>\n" if titre_fr != vo else ""
            msg = (f"{it['tag']} {alerte} <b>{html.escape(titre_fr)}</b>\n"
                   f"{ligne_vo}"
                   f"<i>{meta}</i>\n"
                   f"🇫🇷 {lien_traduit(it['lien'], it['langue'])}\n"
                   f"🔗 {it['lien']}")
        else:
            msg = (f"{it['tag']} {alerte} <b>{html.escape(vo)}</b>\n"
                   f"<i>{meta}</i>\n{it['lien']}")
        if envoyer(msg):
            seen[it["cle"]] = int(time.time())
            envoyes += 1
        time.sleep(1.2)

    for it in uniques.values():
        seen.setdefault(it["cle"], int(time.time()))

    sauver_seen(seen)
    print(f"{envoyes} messages envoyes")


if __name__ == "__main__":
    main()
