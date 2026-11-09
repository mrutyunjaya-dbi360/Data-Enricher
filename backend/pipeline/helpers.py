"""Ported helpers from combined_pipeline.py — business rules preserved."""
import re
import html
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from pipeline.pricing import PRICING
from pipeline.exceptions import CreditExpired

logger = logging.getLogger(__name__)

FREE_EMAIL_DOMAINS = {
    'gmail.com','googlemail.com','yahoo.com','yahoo.co.in','yahoo.co.uk','ymail.com',
    'hotmail.com','outlook.com','live.com','msn.com','rediffmail.com','icloud.com',
    'me.com','aol.com','protonmail.com','proton.me','zoho.com','zohomail.com',
    'mail.com','gmx.com','gmx.de','yandex.com','yandex.ru','qq.com','163.com',
    '126.com','sina.com','naver.com','web.de','inbox.com',
}

BLACKLISTED_DOMAINS = {
    'linkedin.com','facebook.com','twitter.com','instagram.com','youtube.com',
    'tiktok.com','pinterest.com','snapchat.com','amazon.com','ebay.com',
    'alibaba.com','aliexpress.com','indiamart.com','tradeindia.com',
    'exportersindia.com','volza.com','rocketreach.co','zoominfo.com',
    'dnb.com','bloomberg.com','crunchbase.com','manta.com','kompass.com',
    'thomasnet.com','yellowpages.com','whitepages.com','yelp.com',
    'justdial.com','glassdoor.com','indeed.com','wikipedia.org',
    'importgenius.com','pitchbook.com','google.com','bing.com','yahoo.com',
    'apollo.io','hunter.io','lusha.com','seamless.ai',
    'made-in-china.com','goldsupplier.com','tradekorea.com',
    'opencorporates.com','panjiva.com','lookchem.com','amawebs.com',
    'weebly.com','ueniweb.com','godaddy.com','wixsite.com',
    'myshopify.com','bit.ly','breezy.hr',
}

SOURCE_COUNTRY_HINTS = {
    "australia": "Australia", "aus": "Australia", " au ": "Australia",
    "uk": "UK", "united kingdom": "UK", "india": "India",
    "usa": "USA", "united states": "USA", "canada": "Canada",
    "germany": "Germany", "france": "France", "uae": "UAE",
}

COMPANY_TYPES = [
    "Manufacturer", "Exporter", "Importer", "Distributor", "Retailer",
    "Importer, Exporter", "Wholesaler", "Supplier", "Exporter, Importer",
    "Buyer", "Seller", "Trader", "Non-Profit Organization", "Service Provider",
]
EMPLOYEE_COUNTS = ["10", "50", "100", "200", "300", "500", "1000", "5000", "10000"]

_NULL_TEXTS = {"", "nan", "none", "null", "n/a", "na", "not available",
               "not found", "unknown", "undefined", "-", "--"}

FATAL_API_ERRORS = [
    "quota exceeded", "insufficient_quota", "exceeded your current quota",
    "billing", "invalid api key", "incorrect api key", "unauthorized", "402", "401",
]


def is_fatal_api_error(e: Exception) -> bool:
    msg = str(e).lower()
    return any(p in msg for p in FATAL_API_ERRORS)


def normalize_domain(url: str) -> Optional[str]:
    try:
        if not url or not isinstance(url, str):
            return None
        url = url.strip()
        if not url:
            return None
        url = url.encode('ascii', 'ignore').decode('ascii')
        if not url:
            return None
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        parsed = urlparse(url)
        netloc = parsed.netloc
        if not netloc:
            return None
        return f"{parsed.scheme}://{netloc}"
    except Exception:
        return None


def is_blacklisted(url: str) -> bool:
    return any(d in url.lower() for d in BLACKLISTED_DOMAINS)


def get_country_hint(source: str) -> str:
    if not source:
        return ""
    src_lower = source.lower()
    for key, country in SOURCE_COUNTRY_HINTS.items():
        if key in src_lower:
            return country
    return ""


def get_field(doc: dict, path: str):
    cur = doc
    for p in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
    return cur


def clean_value(val) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and val != val:
        return ""
    if isinstance(val, (list, tuple, set)):
        return ", ".join(str(v).strip() for v in val if v is not None and str(v).strip())
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none", "null", "n/a", "na", "-") else s


def clean_text(value, max_chars: int = 2500):
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        cleaned = []
        for item in value:
            item = clean_text(item, max_chars=max_chars)
            if item and item not in cleaned:
                cleaned.append(item)
        return cleaned or None
    if isinstance(value, dict):
        return {str(k): clean_text(v, max_chars=max_chars) for k, v in value.items()}
    text_value = html.unescape(str(value))
    text_value = BeautifulSoup(text_value, "html.parser").get_text(" ", strip=True)
    text_value = text_value.replace("\u00a0", " ").replace("\xa0", " ")
    text_value = re.sub(r"[\u200b-\u200f\ufeff]", "", text_value)
    text_value = re.sub(r"[ \t\r\n]+", " ", text_value).strip()
    if text_value.lower() in _NULL_TEXTS:
        return None
    return text_value[:max_chars].rstrip()


def clean_url(value):
    value = clean_text(value, max_chars=2000)
    if not value:
        return None
    if not re.match(r"^https?://", value, re.I):
        if re.match(r"^[\w.-]+\.[a-z]{2,}([/:?#]|$)", value, re.I):
            value = "https://" + value
        else:
            return value
    try:
        parsed = urlparse(value)
        if not parsed.netloc:
            return None
        return parsed.geturl().rstrip("/")
    except Exception:
        return None


def clean_company_record(record: dict) -> dict:
    cleaned = {}
    url_fields = {"Website", "Company Linkedin Url", "Facebook Url",
                  "Twitter Url", "Logo Url", "company_url", "company_domain"}
    list_fields = {"Keywords"}
    for key, value in record.items():
        if key in list_fields:
            cleaned[key] = clean_text(value)
        elif key in url_fields:
            cleaned[key] = clean_url(value)
        elif isinstance(value, str):
            cleaned[key] = clean_text(value, 2500 if "Description" in key else 1000)
        elif isinstance(value, list):
            cleaned[key] = clean_text(value)
        elif isinstance(value, dict):
            cleaned[key] = clean_company_record(value)
        else:
            cleaned[key] = value
    return cleaned


def extract_context(doc: dict, field_map: dict) -> Dict[str, str]:
    ctx = {}
    for key, fields in field_map.items():
        for f in fields:
            v = clean_value(get_field(doc, f))
            if v:
                ctx[key] = v[:300]
                break
    return ctx


def context_text(ctx: Dict[str, str]) -> str:
    return "\n".join(f"- {k.replace('_', ' ').title()}: {v}" for k, v in ctx.items())


def email_domains(email_str: str) -> List[str]:
    out = []
    for d in re.findall(r'[\w.+-]+@([\w-]+(?:\.[\w-]+)+)', email_str or ""):
        d = d.lower().strip(".")
        if d.startswith("www."):
            d = d[4:]
        if d in FREE_EMAIL_DOMAINS or is_blacklisted(d) or d in out:
            continue
        out.append(d)
    return out


def build_search_queries(name: str, ctx: Dict[str, str], country: str) -> List[str]:
    loc = " ".join(x for x in [ctx.get("city", ""), country] if x)
    extra = ""
    if not loc:
        extra = " ".join((ctx.get("industry") or ctx.get("product") or "").split()[:4])
    q1 = " ".join(f"{name} {loc} {extra} official website".split())
    q2 = " ".join(f"{name} {country} official website".split())
    queries = [q1]
    if q2 != q1:
        queries.append(q2)
    return queries


def signal_match(name: str, text: str, ctx: Dict[str, str]) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    if name.lower() in t:
        return "name"
    for e in re.findall(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+', ctx.get("email", "")):
        if e.lower() in t:
            return "email"
    phone_digits = re.sub(r'\D', '', ctx.get("phone", ""))
    if len(phone_digits) >= 8:
        tail = phone_digits[-8:]
        for chunk in re.findall(r'[\d\s\-\(\)\+\.]{8,}', text):
            if tail in re.sub(r'\D', '', chunk):
                return "phone"
    return None


def extract_domain_parts(url) -> Tuple[str, str]:
    if not url or isinstance(url, float):
        return "", ""
    url = str(url).strip()
    if not url or url.lower() == 'nan':
        return "", ""
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        parsed = urlparse(url)
        domain = parsed.netloc or url.replace('http://', '').replace('https://', '').split('/')[0]
        if domain.startswith('www.'):
            domain = domain[4:]
        if ':' in domain:
            domain = domain.split(':')[0]
        full = domain.lower().strip()
        m = re.search(r'\.(com|co|org|net|edu|gov)\.[a-z]{2}$', full)
        base = re.sub(r'\.[a-z]{2}$', '', full) if m else full
        return full, base
    except Exception:
        return "", ""


def llm_call(client, model, messages, *, emitter, doc_id, step, action, **kw):
    t0 = time.time()
    try:
        res = client.chat.completions.create(model=model, messages=messages, **kw)
        u = getattr(res, "usage", None)
        tin = getattr(u, "prompt_tokens", 0) or 0
        tout = getattr(u, "completion_tokens", 0) or 0
        prices = PRICING.get(model, PRICING.get("gpt-4o-mini", {"in": 0, "out": 0}))
        cost = prices["in"] * tin + prices["out"] * tout
        emitter.emit(
            doc_id=doc_id, step=step, action=action, success=True,
            model=model, tokens_in=tin, tokens_out=tout, cost_usd=cost,
            latency_ms=int((time.time() - t0) * 1000),
        )
        return res
    except Exception as e:
        if is_fatal_api_error(e):
            emitter.emit(doc_id=doc_id, step=step, action=action, success=False,
                         error_type="credit", latency_ms=int((time.time() - t0) * 1000))
            raise CreditExpired(f"openai:{e}")
        emitter.emit(doc_id=doc_id, step=step, action=action, success=False,
                     error_type=type(e).__name__, latency_ms=int((time.time() - t0) * 1000))
        raise


def serper_call(api_key, query, *, emitter, doc_id, step, cancel=None):
    import requests
    if cancel and cancel.is_set():
        raise RuntimeError("cancelled")
    t0 = time.time()
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            json={"q": query},
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=15,
        )
        if r.status_code in (402, 429):
            emitter.emit(doc_id=doc_id, step=step, action="serper", success=False,
                         error_type="credit", serper_queries=1,
                         latency_ms=int((time.time() - t0) * 1000))
            raise CreditExpired("serper credit/rate limit")
        if r.status_code != 200:
            raise RuntimeError(f"Serper status {r.status_code}")
        emitter.emit(doc_id=doc_id, step=step, action="serper", success=True,
                     serper_queries=1, cost_usd=PRICING["serper"],
                     latency_ms=int((time.time() - t0) * 1000))
        return r.json()
    except CreditExpired:
        raise
    except Exception as e:
        emitter.emit(doc_id=doc_id, step=step, action="serper", success=False,
                     error_type=type(e).__name__, serper_queries=1,
                     latency_ms=int((time.time() - t0) * 1000))
        return None
