"""
Deterministic Sensitivity Detectors for Stage 3 Decisioning.
Detects Security/CVE vulnerabilities, Customer NDA references, Compliance standards,
Pricing shifts, and Embargo windows with zero probabilistic hallucinations.
"""

import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone


@dataclass
class SensitivityFindings:
    security_flags: bool = False
    customer_nda_detected: bool = False
    compliance_flag: bool = False
    pricing_impact: bool = False
    is_embargoed: bool = False
    embargo_date: Optional[datetime] = None
    matched_patterns: Dict[str, List[str]] = field(default_factory=dict)
    summary_findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.embargo_date:
            d["embargo_date"] = self.embargo_date.isoformat()
        return d


class SensitivityDetector:
    """
    Compiled regex detectors matching critical security, legal, pricing, and compliance boundaries.
    """

    # Security & CVE Patterns
    CVE_PATTERN = re.compile(r"\b(CVE-\d{4}-\d{4,7})\b", re.IGNORECASE)
    SECURITY_KEYWORDS = re.compile(
        r"\b(vulnerability|auth(?:entication)? bypass|remote code execution|RCE|SQL injection|SQLi|"
        r"cross-site scripting|XSS|zero-day|exploit|buffer overflow|privilege escalation|"
        r"security advisory|patch vulnerability)\b",
        re.IGNORECASE
    )

    # Customer NDA / Confidential Patterns
    CUSTOMER_NDA_PATTERNS = re.compile(
        r"(\[CONFIDENTIAL\]|\bNDA\b|Customer:\s*[A-Z0-9_\-\.]+|acme-corp|enterprise customer|"
        r"confidential customer|custom SLA|client-specific endpoint)",
        re.IGNORECASE
    )

    # Compliance & Regulatory
    COMPLIANCE_PATTERNS = re.compile(
        r"\b(SOC\s*2|HIPAA|GDPR|PCI-?DSS|ISO\s*27001|FedRAMP|compliance audit|"
        r"regulatory requirement|audit log retention)\b",
        re.IGNORECASE
    )

    # Pricing & Monetization
    PRICING_PATTERNS = re.compile(
        r"\b(pricing plan|billing tier|subscription price|paywall|monetization|"
        r"seat license|credit quota|usage limit cost|stripe checkout|price increase|discount tier)\b",
        re.IGNORECASE
    )

    # Embargo Patterns
    EMBARGO_PATTERNS = re.compile(
        r"\b(EMBARGO(?:ED)?|embargo until|confidential until|hold publication until)\b",
        re.IGNORECASE
    )

    # Simple date pattern for embargo (e.g. 2026-12-01)
    DATE_PATTERN = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")

    @classmethod
    def scan_text(cls, text: str) -> SensitivityFindings:
        findings = SensitivityFindings()
        matched: Dict[str, List[str]] = {}

        if not text:
            return findings

        # 1. Security scan
        cve_matches = cls.CVE_PATTERN.findall(text)
        sec_matches = cls.SECURITY_KEYWORDS.findall(text)
        if cve_matches or sec_matches:
            findings.security_flags = True
            sec_all = list(set(cve_matches + sec_matches))
            matched["SECURITY"] = sec_all
            findings.summary_findings.append(f"Security sensitivity detected: {', '.join(sec_all[:5])}")

        # 2. Customer NDA scan
        nda_matches = cls.CUSTOMER_NDA_PATTERNS.findall(text)
        if nda_matches:
            findings.customer_nda_detected = True
            nda_unique = list(set(nda_matches))
            matched["CUSTOMER_NDA"] = nda_unique
            findings.summary_findings.append(f"Customer NDA / confidentiality pattern detected: {', '.join(nda_unique[:3])}")

        # 3. Compliance scan
        comp_matches = cls.COMPLIANCE_PATTERNS.findall(text)
        if comp_matches:
            findings.compliance_flag = True
            comp_unique = list(set(comp_matches))
            matched["COMPLIANCE"] = comp_unique
            findings.summary_findings.append(f"Regulatory compliance standard referenced: {', '.join(comp_unique[:3])}")

        # 4. Pricing scan
        price_matches = cls.PRICING_PATTERNS.findall(text)
        if price_matches:
            findings.pricing_impact = True
            price_unique = list(set(price_matches))
            matched["PRICING"] = price_unique
            findings.summary_findings.append(f"Pricing or monetization modification referenced: {', '.join(price_unique[:3])}")

        # 5. Embargo scan
        embargo_matches = cls.EMBARGO_PATTERNS.findall(text)
        if embargo_matches:
            findings.is_embargoed = True
            date_matches = cls.DATE_PATTERN.findall(text)
            if date_matches:
                try:
                    dt = datetime.strptime(date_matches[0], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    findings.embargo_date = dt
                except Exception:
                    pass
            matched["EMBARGO"] = embargo_matches
            findings.summary_findings.append(
                f"Marketing embargo detected (Hold date: {findings.embargo_date.strftime('%Y-%m-%d') if findings.embargo_date else 'Unspecified'})"
            )

        findings.matched_patterns = matched
        return findings

    @classmethod
    def scan_change_context(
        cls,
        title: str,
        description: Optional[str] = None,
        source_texts: Optional[List[str]] = None
    ) -> SensitivityFindings:
        combined_parts = [title]
        if description:
            combined_parts.append(description)
        if source_texts:
            combined_parts.extend(source_texts)

        return cls.scan_text("\n\n".join(combined_parts))

