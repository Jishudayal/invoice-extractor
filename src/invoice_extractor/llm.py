"""LLM client for Pipeline A, with an Azure OpenAI implementation.

Pipeline A depends only on the small :class:`LLMClient` protocol, so swapping
providers means implementing this protocol and pointing config at it — no
pipeline changes. The Azure OpenAI implementation is the one shipped; it uses
native structured outputs to return the :class:`InvoiceFields` schema directly.

``openai`` is imported lazily (only when the Azure client is constructed) so the
keyless rules path never needs the dependency installed.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from invoice_extractor.config import Settings
from invoice_extractor.models import InvoiceFields

SYSTEM_PROMPT = (
    "You extract structured fields from a single invoice. The text is OCR output "
    "and may appear out of reading order because the invoice has a two-column "
    "layout (Seller on the left, Client on the right) — rely on the labels to "
    "attribute each value to the correct party. Take the monetary totals (net "
    "worth, VAT, gross worth) from the SUMMARY 'Total' row, not from line items. "
    "Copy values exactly as printed; use null for any field that is absent."
)


class LLMExtraction(BaseModel):
    """An LLM extraction plus the token usage needed for cost reporting."""

    fields: InvoiceFields
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient(Protocol):
    """Turns OCR text into structured invoice fields."""

    def extract(self, ocr_text: str) -> LLMExtraction: ...


class AzureOpenAIClient:
    """:class:`LLMClient` backed by Azure OpenAI structured outputs."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        api_version: str,
        deployment: str,
        temperature: float = 0.0,
    ) -> None:
        from openai import AzureOpenAI  # lazy: only needed when Pipeline A runs

        self._client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            max_retries=3,  # SDK retries 429/5xx with backoff
        )
        self._deployment = deployment
        self._temperature = temperature

    def extract(self, ocr_text: str) -> LLMExtraction:
        completion = self._client.beta.chat.completions.parse(
            model=self._deployment,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": ocr_text},
            ],
            response_format=InvoiceFields,
        )
        message = completion.choices[0].message
        if message.parsed is None:
            # A refusal or unparseable response is a failure, not empty extraction —
            # raise so the pipeline records it in PipelineResult.error.
            refusal = getattr(message, "refusal", None)
            raise RuntimeError(f"structured output unavailable: {refusal or 'no parsed content'}")

        usage = completion.usage
        return LLMExtraction(
            fields=message.parsed,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )


def make_llm_client(settings: Settings) -> LLMClient:
    """Build the configured LLM client, or raise if Azure OpenAI is not set up."""
    if not settings.llm_enabled:
        raise RuntimeError("Azure OpenAI is not configured; set the AZURE_OPENAI_* values in .env.")
    return AzureOpenAIClient(
        endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        deployment=settings.azure_openai_deployment_name,
        temperature=settings.llm_temperature,
    )
