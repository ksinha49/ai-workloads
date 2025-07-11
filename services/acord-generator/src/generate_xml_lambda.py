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
import os
import base64
import io

try:  # optional dependencies used for signature checks
    import httpx
    from httpx import HTTPError
except Exception:  # pragma: no cover - allow import without httpx
    httpx = None  # type: ignore
    class HTTPError(Exception):
        pass

try:
    from PIL import Image
except Exception:  # pragma: no cover - allow import without pillow
    Image = None  # type: ignore

SIGNATURE_MODEL_ENDPOINT = os.environ.get("SIGNATURE_MODEL_ENDPOINT")
SIGNATURE_THRESHOLD = float(os.environ.get("SIGNATURE_THRESHOLD", "0.2"))


def verify_signature(img: bytes | str) -> bool:
    """Return ``True`` when the signature image appears valid.

    The helper sends the image to ``SIGNATURE_MODEL_ENDPOINT`` when defined.
    Otherwise it applies a simple heuristic based on the ratio of dark pixels.
    The result is compared against ``SIGNATURE_THRESHOLD``.

    Parameters
    ----------
    img:
        Raw bytes or base64 encoded string of the signature image.

    Returns
    -------
    bool
        ``True`` when the verification score exceeds ``SIGNATURE_THRESHOLD``.
    """

    if isinstance(img, str):
        img_bytes = base64.b64decode(img)
    else:
        img_bytes = img

    score = 0.0
    if SIGNATURE_MODEL_ENDPOINT and httpx:
        try:
            resp = httpx.post(
                SIGNATURE_MODEL_ENDPOINT,
                files={"file": ("signature.png", img_bytes, "image/png")},
            )
            resp.raise_for_status()
            score = float(resp.json().get("score", 0.0))
        except HTTPError:
            score = 0.0
    else:
        if not Image:  # pragma: no cover - pillow unavailable
            return False
        with Image.open(io.BytesIO(img_bytes)) as im:
            hist = im.convert("L").histogram()
        dark = sum(hist[:100])
        total = sum(hist)
        score = dark / float(total or 1)

    return score >= SIGNATURE_THRESHOLD


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
