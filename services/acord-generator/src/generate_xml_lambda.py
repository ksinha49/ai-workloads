# ------------------------------------------------------------------------------
# generate_xml_lambda.py
# ------------------------------------------------------------------------------
"""Generate ACORD 103 XML from extracted data.

The Lambda expects a JSON payload with two top level keys:
``fields``
    Mapping of field names to values extracted from the document.
``signatures``
    Mapping of signature roles to the signer name or timestamp.

The handler returns a simple ACORD 103 document in XML form.
"""

from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, tostring


def generate_acord_xml(data: dict) -> str:
    """Convert field data into an ACORD 103 ``InsuranceSvcRq``.

    Parameters
    ----------
    data:
        Dictionary containing ``fields`` and ``signatures`` mappings.

    Returns
    -------
    str
        The generated XML string.
    """

    fields = data.get("fields") or {}
    signatures = data.get("signatures") or {}

    root = Element("ACORD")
    rq = SubElement(root, "InsuranceSvcRq")

    for key, value in fields.items():
        child = SubElement(rq, key)
        child.text = str(value)

    if signatures:
        sig_el = SubElement(rq, "Signatures")
        for role, value in signatures.items():
            sub = SubElement(sig_el, role)
            sub.text = str(value)

    return tostring(root, encoding="unicode")


def lambda_handler(event, context):  # pragma: no cover - thin wrapper
    """AWS Lambda entry point."""
    xml = generate_acord_xml(event)
    return {"statusCode": 200, "body": xml}
