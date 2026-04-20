"""
Entity extraction pipeline — Phase 2 requirement.

Extracts structured entities: PAN, TAN, employer, amounts, sections, dates
from document text using pattern matching and NER.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional


class EntityType(str, Enum):
    """Types of entities we extract from tax documents."""
    PAN = "pan"
    TAN = "tan"
    AADHAAR = "aadhaar"
    EMPLOYER_NAME = "employer_name"
    EMPLOYEE_NAME = "employee_name"
    AMOUNT = "amount"
    DATE = "date"
    ASSESSMENT_YEAR = "assessment_year"
    FINANCIAL_YEAR = "financial_year"
    SECTION = "section"
    ACCOUNT_NUMBER = "account_number"
    IFSC = "ifsc"
    ADDRESS = "address"
    EMAIL = "email"
    PHONE = "phone"
    PERCENTAGE = "percentage"


@dataclass
class ExtractedEntity:
    """A single extracted entity with metadata."""
    entity_type: EntityType
    value: Any
    raw_text: str
    confidence: float  # 0.0 to 1.0
    source_page: Optional[int] = None
    source_region: Optional[tuple[int, int, int, int]] = None  # x1, y1, x2, y2
    context: Optional[str] = None  # Surrounding text for disambiguation
    validation_status: str = "unvalidated"  # unvalidated, valid, invalid


@dataclass
class ExtractionResult:
    """Result of entity extraction from a document."""
    document_id: str
    document_type: str
    entities: list[ExtractedEntity] = field(default_factory=list)
    extraction_time_ms: int = 0
    warnings: list[str] = field(default_factory=list)


class EntityExtractor:
    """
    Extracts structured entities from document text.
    
    Uses a combination of:
    1. Regex patterns for well-defined formats (PAN, TAN, dates)
    2. Context-aware extraction for amounts (looks for labels)
    3. Validation rules for each entity type
    """
    
    # PAN format: 5 letters + 4 digits + 1 letter
    PAN_PATTERN = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b')
    
    # TAN format: 4 letters + 5 digits + 1 letter
    TAN_PATTERN = re.compile(r'\b[A-Z]{4}[0-9]{5}[A-Z]\b')
    
    # Aadhaar: 12 digits (may have spaces)
    AADHAAR_PATTERN = re.compile(r'\b[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}\b')
    
    # Amount patterns (Indian format with lakhs/crores)
    AMOUNT_PATTERNS = [
        # ₹1,23,456.78 or Rs. 1,23,456.78
        re.compile(r'(?:₹|Rs\.?|INR)\s*([0-9,]+(?:\.[0-9]{1,2})?)', re.IGNORECASE),
        # Amounts with labels like "Gross Salary: 12,34,567"
        re.compile(r'([0-9]{1,2}(?:,[0-9]{2})*(?:,[0-9]{3})(?:\.[0-9]{1,2})?)\b'),
    ]
    
    # Date patterns
    DATE_PATTERNS = [
        # DD/MM/YYYY or DD-MM-YYYY
        (re.compile(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b'), '%d/%m/%Y'),
        # YYYY-MM-DD (ISO)
        (re.compile(r'\b(\d{4})-(\d{2})-(\d{2})\b'), '%Y-%m-%d'),
        # DD Mon YYYY (e.g., 15 Mar 2024)
        (re.compile(r'\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})\b', re.IGNORECASE), '%d %b %Y'),
    ]
    
    # Assessment Year pattern (e.g., AY 2024-25, A.Y. 2024-25)
    AY_PATTERN = re.compile(r'A\.?Y\.?\s*(\d{4})\s*[-–]\s*(\d{2,4})', re.IGNORECASE)
    
    # Financial Year pattern
    FY_PATTERN = re.compile(r'F\.?Y\.?\s*(\d{4})\s*[-–]\s*(\d{2,4})', re.IGNORECASE)
    
    # Section references (80C, 80D, 10(14), etc.)
    SECTION_PATTERN = re.compile(r'\b(?:Section|Sec\.?|u/s)\s*(\d+[A-Z]*(?:\([^)]+\))?)', re.IGNORECASE)
    
    # Bank account number (9-18 digits)
    ACCOUNT_PATTERN = re.compile(r'\b(\d{9,18})\b')
    
    # IFSC code (4 letters + 0 + 6 alphanumeric)
    IFSC_PATTERN = re.compile(r'\b([A-Z]{4}0[A-Z0-9]{6})\b')
    
    # Email
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    
    # Phone (Indian format)
    PHONE_PATTERN = re.compile(r'\b(?:\+91[-\s]?)?[6-9]\d{9}\b')
    
    # Amount labels we look for
    AMOUNT_LABELS = {
        'gross_salary': ['gross salary', 'gross total', 'total salary', 'salary as per'],
        'net_salary': ['net salary', 'net payable', 'take home'],
        'tds_deducted': ['tds deducted', 'tax deducted', 'tds u/s'],
        'hra': ['house rent allowance', 'hra', 'h.r.a'],
        'lta': ['leave travel', 'lta', 'l.t.a'],
        'pf_contribution': ['pf contribution', 'provident fund', 'epf'],
        'professional_tax': ['professional tax', 'profession tax', 'pt'],
        'standard_deduction': ['standard deduction'],
        'total_income': ['total income', 'gross total income'],
        'taxable_income': ['taxable income', 'net taxable'],
        'tax_payable': ['tax payable', 'tax liability', 'total tax'],
        'refund_due': ['refund', 'refund due', 'excess tax'],
    }
    
    def __init__(self):
        self._compile_amount_label_patterns()
    
    def _compile_amount_label_patterns(self):
        """Pre-compile patterns for amount label matching."""
        self._amount_label_patterns = {}
        for field_name, labels in self.AMOUNT_LABELS.items():
            pattern = '|'.join(re.escape(label) for label in labels)
            self._amount_label_patterns[field_name] = re.compile(
                f'({pattern})\\s*:?\\s*(?:₹|Rs\\.?|INR)?\\s*([0-9,]+(?:\\.[0-9]{{1,2}})?)',
                re.IGNORECASE
            )
    
    def extract_all(
        self,
        text: str,
        document_id: str,
        document_type: str,
        page_number: Optional[int] = None
    ) -> ExtractionResult:
        """Extract all entity types from document text."""
        import time
        start_time = time.time()
        
        result = ExtractionResult(
            document_id=document_id,
            document_type=document_type
        )
        
        # Extract each entity type
        result.entities.extend(self.extract_pan(text, page_number))
        result.entities.extend(self.extract_tan(text, page_number))
        result.entities.extend(self.extract_aadhaar(text, page_number))
        result.entities.extend(self.extract_dates(text, page_number))
        result.entities.extend(self.extract_assessment_year(text, page_number))
        result.entities.extend(self.extract_financial_year(text, page_number))
        result.entities.extend(self.extract_sections(text, page_number))
        result.entities.extend(self.extract_labeled_amounts(text, page_number))
        result.entities.extend(self.extract_ifsc(text, page_number))
        result.entities.extend(self.extract_email(text, page_number))
        result.entities.extend(self.extract_phone(text, page_number))
        
        # Validate entities
        for entity in result.entities:
            self._validate_entity(entity)
        
        self._check_for_warnings(result)
        result.extraction_time_ms = int((time.time() - start_time) * 1000)
        return result
    
    def extract_pan(self, text: str, page: Optional[int] = None) -> list[ExtractedEntity]:
        """Extract PAN numbers."""
        entities = []
        for match in self.PAN_PATTERN.finditer(text):
            pan = match.group()
            context = self._get_context(text, match.start(), match.end())
            entities.append(ExtractedEntity(
                entity_type=EntityType.PAN,
                value=pan,
                raw_text=pan,
                confidence=0.95,
                source_page=page,
                context=context
            ))
        return entities
    
    def extract_tan(self, text: str, page: Optional[int] = None) -> list[ExtractedEntity]:
        """Extract TAN numbers."""
        entities = []
        for match in self.TAN_PATTERN.finditer(text):
            tan = match.group()
            if self.PAN_PATTERN.match(tan):
                continue
            context = self._get_context(text, match.start(), match.end())
            entities.append(ExtractedEntity(
                entity_type=EntityType.TAN,
                value=tan,
                raw_text=tan,
                confidence=0.90,
                source_page=page,
                context=context
            ))
        return entities
    
    def extract_aadhaar(self, text: str, page: Optional[int] = None) -> list[ExtractedEntity]:
        """Extract Aadhaar numbers."""
        entities = []
        for match in self.AADHAAR_PATTERN.finditer(text):
            raw = match.group()
            aadhaar = raw.replace(' ', '')
            if len(aadhaar) == 12 and aadhaar.isdigit():
                context = self._get_context(text, match.start(), match.end())
                entities.append(ExtractedEntity(
                    entity_type=EntityType.AADHAAR,
                    value=aadhaar,
                    raw_text=raw,
                    confidence=0.85,
                    source_page=page,
                    context=context
                ))
        return entities
    
    def extract_dates(self, text: str, page: Optional[int] = None) -> list[ExtractedEntity]:
        """Extract dates in various formats."""
        entities = []
        for pattern, fmt in self.DATE_PATTERNS:
            for match in pattern.finditer(text):
                try:
                    raw = match.group()
                    if fmt == '%d/%m/%Y':
                        d, m, y = match.groups()
                        parsed_date = date(int(y), int(m), int(d))
                    elif fmt == '%Y-%m-%d':
                        y, m, d = match.groups()
                        parsed_date = date(int(y), int(m), int(d))
                    else:
                        parsed_date = datetime.strptime(raw, fmt).date()
                    
                    context = self._get_context(text, match.start(), match.end())
                    entities.append(ExtractedEntity(
                        entity_type=EntityType.DATE,
                        value=parsed_date.isoformat(),
                        raw_text=raw,
                        confidence=0.90,
                        source_page=page,
                        context=context
                    ))
                except (ValueError, IndexError):
                    continue
        return entities
    
    def extract_assessment_year(self, text: str, page: Optional[int] = None) -> list[ExtractedEntity]:
        """Extract Assessment Year references."""
        entities = []
        for match in self.AY_PATTERN.finditer(text):
            start_year = match.group(1)
            end_year = match.group(2)
            if len(end_year) == 2:
                end_year = start_year[:2] + end_year
            
            ay = f"{start_year}-{end_year[-2:]}"
            context = self._get_context(text, match.start(), match.end())
            entities.append(ExtractedEntity(
                entity_type=EntityType.ASSESSMENT_YEAR,
                value=ay,
                raw_text=match.group(),
                confidence=0.95,
                source_page=page,
                context=context
            ))
        return entities
    
    def extract_financial_year(self, text: str, page: Optional[int] = None) -> list[ExtractedEntity]:
        """Extract Financial Year references."""
        entities = []
        for match in self.FY_PATTERN.finditer(text):
            start_year = match.group(1)
            end_year = match.group(2)
            if len(end_year) == 2:
                end_year = start_year[:2] + end_year
            
            fy = f"{start_year}-{end_year[-2:]}"
            context = self._get_context(text, match.start(), match.end())
            entities.append(ExtractedEntity(
                entity_type=EntityType.FINANCIAL_YEAR,
                value=fy,
                raw_text=match.group(),
                confidence=0.95,
                source_page=page,
                context=context
            ))
        return entities
    
    def extract_sections(self, text: str, page: Optional[int] = None) -> list[ExtractedEntity]:
        """Extract Income Tax Act section references."""
        entities = []
        for match in self.SECTION_PATTERN.finditer(text):
            section = match.group(1).upper()
            context = self._get_context(text, match.start(), match.end())
            entities.append(ExtractedEntity(
                entity_type=EntityType.SECTION,
                value=section,
                raw_text=match.group(),
                confidence=0.90,
                source_page=page,
                context=context
            ))
        return entities
    
    def extract_labeled_amounts(self, text: str, page: Optional[int] = None) -> list[ExtractedEntity]:
        """Extract amounts that have recognizable labels."""
        entities = []
        for field_name, pattern in self._amount_label_patterns.items():
            for match in pattern.finditer(text):
                amount_str = match.group(2).replace(',', '')
                try:
                    amount = Decimal(amount_str)
                    context = self._get_context(text, match.start(), match.end())
                    entities.append(ExtractedEntity(
                        entity_type=EntityType.AMOUNT,
                        value={
                            "amount": float(amount),
                            "field": field_name,
                            "currency": "INR"
                        },
                        raw_text=match.group(),
                        confidence=0.85,
                        source_page=page,
                        context=context
                    ))
                except (ValueError, ArithmeticError):
                    continue
        return entities
    
    def extract_ifsc(self, text: str, page: Optional[int] = None) -> list[ExtractedEntity]:
        """Extract IFSC codes."""
        entities = []
        for match in self.IFSC_PATTERN.finditer(text):
            ifsc = match.group(1)
            context = self._get_context(text, match.start(), match.end())
            entities.append(ExtractedEntity(
                entity_type=EntityType.IFSC,
                value=ifsc,
                raw_text=ifsc,
                confidence=0.95,
                source_page=page,
                context=context
            ))
        return entities
    
    def extract_email(self, text: str, page: Optional[int] = None) -> list[ExtractedEntity]:
        """Extract email addresses."""
        entities = []
        for match in self.EMAIL_PATTERN.finditer(text):
            email = match.group()
            context = self._get_context(text, match.start(), match.end())
            entities.append(ExtractedEntity(
                entity_type=EntityType.EMAIL,
                value=email.lower(),
                raw_text=email,
                confidence=0.95,
                source_page=page,
                context=context
            ))
        return entities
    
    def extract_phone(self, text: str, page: Optional[int] = None) -> list[ExtractedEntity]:
        """Extract phone numbers."""
        entities = []
        for match in self.PHONE_PATTERN.finditer(text):
            phone = re.sub(r'[\s-]', '', match.group())
            if phone.startswith('+91'):
                phone = phone[3:]
            context = self._get_context(text, match.start(), match.end())
            entities.append(ExtractedEntity(
                entity_type=EntityType.PHONE,
                value=phone,
                raw_text=match.group(),
                confidence=0.90,
                source_page=page,
                context=context
            ))
        return entities
    
    def _get_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """Get surrounding context for an extracted entity."""
        ctx_start = max(0, start - window)
        ctx_end = min(len(text), end + window)
        return text[ctx_start:ctx_end].strip()
    
    def _validate_entity(self, entity: ExtractedEntity) -> None:
        """Validate an extracted entity and update its status."""
        if entity.entity_type == EntityType.PAN:
            pan = entity.value
            valid_4th_chars = 'PCHATBLJFG'
            if len(pan) == 10 and pan[3] in valid_4th_chars:
                entity.validation_status = "valid"
            else:
                entity.validation_status = "invalid"
        elif entity.entity_type == EntityType.TAN:
            entity.validation_status = "valid" if len(entity.value) == 10 else "invalid"
        elif entity.entity_type == EntityType.AADHAAR:
            val = entity.value
            if len(val) == 12 and val.isdigit() and len(set(val)) > 1:
                entity.validation_status = "valid"
            else:
                entity.validation_status = "invalid"
        elif entity.entity_type == EntityType.IFSC:
            ifsc = entity.value
            if len(ifsc) == 11 and ifsc[4] == '0':
                entity.validation_status = "valid"
            else:
                entity.validation_status = "invalid"
        else:
            entity.validation_status = "valid"
    
    def _check_for_warnings(self, result: ExtractionResult) -> None:
        """Add warnings for potential extraction issues."""
        pans = [e for e in result.entities if e.entity_type == EntityType.PAN]
        if len(pans) > 2:
            result.warnings.append(f"Multiple PAN numbers found ({len(pans)})")
        
        invalid = [e for e in result.entities if e.validation_status == "invalid"]
        if invalid:
            result.warnings.append(f"{len(invalid)} entities failed validation")
        
        if result.document_type == "form16":
            if not any(e.entity_type == EntityType.TAN for e in result.entities):
                result.warnings.append("No employer TAN found in Form 16")
            if not any(e.entity_type == EntityType.PAN for e in result.entities):
                result.warnings.append("No PAN found in Form 16")


def run(payload: dict) -> dict:
    """Pipeline entry point for entity extraction."""
    text = payload.get("text", "")
    document_id = payload.get("document_id", "unknown")
    document_type = payload.get("document_type", "unknown")
    
    extractor = EntityExtractor()
    result = extractor.extract_all(text, document_id, document_type)
    
    return {
        **payload,
        "stage": "entities",
        "entities": [
            {
                "type": e.entity_type.value,
                "value": e.value,
                "raw_text": e.raw_text,
                "confidence": e.confidence,
                "validation_status": e.validation_status,
                "context": e.context
            }
            for e in result.entities
        ],
        "extraction_warnings": result.warnings,
        "extraction_time_ms": result.extraction_time_ms
    }


def extract_entities(text: str, document_id: str, document_type: str) -> ExtractionResult:
    """Convenience function for direct extraction."""
    extractor = EntityExtractor()
    return extractor.extract_all(text, document_id, document_type)
