import asyncio
import logging
import time
from pipeline.pricing import PRICING

logger = logging.getLogger(__name__)

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False

try:
    from crawl4ai import CacheMode
except Exception:
    CacheMode = None


async def _async_fetch(url: str, max_chars: int, timeout: int) -> str:
    browser_cfg = BrowserConfig(headless=True, verbose=False)
    run_kwargs = dict(
        word_count_threshold=10,
        exclude_external_links=True,
        remove_overlay_elements=True,
        page_timeout=timeout * 1000,
    )
    if CacheMode is not None:
        run_kwargs["cache_mode"] = CacheMode.BYPASS
    run_cfg = CrawlerRunConfig(**run_kwargs)
    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)
        if result.success and result.markdown:
            return str(result.markdown).strip()[:max_chars]
        return ""


def fetch_company_page(url: str, max_chars: int = 12000, timeout: int = 30) -> str:
    if not url or not CRAWL4AI_AVAILABLE:
        return ""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_async_fetch(url, max_chars, timeout))
        finally:
            loop.close()
    except Exception as e:
        logger.warning(f"Crawl4AI failed for {url}: {e}")
        return ""


def crawl_call(url, *, cfg, emitter, doc_id, step="step3"):
    t0 = time.time()
    content = fetch_company_page(url, cfg.crawl4ai_max_chars, cfg.crawl4ai_timeout)
    nbytes = len(content.encode("utf-8")) if content else 0
    emitter.emit(
        doc_id=doc_id, step=step, action="crawl4ai", success=bool(content),
        crawl_bytes=nbytes, latency_ms=int((time.time() - t0) * 1000),
    )
    return content
