import json
import re
import logging
from typing import List
from pipeline.helpers import COMPANY_TYPES, EMPLOYEE_COUNTS
from pipeline.pricing import PRICING
from pipeline.exceptions import CreditExpired
from pipeline.helpers import is_fatal_api_error

logger = logging.getLogger(__name__)

try:
    from crewai import Agent, Task, Crew, Process, LLM
    from crewai_tools import SerperDevTool
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    logger.warning("CrewAI not installed")


class CountingSerperTool:
    """Wrapper that counts Serper calls inside CrewAI."""
    def __init__(self, counter: dict):
        self._counter = counter
        self._tool = SerperDevTool() if CREWAI_AVAILABLE else None

    def _run(self, *a, **kw):
        self._counter["n"] = self._counter.get("n", 0) + 1
        return self._tool._run(*a, **kw)

    def __getattr__(self, name):
        return getattr(self._tool, name)


def create_agents(llm, serper_counter=None):
    tools = []
    if CREWAI_AVAILABLE:
        try:
            if serper_counter is not None:
                tools.append(CountingSerperTool(serper_counter))
            else:
                tools.append(SerperDevTool())
        except Exception as e:
            logger.warning(f"SerperDevTool unavailable: {e}")
    data_scraper = Agent(
        llm=llm,
        role="Data Scraper",
        goal="Extract all relevant company information from provided content and online sources",
        backstory=(
            "You are a skilled web scraper and data analyst, adept at extracting and organizing "
            "company information from various online sources."
        ),
        tools=tools,
        verbose=False,
        allow_delegation=False,
    )
    info_aggregator = Agent(
        llm=llm,
        role="Information Aggregator",
        goal="Compile and structure all gathered information into a comprehensive company profile.",
        backstory="You are an expert in data synthesis and organization.",
        tools=[],
        verbose=False,
        allow_delegation=False,
    )
    return [data_scraper, info_aggregator]


def create_tasks(company_name, company_url, agents, page_content=""):
    types_str = ", ".join(COMPANY_TYPES)
    emp_str = ", ".join(EMPLOYEE_COUNTS)
    if page_content:
        desc = (
            f"Analyze the following pre-fetched website content for company '{company_name}' "
            f"(Website: {company_url}) and extract all available company information.\n\n"
            f"=== PRE-FETCHED WEBSITE CONTENT ===\n{page_content}\n=== END ===\n\n"
            "Extract: Employees, Company Type, Industry, Company Linkedin Url, Facebook Url, Twitter Url, "
            "Company Street, Company City, Company State, Company Country, Company Postal Code, "
            "Company Address, Keywords, Company Phone, SEO Description, Short Description, "
            "Founded Year, Logo Url, Email.\n"
            f"For Company Type only use one of: {types_str}.\n"
            f"For Employees only one of: {emp_str}. Round UP if between values.\n"
            "Keep null if not found. Do not invent."
        )
    else:
        desc = (
            f"Using website URL '{company_url}' and company name '{company_name}', "
            f"search and extract company information including Employees, Company Type, Industry, "
            "Company Linkedin Url, Facebook Url, Twitter Url, address fields, Keywords, Phone, "
            "SEO Description, Short Description, Founded Year, Logo Url, Email.\n"
            f"Company Type: {types_str}. Employees: {emp_str}."
        )
    task1 = Task(
        description=desc,
        expected_output="A dictionary of company information fields.",
        agent=agents[0],
    )
    task2 = Task(
        description=(
            "Compile into JSON with EXACTLY these keys: Employees, Company Type, Industry, "
            "Company Linkedin Url, Facebook Url, Twitter Url, Company Street, Company City, "
            "Company State, Company Country, Company Postal Code, Company Address, Keywords, "
            "Company Phone, SEO Description, Short Description, Founded Year, Logo Url, Email, "
            "original_language. Return ONLY valid JSON."
        ),
        expected_output="JSON object of company information.",
        agent=agents[1],
    )
    return [task1, task2]


def parse_crewai_output(tasks) -> dict:
    company_info = {}
    for task in tasks:
        try:
            task_output = task.output
        except AttributeError:
            continue
        if task_output is None:
            continue
        try:
            if getattr(task_output, "json_dict", None):
                company_info.update(task_output.json_dict)
                continue
        except Exception:
            pass
        raw = getattr(task_output, "raw", "") or ""
        raw = re.sub(r'^```(?:json)?\s*', '', raw.strip())
        raw = re.sub(r'\s*```$', '', raw).strip()
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                company_info.update(parsed)
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group())
                    if isinstance(parsed, dict):
                        company_info.update(parsed)
                except Exception:
                    pass
    return company_info


def run_crewai(company_name, company_url, page_content, cfg, emitter, doc_id):
    if not CREWAI_AVAILABLE:
        raise RuntimeError("CrewAI not available")
    serper_counter = {"n": 0}
    llm = LLM(model=cfg.crewai_model, temperature=0, api_key=cfg.openai_api_key)
    agents = create_agents(llm, serper_counter)
    tasks = create_tasks(company_name, company_url, agents, page_content)
    crew = Crew(agents=agents, tasks=tasks, process=Process.sequential, verbose=False)
    try:
        result = crew.kickoff()
        # usage metrics
        usage = getattr(crew, "usage_metrics", None) or {}
        tin = int(getattr(usage, "prompt_tokens", 0) or usage.get("prompt_tokens", 0) or 0)
        tout = int(getattr(usage, "completion_tokens", 0) or usage.get("completion_tokens", 0) or 0)
        prices = PRICING.get(cfg.crewai_model, PRICING["gpt-4o-mini"])
        cost = prices["in"] * tin + prices["out"] * tout
        emitter.emit(
            doc_id=doc_id, step="step3", action="crewai", success=True,
            model=cfg.crewai_model, tokens_in=tin, tokens_out=tout, cost_usd=cost,
        )
        if serper_counter["n"]:
            emitter.emit(
                doc_id=doc_id, step="step3", action="serper", success=True,
                serper_queries=serper_counter["n"],
                cost_usd=serper_counter["n"] * PRICING["serper"],
            )
        return parse_crewai_output(tasks)
    except Exception as e:
        if is_fatal_api_error(e):
            raise CreditExpired(f"openai:{e}")
        raise
