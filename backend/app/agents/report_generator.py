import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates a professional PDF report for a legal document analysis."""

    def __init__(self, output_dir: str = "/app/data/reports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._register_custom_styles()

    def _register_custom_styles(self):
        """Add custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name="CustomTitle",
            parent=self.styles["Title"],
            fontSize=22,
            textColor=colors.HexColor("#1a365d"),
            spaceAfter=6,
            alignment=TA_CENTER,
        ))
        self.styles.add(ParagraphStyle(
            name="SectionHeader",
            parent=self.styles["Heading1"],
            fontSize=15,
            textColor=colors.HexColor("#1a365d"),
            spaceBefore=16,
            spaceAfter=8,
            borderPadding=4,
        ))
        self.styles.add(ParagraphStyle(
            name="SubHeader",
            parent=self.styles["Heading2"],
            fontSize=12,
            textColor=colors.HexColor("#2d3748"),
            spaceBefore=10,
            spaceAfter=4,
        ))
        self.styles.add(ParagraphStyle(
            name="BodyText2",
            parent=self.styles["BodyText"],
            fontSize=10,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            name="SmallText",
            parent=self.styles["BodyText"],
            fontSize=9,
            textColor=colors.HexColor("#4a5568"),
            leading=12,
        ))

    def generate(self, document: Dict[str, Any], risk_report: Dict[str, Any],
                 compliance_report: Dict[str, Any], citations: Dict[str, List[Dict]]) -> str:
        """
        Generate a PDF report and return the file path.

        Args:
            document: Document metadata (filename, id, etc.)
            risk_report: Output from the risk-report endpoint
            compliance_report: Output from the compliance endpoint
            citations: Dict mapping clause_type -> list of case citations

        Returns:
            Absolute path to the generated PDF file
        """
        doc_id = document.get("id", "unknown")
        filename = document.get("filename", "document")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"report_doc{doc_id}_{timestamp}.pdf"
        pdf_path = os.path.join(self.output_dir, pdf_filename)

        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=A4,
            topMargin=0.6 * inch,
            bottomMargin=0.6 * inch,
            leftMargin=0.7 * inch,
            rightMargin=0.7 * inch,
        )

        story = []

        # --- Title ---
        story.append(Paragraph("Legal Contract Analysis Report", self.styles["CustomTitle"]))
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1a365d")))
        story.append(Spacer(1, 12))

        # --- Metadata Table ---
        meta_data = [
            ["Document Name:", filename],
            ["Document ID:", str(doc_id)],
            ["Report Generated:", datetime.now().strftime("%B %d, %Y at %H:%M")],
            ["Analysis Engine:", "Gemini 3.6 Flash + LangChain RAG"],
        ]
        meta_table = Table(meta_data, colWidths=[1.8 * inch, 5 * inch])
        meta_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#2d3748")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 16))

        # --- Executive Summary ---
        story.append(Paragraph("📊 Executive Summary", self.styles["SectionHeader"]))

        risk_score = risk_report.get("overall_risk_score", 0)
        risk_level = risk_report.get("risk_level", "Unknown")
        compliance_score = compliance_report.get("compliance_score", 0)
        total_clauses = risk_report.get("total_clauses", 0)

        # Risk color
        if risk_level == "High":
            risk_color = colors.HexColor("#c53030")
        elif risk_level == "Medium":
            risk_color = colors.HexColor("#d69e2e")
        else:
            risk_color = colors.HexColor("#38a169")

        summary_data = [
            ["Risk Score", f"{risk_score} / 100"],
            ["Risk Level", risk_level],
            ["Compliance Score", f"{compliance_score}%"],
            ["Total Clauses Analyzed", str(total_clauses)],
        ]
        summary_table = Table(summary_data, colWidths=[2.5 * inch, 4.3 * inch])
        summary_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf2f7")),
            ("TEXTCOLOR", (1, 1), (1, 1), risk_color),
            ("FONTNAME", (1, 1), (1, 1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
            ("PADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 10))

        if risk_report.get("summary"):
            story.append(Paragraph("<b>Analysis:</b>", self.styles["SubHeader"]))
            story.append(Paragraph(risk_report["summary"], self.styles["BodyText2"]))

        story.append(Spacer(1, 16))

        # --- Clause Analysis ---
        story.append(Paragraph("⚠️ Clause Analysis", self.styles["SectionHeader"]))

        clauses = risk_report.get("clauses", [])
        if not clauses:
            story.append(Paragraph("No clauses were extracted from this document.", self.styles["BodyText2"]))
        else:
            for i, clause in enumerate(clauses, 1):
                story.append(Paragraph(
                    f"<b>{i}. {clause.get('type', 'Unknown')}</b> "
                    f"<font color='#718096'>[{clause.get('risk_level', 'N/A')}]</font>",
                    self.styles["SubHeader"]
                ))
                story.append(Paragraph(
                    f"<i>\"{clause.get('text', '')[:250]}\"</i>",
                    self.styles["SmallText"]
                ))
                story.append(Spacer(1, 4))
                if clause.get("summary"):
                    story.append(Paragraph(
                        f"<b>Summary:</b> {clause['summary']}",
                        self.styles["BodyText2"]
                    ))
                if clause.get("suggestion"):
                    story.append(Paragraph(
                        f"<b>💡 Suggestion:</b> {clause['suggestion']}",
                        self.styles["BodyText2"]
                    ))
                story.append(Spacer(1, 10))

        story.append(PageBreak())

        # --- Compliance Results ---
        story.append(Paragraph("⚖️ Compliance Results", self.styles["SectionHeader"]))

        comp_results = compliance_report.get("compliance_results", [])
        if not comp_results:
            story.append(Paragraph("No compliance checks were performed.", self.styles["BodyText2"]))
        else:
            for r in comp_results:
                status = "✅ Compliant"
                color = "#38a169"
                if r.get("is_violation") is True:
                    status = "❌ Violation"
                    color = "#c53030"
                elif r.get("is_violation") is None:
                    status = "⚠️ Unverified"
                    color = "#d69e2e"

                story.append(Paragraph(
                    f"<b>{r.get('clause_type', 'Unknown')}</b> — "
                    f"<font color='{color}'>{status}</font>",
                    self.styles["SubHeader"]
                ))
                if r.get("relevant_law"):
                    story.append(Paragraph(
                        f"<b>Relevant Law:</b> {r['relevant_law']}",
                        self.styles["BodyText2"]
                    ))
                if r.get("explanation"):
                    story.append(Paragraph(
                        f"<b>Explanation:</b> {r['explanation']}",
                        self.styles["BodyText2"]
                    ))
                story.append(Spacer(1, 10))

        story.append(Spacer(1, 16))

        # --- Case Laws ---
        story.append(Paragraph("📚 Relevant Case Laws", self.styles["SectionHeader"]))

        has_citations = False
        for clause_type, cases in citations.items():
            if cases:
                has_citations = True
                story.append(Paragraph(f"<b>{clause_type}</b>", self.styles["SubHeader"]))
                for case in cases:
                    story.append(Paragraph(
                        f"• <b>{case['case_name']}</b> — {case['court']} ({case['year']})",
                        self.styles["BodyText2"]
                    ))
                    story.append(Paragraph(
                        f"<i>Citation: {case['citation']}</i>",
                        self.styles["SmallText"]
                    ))
                    story.append(Paragraph(
                        f"{case['summary']}",
                        self.styles["SmallText"]
                    ))
                    story.append(Spacer(1, 6))

        if not has_citations:
            story.append(Paragraph("No case law citations available.", self.styles["BodyText2"]))

        story.append(Spacer(1, 20))

        # --- Footer ---
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e0")))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "This report was generated by an AI-powered legal analysis system. "
            "It is intended for informational purposes only and does not constitute legal advice. "
            "Please consult a qualified attorney for professional legal guidance.",
            self.styles["SmallText"]
        ))

        # --- Build PDF ---
        doc.build(story)
        logger.info(f"✅ PDF report generated: {pdf_path}")
        return pdf_path
