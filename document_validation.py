"""Mock document-format validation for the intake / document-completeness agent.

Every required document type here is a real-world PDF (W-9, certificate of
insurance, business license, signed code of conduct, security questionnaire,
ACH form all normally are). Full OCR/layout parsing of an arbitrary PDF is out
of scope for this demo, so validation expects the PDF's extracted text to
contain simple ``Label: Value`` lines (case/spacing-insensitive on the label)
for each field the document type requires — see ``sample_documents/`` for one
valid example per type. A scanned image-only PDF, or one missing/garbling
those labeled lines, fails validation, same as a missing document.

``validate_document`` checks a submitted file against its type's schema; any
failure means the document doesn't satisfy its requirement, same as if it had
never been submitted (see ``graph.nodes.intake``).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from models import DocumentType

Validator = Callable[[str], "str | None"]  # returns an error message, or None if valid

_LABEL_LINE_RE = re.compile(r"^(?P<label>[A-Za-z][A-Za-z0-9 ]*):\s*(?P<value>.+)$")


def _normalize_label(label: str) -> str:
    return re.sub(r"\s+", "_", label.strip().lower())


def _non_empty(value: str) -> str | None:
    return None if value.strip() else "must not be empty"


def _date(value: str) -> str | None:
    try:
        date.fromisoformat(value.strip())
    except ValueError:
        return "must be a date in YYYY-MM-DD format"
    return None


def _future_date(value: str) -> str | None:
    error = _date(value)
    if error:
        return error
    if date.fromisoformat(value.strip()) < date.today():
        return "must not be in the past (document has expired)"
    return None


def _one_of(options: list[str]) -> Validator:
    allowed = {o.lower() for o in options}

    def _check(value: str) -> str | None:
        return None if value.strip().lower() in allowed else f"must be one of: {', '.join(options)}"

    return _check


def _regex(pattern: str, hint: str) -> Validator:
    compiled = re.compile(pattern)

    def _check(value: str) -> str | None:
        return None if compiled.match(value.strip()) else hint

    return _check


def _positive_number(value: str) -> str | None:
    try:
        ok = float(value) > 0
    except ValueError:
        return "must be a number"
    return None if ok else "must be greater than zero"


@dataclass(frozen=True)
class FieldSpec:
    label: str  # human-readable label as it appears in the PDF, e.g. "Legal Name"
    validator: Validator


@dataclass(frozen=True)
class DocumentSchema:
    fields: list[FieldSpec]


SCHEMAS: dict[DocumentType, DocumentSchema] = {
    DocumentType.W9_TAX_ID: DocumentSchema(
        fields=[
            FieldSpec("Legal Name", _non_empty),
            FieldSpec("TIN", _regex(r"^\d{2}-\d{7}$", "must look like 12-3456789")),
            FieldSpec(
                "Business Classification",
                _one_of(
                    [
                        "Individual/Sole Proprietor",
                        "C Corporation",
                        "S Corporation",
                        "Partnership",
                        "Trust/Estate",
                        "LLC",
                        "Other",
                    ]
                ),
            ),
            FieldSpec("Address", _non_empty),
            FieldSpec("Signature Date", _date),
        ]
    ),
    DocumentType.CERTIFICATE_OF_INSURANCE: DocumentSchema(
        fields=[
            FieldSpec("Insurer Name", _non_empty),
            FieldSpec("Policy Number", _non_empty),
            FieldSpec("Coverage Type", _non_empty),
            FieldSpec("Coverage Amount", _positive_number),
            FieldSpec("Expiration Date", _future_date),
        ]
    ),
    DocumentType.BUSINESS_LICENSE: DocumentSchema(
        fields=[
            FieldSpec("Business Name", _non_empty),
            FieldSpec("License Number", _non_empty),
            FieldSpec("Issuing Authority", _non_empty),
            FieldSpec("Issue Date", _date),
            FieldSpec("Expiration Date", _future_date),
        ]
    ),
    DocumentType.CODE_OF_CONDUCT: DocumentSchema(
        fields=[
            FieldSpec("Vendor Name", _non_empty),
            FieldSpec("Signatory Name", _non_empty),
            FieldSpec("Signatory Title", _non_empty),
            FieldSpec("Agreement Version", _one_of(["v1", "v2"])),
            FieldSpec("Signed Date", _date),
        ]
    ),
    DocumentType.SECURITY_QUESTIONNAIRE: DocumentSchema(
        fields=[
            FieldSpec("Vendor Name", _non_empty),
            FieldSpec("Data Encryption At Rest", _one_of(["yes", "no"])),
            FieldSpec("Data Encryption In Transit", _one_of(["yes", "no"])),
            FieldSpec("SOC2 Certified", _one_of(["yes", "no"])),
            FieldSpec("Incident Response Plan", _one_of(["yes", "no"])),
            FieldSpec("Completed Date", _date),
        ]
    ),
    DocumentType.BANKING_ACH_FORM: DocumentSchema(
        fields=[
            FieldSpec("Account Holder Name", _non_empty),
            FieldSpec("Bank Name", _non_empty),
            FieldSpec("Routing Number", _regex(r"^\d{9}$", "must be exactly 9 digits")),
            FieldSpec("Account Number Last4", _regex(r"^\d{4}$", "must be exactly 4 digits")),
            FieldSpec("Account Type", _one_of(["checking", "savings"])),
        ]
    ),
}


def _extract_fields(path: Path) -> dict[str, str]:
    """Parse ``Label: Value`` lines out of a PDF's extracted text."""
    reader = PdfReader(path)
    fields: dict[str, str] = {}
    for page in reader.pages:
        for line in (page.extract_text() or "").splitlines():
            match = _LABEL_LINE_RE.match(line.strip())
            if match:
                fields[_normalize_label(match.group("label"))] = match.group("value").strip()
    return fields


def validate_document(doc_type: DocumentType, path: str | Path) -> list[str]:
    """Validate a submitted PDF against its document type's mock schema.

    Returns a list of error messages; an empty list means the document is valid.
    """
    schema = SCHEMAS[doc_type]
    file_path = Path(path)
    if not file_path.is_file():
        return [f"file not found at {file_path}"]

    try:
        fields = _extract_fields(file_path)
    except PdfReadError:
        return ["could not be read as a PDF (is it the right file?)"]

    errors: list[str] = []
    for field in schema.fields:
        key = _normalize_label(field.label)
        value = fields.get(key)
        if value is None:
            errors.append(f"{field.label}: missing from document (expected a '{field.label}: ...' line)")
            continue
        error = field.validator(value)
        if error:
            errors.append(f"{field.label}: {error}")
    return errors
