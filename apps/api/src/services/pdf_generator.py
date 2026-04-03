"""PDF generator — converts optimized resume JSON to a formatted PDF.

Replicates the layout of the original resume:
  - Large bold name header
  - Contact info line (phone | email | location | linkedin)
  - Section headers with horizontal rule
  - Work experience with company/location, title/dates, bullet points
  - Education with school/dates, degree/field
  - Skills as comma-separated list
"""

from __future__ import annotations

import io
import logging
from typing import Any

from fpdf import FPDF

logger = logging.getLogger(__name__)


def _sanitize_text(text: str) -> str:
    """Replace characters unsupported by Helvetica (latin-1) with safe alternatives."""
    replacements = {
        "\u2022": "-",   # bullet
        "\u2013": "-",   # en-dash
        "\u2014": "--",  # em-dash
        "\u2018": "'",   # left single quote
        "\u2019": "'",   # right single quote
        "\u201c": '"',   # left double quote
        "\u201d": '"',   # right double quote
        "\u2026": "...", # ellipsis
        "\u00a0": " ",   # non-breaking space
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    # Drop any remaining non-latin-1 characters
    return text.encode("latin-1", errors="replace").decode("latin-1")

# ── Layout constants ─────────────────────────────────────────────────────────

PAGE_W = 210  # A4 width mm (but we use Letter below)
MARGIN_LEFT = 15
MARGIN_RIGHT = 15
CONTENT_W = 180  # 210 - 15 - 15

# Font sizes
NAME_SIZE = 22
CONTACT_SIZE = 9
SECTION_HEADER_SIZE = 11
BODY_SIZE = 9.5
COMPANY_SIZE = 10
TITLE_SIZE = 9.5
BULLET_SIZE = 9.5

# Spacing
SECTION_GAP = 4  # mm before section header
LINE_HEIGHT = 4.2  # mm for body text


class ResumePDF(FPDF):
    """Custom FPDF subclass for resume generation."""

    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="Letter")
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(MARGIN_LEFT, 12, MARGIN_RIGHT)
        # Add built-in fonts (no TTF needed)
        # fpdf2 includes Helvetica by default
        self.add_page()

    # ── Helpers ──────────────────────────────────────────────────────────

    def _section_header(self, title: str) -> None:
        """Render a section header with underline rule."""
        self.ln(SECTION_GAP)
        self.set_font("Helvetica", "B", SECTION_HEADER_SIZE)
        y_before = self.get_y()
        self.cell(w=0, h=6, text=_sanitize_text(title.upper()), new_x="LMARGIN", new_y="NEXT")
        # Draw horizontal line
        y_after = self.get_y()
        self.set_draw_color(0, 0, 0)
        self.set_line_width(0.4)
        self.line(MARGIN_LEFT, y_after, MARGIN_LEFT + CONTENT_W, y_after)
        self.ln(1.5)

    def _body_text(self, text: str) -> None:
        """Render body paragraph text."""
        self.set_font("Helvetica", "", BODY_SIZE)
        self.multi_cell(w=0, h=LINE_HEIGHT, text=_sanitize_text(text))

    def _bullet_point(self, text: str) -> None:
        """Render a bullet point with hanging indent."""
        bullet_indent = 5
        text_indent = 9
        self.set_font("Helvetica", "", BULLET_SIZE)
        x = self.get_x()

        # Bullet character (use hyphen — safe for latin-1)
        self.set_x(MARGIN_LEFT + bullet_indent)
        self.cell(w=text_indent - bullet_indent, h=LINE_HEIGHT, text="-")

        # Text with hanging indent
        self.set_x(MARGIN_LEFT + text_indent)
        self.multi_cell(
            w=CONTENT_W - text_indent,
            h=LINE_HEIGHT,
            text=_sanitize_text(text.strip()),
        )

    def _two_column_row(
        self,
        left: str,
        right: str,
        left_style: str = "B",
        left_size: float = COMPANY_SIZE,
        right_style: str = "",
        right_size: float = BODY_SIZE,
    ) -> None:
        """Render a row with left-aligned and right-aligned text on same line."""
        left = _sanitize_text(left)
        right = _sanitize_text(right)
        y = self.get_y()

        # Right side first (to measure)
        self.set_font("Helvetica", right_style, right_size)
        right_w = self.get_string_width(right) + 2

        # Left side
        self.set_font("Helvetica", left_style, left_size)
        self.set_xy(MARGIN_LEFT, y)
        self.cell(w=CONTENT_W - right_w, h=5, text=left)

        # Right side
        self.set_font("Helvetica", right_style, right_size)
        self.set_xy(MARGIN_LEFT + CONTENT_W - right_w, y)
        self.cell(w=right_w, h=5, text=right, align="R")

        self.set_xy(MARGIN_LEFT, y + 5)


def _format_date_range(from_date: dict | None, to_date: dict | None, currently_here: bool = False) -> str:
    """Format date range like '01/2019 - Present'."""
    def fmt(d: dict | None) -> str:
        if not d:
            return ""
        month = d.get("month", "")
        year = d.get("year", "")
        if month and year:
            return f"{month}/{year}"
        return year or ""

    start = fmt(from_date)
    if currently_here or not to_date or (not to_date.get("month") and not to_date.get("year")):
        end = "Present"
    else:
        end = fmt(to_date)

    if start and end:
        return f"{start} - {end}"
    return start or end or ""


def generate_resume_pdf(resume_json: dict[str, Any]) -> bytes:
    """Generate a PDF from an optimized resume JSON dict.

    Parameters
    ----------
    resume_json : dict
        Optimized resume JSON (same schema as base resume components,
        plus optional jd_alignment_notes and _optimised_for keys).

    Returns
    -------
    bytes
        PDF file content.
    """
    pdf = ResumePDF()

    # ── Header: Name ─────────────────────────────────────────────────────
    personal = resume_json.get("personal_info", {})
    full_name = personal.get("full_name", "")
    if not full_name:
        first = personal.get("first_name", "")
        last = personal.get("last_name", "")
        full_name = f"{first} {last}".strip()

    if full_name:
        pdf.set_font("Helvetica", "B", NAME_SIZE)
        pdf.cell(w=0, h=10, text=_sanitize_text(full_name.upper()), new_x="LMARGIN", new_y="NEXT")

    # ── Contact line ─────────────────────────────────────────────────────
    contact_parts = []
    if personal.get("phone"):
        contact_parts.append(personal["phone"])
    if personal.get("email"):
        contact_parts.append(personal["email"])
    if personal.get("location"):
        contact_parts.append(personal["location"])
    if personal.get("linkedin"):
        contact_parts.append(personal["linkedin"])

    if contact_parts:
        pdf.set_font("Helvetica", "", CONTACT_SIZE)
        pdf.cell(w=0, h=4, text=_sanitize_text(" | ".join(contact_parts)), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    # ── Professional Summary ──────────────────────────────────────────────
    summary = resume_json.get("professional_summary", "")
    if summary:
        pdf._section_header("Professional Summary")
        pdf._body_text(summary)

    # ── Accomplishments ──────────────────────────────────────────────────
    accomplishments = resume_json.get("accomplishments", [])
    if accomplishments:
        pdf._section_header("Accomplishments")
        for acc in accomplishments:
            company = acc.get("company", "")
            acc_type = acc.get("type", "")
            desc = acc.get("description", "")
            prefix = f"{company} ({acc_type}): " if company else ""
            pdf._bullet_point(f"{prefix}{desc}")

    # ── Professional Experience ──────────────────────────────────────────
    experience = resume_json.get("work_experience", [])
    if experience:
        pdf._section_header("Professional Experience")

        for i, exp in enumerate(experience):
            if i > 0:
                pdf.ln(2)

            company = exp.get("company", "")
            location = exp.get("location", "")
            title = exp.get("job_title", "")
            currently = exp.get("currently_work_here", False)
            date_range = _format_date_range(
                exp.get("from"), exp.get("to"), currently
            )

            # Company + Location
            pdf._two_column_row(company, location, left_style="B", left_size=COMPANY_SIZE)

            # Title + Dates (italic)
            pdf._two_column_row(
                title, date_range,
                left_style="I", left_size=TITLE_SIZE,
                right_style="I", right_size=TITLE_SIZE,
            )

            # Bullet points
            role_desc = exp.get("role_description", "")
            if role_desc:
                bullets = [b.strip().lstrip("\u2022").lstrip("- ").strip()
                           for b in role_desc.split("\n") if b.strip()]
                for bullet in bullets:
                    pdf._bullet_point(bullet)

    # ── Education ────────────────────────────────────────────────────────
    education = resume_json.get("education", [])
    if education:
        pdf._section_header("Education")

        for i, edu in enumerate(education):
            if i > 0:
                pdf.ln(1.5)

            school = edu.get("school_or_university", "")
            date_range = _format_date_range(edu.get("from"), edu.get("to"))
            degree = edu.get("degree", "")
            field = edu.get("field_of_study", "")

            # School + Dates
            pdf._two_column_row(school, date_range, left_style="B", left_size=COMPANY_SIZE)

            # Degree + Field (italic)
            degree_text = f"{degree}, {field}" if degree and field else degree or field
            if degree_text:
                pdf.set_font("Helvetica", "I", TITLE_SIZE)
                pdf.cell(w=0, h=LINE_HEIGHT, text=_sanitize_text(degree_text), new_x="LMARGIN", new_y="NEXT")

    # ── Skills ───────────────────────────────────────────────────────────
    skills = resume_json.get("skills", [])
    if skills:
        pdf._section_header("Skills")
        pdf.set_font("Helvetica", "", BODY_SIZE)
        # "Skills:" prefix in bold
        pdf.set_font("Helvetica", "B", BODY_SIZE)
        pdf.write(LINE_HEIGHT, "Skills: ")
        pdf.set_font("Helvetica", "", BODY_SIZE)
        pdf.write(LINE_HEIGHT, _sanitize_text(", ".join(skills)))
        pdf.ln()

    # ── Output ───────────────────────────────────────────────────────────
    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
