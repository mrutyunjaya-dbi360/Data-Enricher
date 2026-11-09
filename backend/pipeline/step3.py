"""Step 3 — CrewAI company details scraper."""
import logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pymongo import ReturnDocument
from pipeline.helpers import clean_text, clean_url, clean_company_record
from pipeline.crawl import crawl_call
from pipeline.crew import run_crewai, CREWAI_AVAILABLE
from pipeline.exceptions import CreditExpired

logger = logging.getLogger(__name__)


def build_scraped_details(company_name, company_url, raw_data):
    return {
        "Company": company_name,
        "Company Name for Emails": company_name,
        "Employees": raw_data.get("Employees"),
        "Company Type": raw_data.get("Company Type"),
        "Industry": raw_data.get("Industry"),
        "Website": company_url,
        "Email": raw_data.get("Email"),
        "Company Linkedin Url": raw_data.get("Company Linkedin Url"),
        "Facebook Url": raw_data.get("Facebook Url"),
        "Twitter Url": raw_data.get("Twitter Url"),
        "Company Street": raw_data.get("Company Street"),
        "Company City": raw_data.get("Company City"),
        "Company State": raw_data.get("Company State"),
        "Company Country": raw_data.get("Company Country"),
        "Company Postal Code": raw_data.get("Company Postal Code"),
        "Company Address": raw_data.get("Company Address"),
        "Keywords": raw_data.get("Keywords"),
        "Company Phone": raw_data.get("Company Phone"),
        "SEO Description": raw_data.get("SEO Description"),
        "Short Description": raw_data.get("Short Description"),
        "Founded Year": raw_data.get("Founded Year"),
        "Logo Url": raw_data.get("Logo Url"),
        "Original Language": raw_data.get("original_language", "English"),
        "status": "processed",
    }


def _completeness(details: dict) -> float:
    keys = [
        "Employees", "Company Type", "Industry", "Email", "Company Phone",
        "Company City", "Company Country", "Short Description", "Founded Year",
        "Company Linkedin Url", "Keywords",
    ]
    filled = sum(1 for k in keys if details.get(k))
    return round(filled / len(keys), 3)


def record_failure(col, _id, err, crawl4ai_used, max_attempts):
    res = col.find_one_and_update(
        {"_id": _id},
        {
            "$inc": {"step3_attempts": 1},
            "$set": {
                "status": "unmatched",
                "company_details_completed": datetime.now(timezone.utc),
                "company_details_error": err,
                "crawl4ai_used": crawl4ai_used,
            },
        },
        projection={"step3_attempts": 1},
        return_document=ReturnDocument.AFTER,
    )
    attempts = (res or {}).get("step3_attempts", 1)
    if attempts >= max_attempts:
        col.update_one({"_id": _id}, {"$set": {"status": "scrape_failed"}})
        logger.error(f"[STEP3] {_id} failed {attempts}x — scrape_failed")


def scrape_one(doc, cfg, col, emitter, cancel):
    _id = doc["_id"]
    doc_id = str(_id)
    company_name = clean_text(doc.get(cfg.name_field, ""), 300) or ""
    company_url = clean_url(doc.get("company_url", "")) or ""
    crawl4ai_used = False

    if cancel and cancel.is_set():
        return

    try:
        page_content = ""
        if company_url:
            page_content = crawl_call(company_url, cfg=cfg, emitter=emitter, doc_id=doc_id)
            crawl4ai_used = bool(page_content)

        raw_data = run_crewai(company_name, company_url, page_content, cfg, emitter, doc_id)
        if not raw_data:
            raise Exception("CrewAI returned empty data")

        scraped = clean_company_record(build_scraped_details(company_name, company_url, raw_data))
        col.update_one({"_id": _id}, {"$set": {
            "status": "processed",
            "company_details_completed": datetime.now(timezone.utc),
            "company_details_error": None,
            "scraped_details": scraped,
            "crawl4ai_used": crawl4ai_used,
        }})

        # DocQuality upsert via emitter path
        try:
            from metrics.models import DocQuality
            from decimal import Decimal
            fields_present = {k: bool(v) for k, v in scraped.items() if k not in ("status",)}
            DocQuality.objects.update_or_create(
                job_id=cfg.job_id,
                doc_id=doc_id,
                defaults={
                    "datasource_id": cfg.datasource_id,
                    "datasource_owner_id": cfg.datasource_owner_id,
                    "domain": company_url or "",
                    "method": "crewai",
                    "status": "processed",
                    "completeness": Decimal(str(_completeness(scraped))),
                    "confidence": Decimal("0.800"),
                    "fields": fields_present,
                    "validation_errors": [],
                },
            )
        except Exception as e:
            logger.warning(f"DocQuality upsert failed: {e}")

        emitter.emit(
            doc_id=doc_id, step="step3", action="doc_complete", success=True,
            method="crewai", cost_usd=float(emitter.doc_cost(doc_id)),
        )
        logger.info(f"[STEP3][DONE] '{company_name}'")
    except CreditExpired:
        raise
    except Exception as e:
        record_failure(col, _id, str(e), crawl4ai_used, cfg.max_step3_attempts)
        emitter.emit(doc_id=doc_id, step="step3", action="doc_complete", success=False,
                     error_type=type(e).__name__)
        logger.warning(f"[STEP3][ERROR] '{company_name}' | {e}")


def run_step3(cfg, local_client, cancel, emitter, progress_cb=None):
    if not CREWAI_AVAILABLE:
        logger.warning("CrewAI not available — skipping Step 3")
        return
    col = local_client[cfg.local_db][cfg.local_col]
    query = {
        "status": "unmatched",
        "$or": [
            {"step3_attempts": {"$exists": False}},
            {"step3_attempts": {"$lt": cfg.max_step3_attempts}},
        ],
    }
    docs = list(col.find(query, {"_id": 1, cfg.name_field: 1, "company_url": 1}))
    if cfg.max_docs:
        docs = docs[:cfg.max_docs]
    logger.info(f"STEP 3 — CrewAI scrape | Docs: {len(docs)}")
    if not docs:
        return
    processed = 0
    with ThreadPoolExecutor(max_workers=cfg.crewai_threads) as ex:
        futs = {ex.submit(scrape_one, d, cfg, col, emitter, cancel): d for d in docs}
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
                logger.error(f"Step3 thread: {e}")
            processed += 1
            if progress_cb and processed % 5 == 0:
                progress_cb(processed=processed)
