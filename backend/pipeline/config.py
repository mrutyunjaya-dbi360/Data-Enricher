from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import json


DEFAULT_CONTEXT_FIELD_MAP = {
    "country": ["country", "company_country", "Country", "Company Country"],
    "state": ["state", "company_state", "State"],
    "city": ["city", "company_city", "City"],
    "address": ["address", "company_address", "Address"],
    "industry": ["industry", "Industry", "sector"],
    "product": ["product", "products", "product_description", "hs_description"],
    "phone": ["phone", "company_phone", "contact_number", "Phone"],
    "email": ["email", "company_email", "contact_email", "Email"],
    "website": ["website", "company_website", "Website", "domain"],
    "person_name": ["contact_name", "person_name", "contact_person"],
}


@dataclass
class JobConfig:
    job_id: str
    local_uri: str
    local_db: str
    local_col: str
    master_uri: Optional[str] = None
    master_db: str = "Master"
    master_col: str = "organizationmaster"
    name_field: str = "company_name"
    source_field: str = "source"
    field_mapping: Dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_CONTEXT_FIELD_MAP))
    max_docs: int = 0  # 0 = unlimited
    max_cycles: int = 10
    domain_threads: int = 10
    crewai_threads: int = 5
    serper_concurrency: int = 5
    openai_concurrency: int = 5
    trust_email_domain: bool = True
    domain_batch: int = 100
    update_master: bool = False  # MVP: read-only
    crawl4ai_max_chars: int = 12000
    crawl4ai_timeout: int = 30
    max_step3_attempts: int = 3
    crewai_model: str = "openai/gpt-4o-mini"
    openai_api_key: str = ""
    serper_api_key: str = ""
    tenant_id: str = ""
    datasource_id: str = ""
    datasource_owner_id: str = ""
    submitted_by_id: str = ""

    @classmethod
    def from_job(cls, job, decrypted_uri: str, decrypted_master_uri: Optional[str] = None):
        from django.conf import settings
        cfg = job.config or {}
        ds = job.datasource
        mapping = ds.field_mapping or DEFAULT_CONTEXT_FIELD_MAP
        return cls(
            job_id=str(job.id),
            local_uri=decrypted_uri,
            local_db=ds.db_name,
            local_col=ds.col_name,
            master_uri=decrypted_master_uri,
            name_field=cfg.get("name_field", "company_name"),
            source_field=cfg.get("source_field", "source"),
            field_mapping=mapping,
            max_docs=cfg.get("max_docs", 0),
            max_cycles=cfg.get("max_cycles", 10),
            domain_threads=cfg.get("domain_threads", 10),
            crewai_threads=cfg.get("crewai_threads", 5),
            crawl4ai_max_chars=getattr(settings, "CRAWL4AI_MAX_CHARS", 12000),
            crawl4ai_timeout=getattr(settings, "CRAWL4AI_TIMEOUT", 30),
            max_step3_attempts=getattr(settings, "MAX_STEP3_ATTEMPTS", 3),
            crewai_model=getattr(settings, "CREWAI_MODEL", "openai/gpt-4o-mini"),
            openai_api_key=getattr(settings, "OPENAI_API_KEY", ""),
            serper_api_key=getattr(settings, "SERPER_API_KEY", ""),
            tenant_id=str(job.tenant_id),
            datasource_id=str(job.datasource_id),
            datasource_owner_id=str(job.datasource_owner_id),
            submitted_by_id=str(job.submitted_by_id),
        )
