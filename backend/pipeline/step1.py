"""Step 1 — Domain Finder (ported, context-aware)."""
import logging
import re
import requests
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from pipeline.helpers import (
    clean_value, extract_context, normalize_domain, is_blacklisted,
    email_domains, build_search_queries, signal_match, get_country_hint,
    context_text, llm_call, serper_call,
)
from pipeline.exceptions import CreditExpired

logger = logging.getLogger(__name__)
_http_headers = {"User-Agent": "Mozilla/5.0"}


def _get_website_text(domain: str) -> str:
    text = ""
    for path in ["", "/about", "/about-us", "/contact", "/contact-us"]:
        try:
            r = requests.get(domain + path, headers=_http_headers, timeout=(5, 10))
            if r.status_code == 200 and len(r.content) <= 5_000_000:
                from bs4 import BeautifulSoup
                text += BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)[:3000]
        except Exception:
            pass
    return text[:10000]


def _ai_select(client, company, results_text, country_hint, ctx, emitter, doc_id):
    country_line = (
        f"The company is likely based in {country_hint}. Prefer {country_hint} domains.\n"
        if country_hint else ""
    )
    details = context_text(ctx)
    details_block = f"Known details about the company:\n{details}\n" if details else ""
    prompt = (
        f"Company: {company}\n{details_block}{country_line}"
        f"Search Results (title | link | snippet):\n{results_text}\n\n"
        "Pick the official website of THIS company. Return ONLY the domain or None."
    )
    res = llm_call(
        client, "gpt-4o-mini", [{"role": "user", "content": prompt}],
        emitter=emitter, doc_id=doc_id, step="step1", action="llm_select", temperature=0,
    )
    return res.choices[0].message.content.strip()


def _ai_verify(client, company, text, ctx, emitter, doc_id):
    details = context_text(ctx)
    details_block = f"Known details about the company:\n{details}\n\n" if details else ""
    prompt = (
        f"Company: {company}\n\n{details_block}"
        f"Website Content:\n{text}\n\n"
        "Is this the official website of this specific company? Return ONLY YES or NO."
    )
    res = llm_call(
        client, "gpt-4o-mini", [{"role": "user", "content": prompt}],
        emitter=emitter, doc_id=doc_id, step="step1", action="llm_verify", temperature=0,
    )
    return res.choices[0].message.content.strip()


def _verify_domain(client, name, domain, ctx, emitter, doc_id):
    text = _get_website_text(domain)
    if not text:
        return False, ""
    sig = signal_match(name, text, ctx)
    if sig:
        return True, text
    return "YES" in _ai_verify(client, name, text, ctx, emitter, doc_id).upper(), text


def _mark_found(col, _id, name, domain, method, ctx):
    col.update_one({"_id": _id}, {
        "$set": {
            "status": "find_domain",
            "company_url": domain,
            "domain_status_method": method,
            "domain_context_used": list(ctx.keys()),
            "domain_found_at": datetime.now(timezone.utc),
        },
        "$unset": {"domain_status_error": ""},
    })
    logger.info(f"[STEP1][{method}] '{name}' -> {domain}")


def find_domain_for_doc(doc, cfg, col, client, emitter, cancel):
    name = clean_value(doc.get(cfg.name_field, ""))
    _id = doc["_id"]
    source = clean_value(doc.get(cfg.source_field, ""))
    doc_id = str(_id)

    if cancel and cancel.is_set():
        return

    if not name:
        col.update_one({"_id": _id}, {"$set": {
            "status": "domain_not_found", "domain_status_error": "Empty company_name",
        }})
        return

    try:
        ctx = extract_context(doc, cfg.field_mapping)
        country_hint = ctx.get("country") or get_country_hint(source)

        for d in email_domains(ctx.get("email", "")):
            domain = normalize_domain(d)
            if not domain:
                continue
            ok, text = _verify_domain(client, name, domain, ctx, emitter, doc_id)
            if ok:
                _mark_found(col, _id, name, domain, "email_domain", ctx)
                return
            if not text and cfg.trust_email_domain:
                _mark_found(col, _id, name, domain, "email_domain_unverified", ctx)
                return

        for w in re.split(r'[,\s;|]+', ctx.get("website", "")):
            if not w or is_blacklisted(w):
                continue
            domain = normalize_domain(w)
            if not domain:
                continue
            ok, _ = _verify_domain(client, name, domain, ctx, emitter, doc_id)
            if ok:
                _mark_found(col, _id, name, domain, "given_website", ctx)
                return

        search_data = None
        for q in build_search_queries(name, ctx, country_hint):
            if cancel and cancel.is_set():
                return
            data = serper_call(cfg.serper_api_key, q, emitter=emitter, doc_id=doc_id, step="step1", cancel=cancel)
            if data and data.get("organic"):
                search_data = data
                break

        if not search_data:
            raise Exception("Serper returned nothing")

        results_text = "\n".join(
            f"{item.get('title')} | {item.get('link')} | {(item.get('snippet') or '')[:200]}"
            for item in search_data.get("organic", [])[:10]
            if item.get("link") and not is_blacklisted(item.get("link", ""))
        )
        candidate = _ai_select(client, name, results_text, country_hint, ctx, emitter, doc_id)
        if not candidate or candidate.lower() == "none":
            raise Exception("No candidate from AI")
        domain = normalize_domain(candidate)
        if not domain:
            raise Exception(f"Could not normalize: {candidate}")
        if is_blacklisted(domain):
            raise Exception(f"AI picked blacklisted domain: {domain}")
        ok, _ = _verify_domain(client, name, domain, ctx, emitter, doc_id)
        if ok:
            _mark_found(col, _id, name, domain, "ai_select", ctx)
        else:
            raise Exception("AI verification failed")
    except CreditExpired:
        raise
    except Exception as e:
        col.update_one({"_id": _id}, {"$set": {
            "status": "domain_not_found", "company_url": None, "domain_status_error": str(e),
        }})
        logger.warning(f"[STEP1][NOT FOUND] '{name}' | {e}")


def run_step1(cfg, local_client, cancel, emitter, progress_cb=None):
    col = local_client[cfg.local_db][cfg.local_col]
    proj = {"_id": 1, cfg.name_field: 1, cfg.source_field: 1}
    for fields in cfg.field_mapping.values():
        for f in fields:
            proj[f] = 1
    docs = list(col.find({"status": "unprocessed"}, proj))
    if cfg.max_docs:
        docs = docs[:cfg.max_docs]
    logger.info(f"STEP 1 — Domain Finder | Docs: {len(docs)}")
    if not docs:
        return
    client = OpenAI(api_key=cfg.openai_api_key)
    processed = 0
    with ThreadPoolExecutor(max_workers=cfg.domain_threads) as ex:
        futs = {ex.submit(find_domain_for_doc, d, cfg, col, client, emitter, cancel): d for d in docs}
        for f in as_completed(futs):
            if cancel and cancel.is_set():
                ex.shutdown(wait=False, cancel_futures=True)
                break
            try:
                f.result()
            except CreditExpired:
                ex.shutdown(wait=False, cancel_futures=True)
                raise
            except Exception as e:
                logger.error(f"Step1 thread: {e}")
            processed += 1
            if progress_cb and processed % 10 == 0:
                progress_cb(processed=processed)
