import json
import os
import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.document import Document, DocumentStatus
from app.schemas.document import DocumentResponse, DocumentTextResponse
from app.agents.document_parser import DocumentParser
from app.agents.clause_extractor import ClauseExtractor
from app.agents.gemini_extractor import GeminiExtractor

def parse_extra_data(raw) -> dict:
    """
    Safely parse extra_data which may be a dict, a JSON string,
    or a double-encoded JSON string. Returns an empty dict on failure.
    """
    if raw is None:
        return {}
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        # Handle double-encoded JSON
        if isinstance(parsed, str):
            parsed = json.loads(parsed)
        return parsed if isinstance(parsed, dict) else {}
    except Exception as e:
        logger.warning(f"Failed to parse extra_data: {e}")
        return {}

logger = logging.getLogger(__name__)
router = APIRouter()
parser = DocumentParser()


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    allowed = ['.pdf', '.docx']
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"Allowed: {', '.join(allowed)}")

    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    unique_name = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(upload_dir, unique_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
        filename=file.filename,
        file_path=file_path,
        file_size=len(content),
        file_type=ext,
        status=DocumentStatus.PENDING,
        extra_data=json.dumps({"uploaded_at": datetime.utcnow().isoformat()})
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(process_document, doc.id, file_path, content, db)

    return {
        "document_id": doc.id,
        "filename": doc.filename,
        "status": "processing",
        "message": "Document uploaded."
    }


async def process_document(doc_id: int, file_path: str, content: bytes, db: Session):
    """Process document using LangGraph orchestrator — runs in a worker thread so the event loop stays free."""
    import asyncio
    from app.agents.orchestrator import build_orchestrator_graph

    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return
        doc.status = DocumentStatus.PROCESSING
        doc.progress = 10
        db.commit()

        logger.info(f"🚀 Starting LangGraph orchestrator for doc {doc_id}")

        # ── Build the graph once ──
        graph = build_orchestrator_graph()

        initial_state = {
            "doc_id": doc_id,
            "file_path": file_path,
            "file_content": content,
            "raw_text": "",
            "processed_text": "",
            "word_count": 0,
            "page_count": 0,
            "regex_clauses": [],
            "gemini_clauses": [],
            "clauses": [],
            "risk_report": {},
            "compliance_report": {},
            "citations": {},
            "reasoning_trace": [],
            "error": "",
            "status": "processing",
        }

        # ── Run the heavy blocking work in a separate thread ──
        # This keeps the FastAPI event loop responsive so other API
        # calls (uploads, risk/compliance lookups, /ping) still work.
        final_state = await asyncio.to_thread(graph.invoke, initial_state)

        logger.info(f"✅ Orchestrator completed for doc {doc_id}")

        # ── Ensure save_results trace entry exists ──
        if final_state.get("status") == "complete":
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                extra = {}
                if doc.extra_data:
                    try:
                        extra = json.loads(doc.extra_data) if isinstance(doc.extra_data, str) else doc.extra_data
                    except:
                        pass
                trace = extra.get("reasoning_trace", [])
                if not any(t.get("step") == "save_results" for t in trace):
                    trace.append({
                        "step": "save_results",
                        "status": "success",
                        "duration_ms": 0,
                        "message": f"Saved {len(final_state.get('clauses', []))} clauses + reports",
                    })
                    extra["reasoning_trace"] = trace
                    doc.extra_data = json.dumps(extra)
                    db.commit()

    except Exception as e:
        logger.error(f"❌ Orchestrator failed for doc {doc_id}: {e}")
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.status = DocumentStatus.FAILED
            extra = {}
            if doc.extra_data:
                try:
                    extra = json.loads(doc.extra_data) if isinstance(doc.extra_data, str) else doc.extra_data
                except:
                    pass
            extra["error"] = str(e)
            doc.extra_data = json.dumps(extra)
            db.commit()

@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("/{doc_id}/text", response_model=DocumentTextResponse)
async def get_document_text(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if doc.status != DocumentStatus.PARSED:
        raise HTTPException(400, "Document not yet parsed")
    if not doc.processed_text:
        raise HTTPException(400, "No text extracted")
    return {"document_id": doc_id, "text": doc.processed_text, "word_count": doc.word_count}


@router.get("/{doc_id}/clauses")
async def get_document_clauses(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if doc.status != DocumentStatus.PARSED:
        raise HTTPException(400, "Document not yet parsed")
    clauses = []
    if doc.extra_data:
        try:
            extra = json.loads(doc.extra_data) if isinstance(doc.extra_data, str) else doc.extra_data
            clauses = extra.get("clauses", [])
        except:
            pass
    return {"document_id": doc_id, "clauses": clauses, "total": len(clauses)}


@router.get("/")
async def list_documents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(Document)
    total = query.count()
    docs = query.offset(skip).limit(limit).all()
    return {
        "documents": [
            {
                "id": d.id,
                "filename": d.filename,
                "status": d.status,
                "progress": d.progress,
                "word_count": d.word_count,
                "created_at": d.created_at
            }
            for d in docs
        ],
        "total": total
    }


@router.delete("/{doc_id}")
async def delete_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    db.delete(doc)
    db.commit()
    return {"message": "Deleted"}


@router.get("/{doc_id}/risk-report")
async def get_risk_report(doc_id: int, refresh: bool = False, db: Session = Depends(get_db)):
    """
    Get risk report — returns cached version if available (unless refresh=true).
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if doc.status != DocumentStatus.PARSED:
        raise HTTPException(400, "Document not yet parsed")

    # Parse extra_data

    extra = parse_extra_data(doc.extra_data)
    # ── CACHE HIT (skip if cache seems incomplete) ──
    cached = extra.get("risk_report")
    if cached and not refresh:
        # If cache has fewer clauses than gemini_clauses, it's stale
        gemini_count = len(extra.get("gemini_clauses", []))
        cached_count = cached.get("total_clauses", 0)
        # Only trust cache if it used Gemini clauses (or no Gemini available)
        cache_is_valid = (gemini_count == 0 or cached_count == gemini_count)

        if cache_is_valid:
            logger.info(f"⚡ Returning CACHED risk report for doc {doc_id}")
            return {**cached, "document_id": doc_id, "filename": doc.filename}
        else:
            logger.info(f"🔄 Cache stale ({cached_count} vs {gemini_count} clauses), recomputing")

    # ── CACHE MISS or force refresh ──
    logger.info(f"🔨 Computing fresh risk report for doc {doc_id}")
    clauses = extra.get("gemini_clauses") or extra.get("clauses") or []
    if not clauses:
        raise HTTPException(400, "No clauses found in this document")

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
    risk_score = round((total_weight / max_possible) * 100) if max_possible else 0
    overall = "High" if risk_score >= 70 else ("Medium" if risk_score >= 40 else "Low")

    if breakdown["high"] > 0:
        summary = f"⚠️ High risk contract with {breakdown['high']} critical clauses requiring immediate attention."
    elif breakdown["medium"] > 0:
        summary = f"📊 Medium risk contract with {breakdown['medium']} moderate-risk clauses. Review suggested improvements."
    else:
        summary = f"✅ Low risk contract. All clauses appear standard and safe."

    sorted_clauses = sorted(enriched, key=lambda x: risk_weights.get(x["risk_level"], 0), reverse=True)
    report = {
        "document_id": doc_id,
        "filename": doc.filename,
        "overall_risk_score": risk_score,
        "risk_level": overall,
        "summary": summary,
        "breakdown": breakdown,
        "top_risks": sorted_clauses[:3],
        "clauses": enriched,
        "total_clauses": len(enriched),
    }

    # Save to cache
    extra["risk_report"] = report
    doc.extra_data = json.dumps(extra)
    db.commit()
    logger.info(f"💾 Cached risk report for doc {doc_id}")

    return report

@router.get("/{doc_id}/compliance")
async def get_compliance_report(doc_id: int, refresh: bool = False, db: Session = Depends(get_db)):
    """
    Get compliance report — returns cached version if available (unless refresh=true).
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if doc.status != DocumentStatus.PARSED:
        raise HTTPException(400, "Document not yet parsed")


    extra = parse_extra_data(doc.extra_data)
    # ── CACHE HIT (skip if cache contains failures) ──
    cached = extra.get("compliance_report")
    cache_is_valid = False
    if cached and not refresh:
        # Check if cache contains any failed results
        results = cached.get("compliance_results", [])
        has_failures = any(
            r.get("is_violation") is None and "not available" in str(r.get("explanation", "")).lower()
            for r in results
        )
        cache_is_valid = not has_failures

        if cache_is_valid:
            logger.info(f"⚡ Returning CACHED compliance report for doc {doc_id}")
            return {
                "document_id": doc_id,
                "filename": doc.filename,
                **cached,
            }
        else:
            logger.info(f"🔄 Cache invalid (contains failures), recomputing for doc {doc_id}")
    # ── CACHE MISS or force refresh ──
    logger.info(f"🔨 Computing fresh compliance for doc {doc_id}")
    clauses = extra.get("gemini_clauses") or extra.get("clauses") or []
    if not clauses:
        raise HTTPException(400, "No clauses found in this document")

    from app.agents.compliance_agent import ComplianceAgent
    agent = ComplianceAgent()

    results = []
    violations = 0
    for clause in clauses[:3]:
        ct = clause.get("type", "Unknown")
        ctext = clause.get("text", clause.get("snippet", ""))
        if ctext:
            r = agent.check_clause(ct, ctext)
            results.append(r)
            if r.get("is_violation") is True:
                violations += 1

    total = len(results)
    compliant = total - violations
    score = round((compliant / total) * 100) if total else 100

    compliance_data = {
        "compliance_score": score,
        "total_checks": total,
        "violations": violations,
        "compliance_results": results,
    }

    # Save to cache
    extra["compliance_report"] = compliance_data
    doc.extra_data = json.dumps(extra)
    db.commit()
    logger.info(f"💾 Cached compliance report for doc {doc_id}")

    return {
        "document_id": doc_id,
        "filename": doc.filename,
        **compliance_data,
    }

@router.get("/{doc_id}/report")
async def generate_report(doc_id: int, db: Session = Depends(get_db)):
    """
    Generate a comprehensive PDF report using cached risk/compliance data.
    """
    from fastapi.responses import FileResponse
    from app.agents.citation_agent import CitationAgent
    from app.agents.report_generator import ReportGenerator

    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if doc.status != DocumentStatus.PARSED:
        raise HTTPException(400, "Document not yet parsed")

    # Parse extra_data

    extra = parse_extra_data(doc.extra_data)

    clauses = extra.get("gemini_clauses") or extra.get("clauses") or []
    if not clauses:
        raise HTTPException(400, "No clauses found in this document")

    # ── 1. RISK REPORT (use cache or compute once) ──
    risk_report = extra.get("risk_report")
    if not risk_report:
        logger.info(f"🔨 Computing risk report for PDF (doc {doc_id})")
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

        if breakdown["high"] > 0:
            summary = f"⚠️ High risk contract with {breakdown['high']} critical clauses."
        elif breakdown["medium"] > 0:
            summary = f"📊 Medium risk contract with {breakdown['medium']} moderate-risk clauses."
        else:
            summary = f"✅ Low risk contract. All clauses appear standard and safe."

        risk_report = {
            "document_id": doc_id,
            "filename": doc.filename,
            "overall_risk_score": score,
            "risk_level": level,
            "summary": summary,
            "breakdown": breakdown,
            "clauses": enriched,
            "total_clauses": len(enriched),
            "top_risks": sorted(enriched, key=lambda x: risk_weights.get(x["risk_level"], 0), reverse=True)[:3],
        }
        extra["risk_report"] = risk_report
        doc.extra_data = json.dumps(extra)
        db.commit()
    else:
        logger.info(f"⚡ Using CACHED risk report for PDF (doc {doc_id})")

    # ── 2. COMPLIANCE REPORT (use cache or compute once) ──
    compliance_report = extra.get("compliance_report")
    if not compliance_report:
        logger.info(f"🔨 Computing compliance for PDF (doc {doc_id})")
        results = []
        violations = 0
        try:
            from app.agents.compliance_agent import ComplianceAgent
            agent = ComplianceAgent()
            for c in risk_report["clauses"][:3]:
                r = agent.check_clause(c["type"], c["text"])
                results.append(r)
                if r.get("is_violation") is True:
                    violations += 1
        except Exception as e:
            logger.error(f"Compliance check failed during PDF generation: {e}")

        total_checks = len(results)
        compliant = total_checks - violations
        comp_score = round((compliant / total_checks) * 100) if total_checks else 100

        compliance_report = {
            "compliance_score": comp_score,
            "total_checks": total_checks,
            "violations": violations,
            "compliance_results": results,
        }
        extra["compliance_report"] = compliance_report
        doc.extra_data = json.dumps(extra)
        db.commit()
    else:
        logger.info(f"⚡ Using CACHED compliance report for PDF (doc {doc_id})")

    # ── 3. CITATIONS (use cache or compute once) ──
    citations = extra.get("citations")
    if not citations:
        logger.info(f"🔨 Computing citations for PDF (doc {doc_id})")
        citation_agent = CitationAgent()
        citations = {}
        for c in risk_report["clauses"]:
            ct = c["type"]
            if ct not in citations:
                citations[ct] = citation_agent.find_citations(ct, c.get("text", ""))
        extra["citations"] = citations
        doc.extra_data = json.dumps(extra)
        db.commit()
    else:
        logger.info(f"⚡ Using CACHED citations for PDF (doc {doc_id})")

    # ── 4. GENERATE PDF ──
    doc_meta = {"id": doc.id, "filename": doc.filename}
    generator = ReportGenerator()
    pdf_path = generator.generate(doc_meta, risk_report, compliance_report, citations)

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"report_{doc.filename.replace('.pdf', '')}.pdf",
    )

@router.get("/{doc_id}/trace")
async def get_reasoning_trace(doc_id: int, db: Session = Depends(get_db)):
    """
    Returns the agent reasoning trace for a document.
    Shows each step: parse → clauses → (risk + compliance + citations) → save
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    extra = parse_extra_data(doc.extra_data)

    return {
        "document_id": doc_id,
        "filename": doc.filename,
        "status": doc.status,
        "reasoning_trace": extra.get("reasoning_trace", []),
    }
