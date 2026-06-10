"""Tesseract OCR front-end shared by the OCR-based pipelines.

A single :func:`run_ocr` call returns both the reconstructed page text (for the
LLM pipeline) and per-word bounding boxes (for the rules pipeline), so both
pipelines consume the same OCR pass rather than running Tesseract twice.

Requires the Tesseract binary on the system (``brew install tesseract`` on macOS);
``pytesseract`` is only a thin wrapper around it.
"""

from __future__ import annotations

from pathlib import Path

import pytesseract
from PIL import Image
from pydantic import BaseModel


class OcrWord(BaseModel):
    """One recognised word and where it sits on the page."""

    text: str
    confidence: float  # Tesseract confidence, 0-100
    left: int
    top: int
    width: int
    height: int


class OcrResult(BaseModel):
    """The output of OCR-ing one image: full text plus located words."""

    text: str  # reconstructed page text, line breaks preserved
    words: list[OcrWord]


def run_ocr(
    image_path: Path,
    *,
    tesseract_cmd: str | None = None,
    grayscale: bool = False,
) -> OcrResult:
    """Run Tesseract over one image and return its text and word boxes.

    ``tesseract_cmd`` overrides the binary location when it is not on ``PATH``.
    These invoices are clean digital renders, so no preprocessing is applied by
    default; ``grayscale`` is available as an opt-in.
    """
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    with Image.open(image_path) as image:
        if grayscale:
            image = image.convert("L")
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

    words: list[OcrWord] = []
    lines: dict[tuple[int, int, int, int], list[str]] = {}
    for i, raw_text in enumerate(data["text"]):
        text = raw_text.strip()
        if not text:
            continue
        confidence = float(data["conf"][i])
        if confidence < 0:  # Tesseract marks non-text layout rows with conf -1
            continue
        words.append(
            OcrWord(
                text=text,
                confidence=confidence,
                left=int(data["left"][i]),
                top=int(data["top"][i]),
                width=int(data["width"][i]),
                height=int(data["height"][i]),
            )
        )
        line_key = (
            data["page_num"][i],
            data["block_num"][i],
            data["par_num"][i],
            data["line_num"][i],
        )
        lines.setdefault(line_key, []).append(text)

    page_text = "\n".join(" ".join(parts) for parts in lines.values())
    return OcrResult(text=page_text, words=words)
