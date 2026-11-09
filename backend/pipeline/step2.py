"""Step 2 — Domain Matcher (read-only master in MVP)."""
import logging
from pymongo import UpdateOne
from pipeline.helpers import extract_domain_parts

logger = logging.getLogger(__name__)


def _empty_match():
    return {
        "matched": False, "company_name_db": "", "country_db": "",
        "_id": None, "org_sources": [], "filter_sources": [],
    }


def batch_check_domains(batch, master_col):
    all_d = set()
    for full, base in batch:
        if full:
            all_d.add(full)
        if base and base != full:
            all_d.add(base)
    if not all_d:
        return {}
    if master_col is None:
        return {full: _empty_match() for full, _ in batch}

    query = {"$or": [
        {"organization.domain_list": {"$in": list(all_d)}},
        {"organization.primary_domain": {"$in": list(all_d)}},
    ]}
    try:
        cursor = master_col.find(query, {
            "_id": 1,
            "organization.primary_domain": 1,
            "organization.domain_list": 1,
            "organization.name": 1,
            "organization.country": 1,
        }).max_time_ms(30000).batch_size(100)
        db_map = {}
        for doc in cursor:
            org = doc.get("organization", {})
            dl = org.get("domain_list", [])
            if not isinstance(dl, list):
                dl = [dl] if dl else []
            pd_ = (org.get("primary_domain", "") or "").lower()
            data = {
                "matched": True,
                "company_name_db": org.get("name", ""),
                "country_db": org.get("country", ""),
                "_id": doc["_id"],
            }
            for d in [x.lower() for x in dl if x]:
                if d in all_d:
                    db_map[d] = data
            if pd_ and pd_ in all_d:
                db_map[pd_] = data
    except Exception as e:
        logger.error(f"[STEP2] Master cursor error: {e}")
        return {}

    result = {}
    for full, base in batch:
        info = db_map.get(full) or db_map.get(base)
        result[full] = info if info else _empty_match()
    return result


def run_step2(cfg, local_client, master_client, cancel, emitter):
    col = local_client[cfg.local_db][cfg.local_col]
    query = {
        "$and": [
            {"$or": [
                {"status": "find_domain"},
                {"status": {"$exists": False}},
                {"status": None},
            ]},
            {"company_url": {"$exists": True, "$nin": ["", None]}},
        ]
    }
    docs = list(col.find(query, {"_id": 1, "company_url": 1, cfg.source_field: 1}))
    logger.info(f"STEP 2 — Domain Matcher | Docs: {len(docs)}")
    if not docs:
        return

    master_col = None
    if master_client and cfg.master_uri:
        master_col = master_client[cfg.master_db][cfg.master_col]
    else:
        logger.warning("[STEP2] No master — all unmatched")

    pairs = [extract_domain_parts(d.get("company_url", "")) for d in docs]
    batch_size = cfg.domain_batch
    domain_results = {}
    for i in range(0, len(pairs), batch_size):
        if cancel and cancel.is_set():
            return
        chunk = pairs[i:i + batch_size]
        domain_results.update(batch_check_domains(chunk, master_col))

    ops = []
    matched_cnt = no_match_cnt = 0
    for doc, (full_domain, _) in zip(docs, pairs):
        _id = doc["_id"]
        if not full_domain:
            ops.append(UpdateOne({"_id": _id}, {"$set": {
                "status": "unmatched", "domain_full": "", "domain_company_db": "",
                "domain_country_db": "", "step2_source_updated": False,
            }}))
            no_match_cnt += 1
            continue
        info = domain_results.get(full_domain, {})
        if info.get("matched"):
            matched_cnt += 1
            ops.append(UpdateOne({"_id": _id}, {"$set": {
                "status": "matched",
                "domain_full": full_domain,
                "domain_company_db": info.get("company_name_db", ""),
                "domain_country_db": info.get("country_db", ""),
                "step2_source_updated": False,
            }}))
        else:
            no_match_cnt += 1
            ops.append(UpdateOne({"_id": _id}, {"$set": {
                "status": "unmatched",
                "domain_full": full_domain,
                "domain_company_db": "",
                "domain_country_db": "",
                "step2_source_updated": False,
            }}))

    if ops:
        for i in range(0, len(ops), 2000):
            col.bulk_write(ops[i:i + 2000], ordered=False)
    logger.info(f"STEP 2 DONE | Matched: {matched_cnt} | Unmatched: {no_match_cnt}")
