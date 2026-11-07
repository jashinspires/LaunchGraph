"""
Unit tests for Stage 3 Deterministic Sensitivity Detectors.
"""

from services.decisioner.services.sensitivity_detector import SensitivityDetector


def test_sensitivity_security_cve():
    text = "Fixes CVE-2026-4412 remote code execution in webhook parser."
    findings = SensitivityDetector.scan_text(text)

    assert findings.security_flags is True
    assert "CVE-2026-4412" in findings.matched_patterns.get("SECURITY", [])
    assert findings.customer_nda_detected is False


def test_sensitivity_customer_nda():
    text = "Implements custom SLA retry routing for Customer: Acme-Enterprise [CONFIDENTIAL]."
    findings = SensitivityDetector.scan_text(text)

    assert findings.customer_nda_detected is True
    assert findings.security_flags is False


def test_sensitivity_compliance_soc2():
    text = "Adds audit log persistence to satisfy SOC 2 and HIPAA security requirements."
    findings = SensitivityDetector.scan_text(text)

    assert findings.compliance_flag is True
    assert any("SOC 2" in m or "SOC" in m for m in findings.matched_patterns.get("COMPLIANCE", []))


def test_sensitivity_pricing():
    text = "Updates stripe checkout for new subscription price and billing tier quotas."
    findings = SensitivityDetector.scan_text(text)

    assert findings.pricing_impact is True


def test_sensitivity_embargo_date():
    text = "Major announcement: EMBARGO UNTIL 2026-12-15 for press release."
    findings = SensitivityDetector.scan_text(text)

    assert findings.is_embargoed is True
    assert findings.embargo_date is not None
    assert findings.embargo_date.year == 2026
    assert findings.embargo_date.month == 12
    assert findings.embargo_date.day == 15


def test_sensitivity_clean_text():
    text = "Refactor logging helper to format timestamps as UTC."
    findings = SensitivityDetector.scan_text(text)

    assert findings.security_flags is False
    assert findings.customer_nda_detected is False
    assert findings.compliance_flag is False
    assert findings.pricing_impact is False
    assert findings.is_embargoed is False

