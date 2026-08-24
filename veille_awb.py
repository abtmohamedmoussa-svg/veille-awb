#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Veille -> Telegram (canal unique, articles tagues par sujet)

  AWB   : Attijariwafa bank et filiales
  TN    : secteur bancaire tunisien
  SOUV  : risque souverain, macro et politique monetaire (FR / EN / AR)
  TECH  : use cases technologiques internationaux dans la banque/finance

Articles non francophones : titre + resume traduits, lien vers version traduite.
Etat persistant : seen.json, recommit a chaque run.
"""

import os, json, time, hashlib, html, re, sys, base64
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
# ======================================================================
SUJETS = [
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
    {
        "tag": "🟩 SOUV",
        "locales": L_AR,
        "seuil": 16,
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
    {
        "tag": "🟪 TECH",
        "locales": L_TECH,
        "seuil": 15,
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
        # Flux natifs : liens editeur directs + vraies descriptions.
        # Le filtre use-case (motif_et) ne s'y applique pas : source deja curee.
        "flux": [
            ("Finextra", "https://www.finextra.com/rss/headlines.aspx", 9),
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

SRC_EXCLUES = re.compile(
    r"pr ?newswire|business ?wire|globe ?newswire|ein ?presswire|accesswire|prweb|"
    r"openpr|newsfile|issuewire|analytics ?insight|cryptopolitan|bitcoinist|"
    r"coinpedia|ambcrypto|benzinga|zacks|simply ?wall|investing\.com|marketbeat|"
    r"medium\.com|linkedin\.com|substack|blogspot", re.IGNORECASE)

SRC_QUALITE = re.compile(
    r"finextra|american banker|banking dive|the banker|financial times|reuters|"
    r"bloomberg|wall street journal|the economist|techcrunch|sifted|rest of world|"
    r"nikkei|mit technology review|ieee|bank for international|fintech futures|"
    r"the paypers|payments dive|central banking|risk\.net", re.IGNORECASE)

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
    r"tokeni[sz]|stablecoin|settlement|custody|distributed ledger|smart contract": 6,
    r"chief (?:ai|data|digital|technolog\w+|information) officer|\bcaio\b": 4,
    r"fund ?rais|valuation|\$\d+ ?(?:m|bn|billion|million)": 5,
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


# ----------------------------------------------------------------------
# TRADUCTION
# ----------------------------------------------------------------------
TRADUIRE = os.environ.get("TRADUIRE", "1") == "1"
_CACHE_TRAD = {}
_ECHECS_GTX = [0]


def _http_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _trad_gtx(texte, source):
    url = ("https://translate.googleapis.com/translate_a/single"
           f"?client=gtx&sl={source}&tl=fr&dt=t&q={quote_plus(texte)}")
    data = _http_json(url)
    return "".join(seg[0] for seg in data[0] if seg and seg[0])


def _trad_mymemory(texte, source):
    src = "en" if source in ("auto", "en") else source
    url = ("https://api.mymemory.translated.net/get"
           f"?q={quote_plus(texte)}&langpair={src}|fr")
    mail = os.environ.get("MYMEMORY_MAIL", "")
    if mail:
        url += f"&de={quote_plus(mail)}"
    data = _http_json(url)
    return (data.get("responseData") or {}).get("translatedText") or ""


def traduire(texte, source="auto"):
    """Traduit vers le francais : gtx, puis MyMemory, sinon texte original.
    Cap a 450 caracteres : l'API MyMemory limite q a 500 octets."""
    if not TRADUIRE or not texte:
        return texte
    texte = texte[:450]
    if texte in _CACHE_TRAD:
        return _CACHE_TRAD[texte]

    if _ECHECS_GTX[0] < 3:
        try:
            out = _trad_gtx(texte, source)
            if out:
                _CACHE_TRAD[texte] = out
                return out
        except Exception as ex:
            _ECHECS_GTX[0] += 1
            if _ECHECS_GTX[0] == 1:
                print(f"  ! gtx indisponible ({ex}), bascule MyMemory", file=sys.stderr)

    try:
        out = _trad_mymemory(texte, source)
        if out:
            _CACHE_TRAD[texte] = out
            return out
    except Exception as ex:
        print(f"  ! MyMemory indisponible ({ex})", file=sys.stderr)

    _CACHE_TRAD[texte] = texte
    return texte


# ----------------------------------------------------------------------
# RESOLUTION DES LIENS GOOGLE NEWS
# ----------------------------------------------------------------------
def _varint(b, i):
    val = shift = 0
    while i < len(b):
        octet = b[i]; i += 1
        val |= (octet & 0x7F) << shift
        if not octet & 0x80:
            return val, i
        shift += 7
    return None, i


RESOUDRE_HTTP = os.environ.get("RESOUDRE_HTTP", "0") == "1"
_CACHE_URL = {}
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")


def _decoder_b64(url_gnews):
    """Ancien format d'identifiant : l'URL est en clair dans le protobuf."""
    m = re.search(r"/(?:rss/)?articles/([A-Za-z0-9_\-]+)", url_gnews)
    if not m:
        return None
    ident = m.group(1)
    try:
        b = base64.urlsafe_b64decode(ident + "=" * (-len(ident) % 4))
    except Exception:
        return None
    i = 0
    while i < len(b):
        j = b.find(b"\x22", i)
        if j < 0:
            return None
        longueur, k = _varint(b, j + 1)
        if longueur is None or longueur <= 0 or k + longueur > len(b):
            i = j + 1
            continue
        val = b[k:k + longueur]
        if val[:4] == b"http":
            try:
                u = val.decode("utf-8")
            except Exception:
                i = j + 1
                continue
            if u.startswith("http"):
                return u
        i = j + 1
    return None


def _suivre_http(url):
    """Suit la redirection Google News et extrait l'URL de l'editeur."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=12) as r:
            final = r.geturl()
            corps = r.read(200000).decode("utf-8", "ignore")
    except Exception as ex:
        print(f"  ! resolution echouee: {ex}", file=sys.stderr)
        return None
    if "news.google.com" not in final:
        return final
    m = re.search(r'data-n-au="(https?://[^"]+)"', corps)
    if m:
        return html.unescape(m.group(1))
    m = re.search(r'<a[^>]+href="(https?://(?!\S*?google\.)[^"]+)"', corps)
    if m:
        return html.unescape(m.group(1))
    return None


def resoudre_lien(url_gnews):
    """URL reelle de l'editeur. None si irrecuperable."""
    if not url_gnews.startswith("http"):
        return None
    if "news.google.com" not in url_gnews:
        return url_gnews
    if url_gnews in _CACHE_URL:
        return _CACHE_URL[url_gnews]
    reel = _decoder_b64(url_gnews) or (_suivre_http(url_gnews) if RESOUDRE_HTTP else None)
    _CACHE_URL[url_gnews] = reel
    return reel


def lien_traduit(url, src="auto"):
    """Proxy translate.goog applique a une URL editeur. None si non resolue."""
    reel = resoudre_lien(url)
    if not reel or "news.google.com" in reel:
        return None
    m = re.match(r"^https?://([^/?#]+)([^#]*)$", reel)
    if not m:
        return None
    host, reste = m.group(1), m.group(2) or "/"
    if not reste.startswith("/"):
        reste = "/" + reste
    host_tr = host.replace("-", "--").replace(".", "-")
    sep = "&" if "?" in reste else "?"
    return (f"https://{host_tr}.translate.goog{reste}{sep}"
            f"_x_tr_sl={src}&_x_tr_tl=fr&_x_tr_hl=fr")


# ----------------------------------------------------------------------
def titre_propre(titre, media):
    """Retire le suffixe ' - Media' redondant avec la ligne source."""
    if media and titre.endswith(" - " + media):
        return titre[: -(len(media) + 3)].strip()
    return re.sub(r"\s+[-|–—]\s+[^-|–—]{2,40}$", "", titre).strip()


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
        "parse_mode": "HTML", "disable_web_page_preview": True,
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


def traiter_flux(url, sujet, motif, motif_et, poids, etiquette, limite, items,
                 langue="fr", strict=True):
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
        media = source_de(e, titre) or etiquette

        if SRC_EXCLUES.search(media):
            continue
        if PUB_RE.search(txt):
            continue
        if not motif.search(txt):
            continue
        if strict and motif_et and not motif_et.search(txt):
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
            "resume": resume,
            "tag": sujet["tag"], "source": media, "date": dt,
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
                                    nom, limite, items, "en", strict=False)
            time.sleep(0.35)

        langue = sujet["locales"][0][0] if sujet["locales"] else "rss"
        print(f"  {sujet['tag']} ({langue}) : {n_sujet} items retenus")
    return items


def main():
    if TRADUIRE:
        essai = traduire("The central bank rolled out a new payment system", "en")
        print(f"Autotest traduction : {essai[:70]}")

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
        vo = titre_propre(it["titre"], it["source"])
        meta = (f"{html.escape(it['source'])} · "
                f"{it['date'].strftime('%d/%m %H:%M')} · score {it['score']}")

        ligne_res = ""
        brut = (it.get("resume") or "").strip()
        if len(brut) > 60:
            court = brut[:400].rsplit(" ", 1)[0]
            if it.get("langue", "fr") != "fr":
                court = traduire(court, it["langue"])
            ligne_res = f"{html.escape(court)}\n"

        cible = resoudre_lien(it["lien"]) or it["lien"]
        liens = [f"<a href=\"{html.escape(cible, quote=True)}\">🔗 Source</a>"]

        if it.get("langue", "fr") != "fr":
            titre_aff = traduire(vo, it["langue"])
            ligne_vo = f"<i>{html.escape(vo)}</i>\n" if titre_aff != vo else ""
            lfr = lien_traduit(it["lien"], it["langue"])
            if lfr:
                liens.insert(0, f"<a href=\"{html.escape(lfr, quote=True)}\">🇫🇷 Lire en français</a>")
        else:
            titre_aff, ligne_vo = vo, ""

        msg = (f"{it['tag']} {alerte} <b>{html.escape(titre_aff)}</b>\n"
               f"{ligne_vo}"
               f"{ligne_res}"
               f"<i>{meta}</i>\n"
               + "  ·  ".join(liens))

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
