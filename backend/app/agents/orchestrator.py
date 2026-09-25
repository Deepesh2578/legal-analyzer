import time
import json
import logging
from typing import TypedDict, Annotated
import operator
from datetime import datetime

from langgraph.graph import StateGraph, START, END

from app.core.database import SessionLocal
from app.models.document import Document, DocumentStatus
from app.agents.document_parser import DocumentParser
from app.agents.clause_extractor import ClauseExtractor
from app.agents.gemini_extractor import GeminiExtractor

logger = logging.getLogger(__name__)


class DocumentState(TypedDict):
    doc_id: int
    file_path: str
    file_content: bytes
    raw_text: str
    processed_text: str
    word_count: int
    page_count: int
    regex_clauses: list
    gemini_clauses: list
    clauses: list
    risk_report: dict
    compliance_report: dict
    citations: dict
    reasoning_trace: Annotated[list, operator.add]
    error: str
    status: str


def parse_node(state: DocumentState) -> dict:
    start = time.time()
    try:
        parser = DocumentParser()
        result = parser.parse_document(state["file_path"], state.get("file_content"))
        duration = int((time.time() - start) * 1000)
        logger.info(f"[parse] doc {state['doc_id']} → {result.get('word_count', 0)} words")
        return {
            "raw_text": result.get("raw_text", ""),
            "processed_text": result.get("processed_text", ""),
            "word_count": result.get("word_count", 0),
            "page_count": result.get("page_count", 0),
            "reasoning_trace": [{
                "step": "parse_document",
                "status": "success",
                "duration_ms": duration,
                "message": f"Extracted {result.get('word_count', 0)} words from {result.get('page_count', 0)} pages",
            }],
        }
    except Exception as e:
        logger.error(f"[parse] failed: {e}")
        return {
            "error": str(e),
            "reasoning_trace": [{
                "step": "parse_document",
                "status": "failed",
                "duration_ms": int((time.time() - start) * 1000),
                "message": str(e),
            }],
        }


def extract_clauses_node(state: DocumentState) -> dict:
    start = time.time()
    text = state.get("processed_text", "")
    if not text:
        return {
            "reasoning_trace": [{
                "step": "clause_extraction",
                "status": "skipped",
                "duration_ms": int((time.time() - start) * 1000),
                "message": "No text to extract",
            }]
        }

    regex_clauses = []
    gemini_clauses = []

    try:
        regex_clauses = ClauseExtractor().extract(text)
    except Exception as e:
        logger.error(f"[clauses] regex failed: {e}")

    try:
        gemini_clauses = GeminiExtractor().extract(text)
    except Exception as e:
        logger.error(f"[clauses] gemini failed: {e}")

    clauses = gemini_clauses if gemini_clauses else regex_clauses
    duration = int((time.time() - start) * 1000)
    logger.info(f"[clauses] regex={len(regex_clauses)}, gemini={len(gemini_clauses)}, using={len(clauses)}")

    return {
        "regex_clauses": regex_clauses,
        "gemini_clauses": gemini_clauses,
        "clauses": clauses,
        "reasoning_trace": [{
            "step": "clause_extraction",
            "status": "success",
            "duration_ms": duration,
            "message": f"Regex: {len(regex_clauses)}, Gemini: {len(gemini_clauses)} → using {len(clauses)}",
        }],
    }


def risk_analysis_node(state: DocumentState) -> dict:
    start = time.time()
    clauses = state.get("clauses", [])
    if not clauses:
        return {
            "risk_report": {},
            "reasoning_trace": [{
                "step": "risk_analysis",
                "status": "skipped",
                "duration_ms": int((time.time() - start) * 1000),
                "message": "No clauses to analyze",
            }]
        }

    risk_weights = {"High": 10, "Medium": 5, "Low": 1}
    total_weight = 0
    breakdown = {"high": 0, "medium": 0, "low": 0}
    enriched = []

    for c in clauses:
        risk = c.get("risk_level", "Low")
        if risk not in risk_weights:
            risk = "Low"
        total_weight += risk_weights[risk]
        breakdown[risk.lower()] += 1
        enriched.append({
            "type": c.get("type"),
            "text": c.get("text", "")[:200],
            "summary": c.get("summary", ""),
            "risk_level": risk,
            "suggestion": c.get("suggestion"),
        })

    max_possible = len(clauses) * 10
    score = round((total_weight / max_possible) * 100) if max_possible else 0
    level = "High" if score >= 70 else ("Medium" if score >= 40 else "Low")


    report = {
        "document_id": state["doc_id"],
        "overall_risk_score": score,
        "risk_level": level,
        "breakdown": breakdown,
        "clauses": enriched,
        "total_clauses": len(enriched),
        "summary": f"Document has {breakdown['high']} high, {breakdown['medium']} medium, and {breakdown['low']} low-risk clauses.",
    }
    logger.info(f"[risk] score={score}/100 ({level})")
    return {
        "risk_report": report,
        "reasoning_trace": [{
            "step": "risk_analysis",
            "status": "success",
            "duration_ms": int((time.time() - start) * 1000),
            "message": f"Score: {score}/100 ({level})",
        }],
    }


def compliance_node(state: DocumentState) -> dict:
    start = time.time()
    clauses = state.get("clauses", [])
    if not clauses:
        return {
            "compliance_report": {},
            "reasoning_trace": [{
                "step": "compliance_check",
                "status": "skipped",
                "duration_ms": int((time.time() - start) * 1000),
                "message": "No clauses to check",
            }]
        }

    try:
        from app.agents.compliance_agent import ComplianceAgent
        agent = ComplianceAgent()
        results = []
        violations = 0
        for c in clauses[:3]:
            r = agent.check_clause(c.get("type", "Unknown"), c.get("text", ""))
            results.append(r)
            if r.get("is_violation") is True:
                violations += 1

        total = len(results)
        compliant = total - violations
        score = round((compliant / total) * 100) if total else 100

        report = {
            "compliance_score": score,
            "total_checks": total,
            "violations": violations,
            "compliance_results": results,
        }
        status = "success"
        msg = f"Checked {total} clauses, {violations} violations"
        logger.info(f"[compliance] {msg}")
    except Exception as e:
        logger.error(f"[compliance] failed: {e}")
        report = {}
        status = "failed"
        msg = str(e)[:200]

    return {
        "compliance_report": report,
        "reasoning_trace": [{
            "step": "compliance_check",
            "status": status,
            "duration_ms": int((time.time() - start) * 1000),
            "message": msg,
        }],
    }


def citation_node(state: DocumentState) -> dict:
    start = time.time()
    clauses = state.get("clauses", [])
    if not clauses:
        return {
            "citations": {},
            "reasoning_trace": [{
                "step": "citation_lookup",
                "status": "skipped",
                "duration_ms": int((time.time() - start) * 1000),
                "message": "No clauses",
            }]
        }

    try:
        from app.agents.citation_agent import CitationAgent
        agent = CitationAgent()
        citations = {}
        for c in clauses:
            ct = c.get("type", "Unknown")
            if ct not in citations:
                citations[ct] = agent.find_citations(ct, c.get("text", ""))

        total = sum(len(v) for v in citations.values())
        status = "success"
        msg = f"Found {total} cases across {len(citations)} clause types"
        logger.info(f"[citation] {msg}")
    except Exception as e:
        logger.error(f"[citation] failed: {e}")
        citations = {}
        status = "failed"
        msg = str(e)[:200]

    return {
        "citations": citations,
        "reasoning_trace": [{
            "step": "citation_lookup",
            "status": status,
            "duration_ms": int((time.time() - start) * 1000),
            "message": msg,
        }],
    }


def save_node(state: DocumentState) -> dict:
    start = time.time()
    doc_id = state["doc_id"]
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return {
                "reasoning_trace": [{
                    "step": "save_results",
                    "status": "failed",
                    "duration_ms": 0,
                    "message": "Document not found",
                }]
            }

        extra = {}
        if doc.extra_data:
            try:
                extra = json.loads(doc.extra_data) if isinstance(doc.extra_data, str) else doc.extra_data
            except:
                extra = {}

        extra["regex_clauses"] = state.get("regex_clauses", [])
        extra["gemini_clauses"] = state.get("gemini_clauses", [])
        extra["clauses"] = state.get("clauses", [])
        extra["risk_report"] = state.get("risk_report", {})
        extra["compliance_report"] = state.get("compliance_report", {})
        extra["citations"] = state.get("citations", {})
        extra["reasoning_trace"] = state.get("reasoning_trace", [])

        doc.extra_data = json.dumps(extra)
        doc.raw_text = state.get("raw_text", "")
        doc.processed_text = state.get("processed_text", "")
        doc.word_count = state.get("word_count", 0)
        doc.page_count = state.get("page_count", 0)
        doc.status = DocumentStatus.PARSED
        doc.progress = 100
        doc.processed_at = datetime.utcnow()

        db.commit()
        db.refresh(doc)
        logger.info(f"[save] doc {doc_id} saved successfully")

        return {
            "reasoning_trace": [{
                "step": "save_results",
                "status": "success",
                "duration_ms": int((time.time() - start) * 1000),
                "message": f"Saved {len(state.get('clauses', []))} clauses + reports",
            }],
            "status": "complete",
        }
    except Exception as e:
        logger.error(f"[save] failed: {e}")
        db.rollback()
        return {
            "reasoning_trace": [{
                "step": "save_results",
                "status": "failed",
                "duration_ms": int((time.time() - start) * 1000),
                "message": str(e),
            }]
        }
    finally:
        db.close()


def build_orchestrator_graph():
    graph = StateGraph(DocumentState)

    graph.add_node("parse", parse_node)
    graph.add_node("extract_clauses", extract_clauses_node)
    graph.add_node("risk_analysis", risk_analysis_node)
    graph.add_node("compliance_check", compliance_node)
    graph.add_node("citation_lookup", citation_node)
    graph.add_node("save", save_node)

    graph.add_edge(START, "parse")
    graph.add_edge("parse", "extract_clauses")

    # Parallel fan-out (3 agents run simultaneously)
    graph.add_edge("extract_clauses", "risk_analysis")
    graph.add_edge("extract_clauses", "compliance_check")
    graph.add_edge("extract_clauses", "citation_lookup")

    # Fan-in (wait for all 3 to finish)
    graph.add_edge("risk_analysis", "save")
    graph.add_edge("compliance_check", "save")
    graph.add_edge("citation_lookup", "save")

    graph.add_edge("save", END)

    return graph.compile()
