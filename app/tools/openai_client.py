import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Optional


class OpenAIClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenAIResponse:
    text: str
    raw: Dict[str, Any]


class OpenAIClient:
    def __init__(
        self,
        api_key: str,
        model: str = "doubao-seed-2.0-code",
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        timeout_seconds: int = 60,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate_text(
        self,
        instructions: str,
        input_text: str,
        max_output_tokens: int = 700,
    ) -> OpenAIResponse:
        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": input_text,
            "max_output_tokens": max_output_tokens,
            "store": False,
        }
        request = urllib.request.Request(
            url=f"{self.base_url}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            message = error.read().decode("utf-8", errors="replace")
            raise OpenAIClientError(f"OpenAI API request failed: {error.code} {message}") from error
        except urllib.error.URLError as error:
            raise OpenAIClientError(f"OpenAI API request failed: {error.reason}") from error

        data = json.loads(body)
        text = extract_output_text(data)
        if not text:
            raise OpenAIClientError("OpenAI API response did not include output text.")
        return OpenAIResponse(text=text, raw=data)

    def generate_text_stream(
        self,
        instructions: str,
        input_text: str,
        max_output_tokens: int = 700,
    ) -> Iterator[str]:
        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": input_text,
            "max_output_tokens": max_output_tokens,
            "store": False,
            "stream": True,
        }
        request = urllib.request.Request(
            url=f"{self.base_url}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                for delta in iter_sse_text_deltas(response):
                    if delta:
                        yield delta
        except urllib.error.HTTPError as error:
            message = error.read().decode("utf-8", errors="replace")
            raise OpenAIClientError(f"OpenAI API request failed: {error.code} {message}") from error
        except urllib.error.URLError as error:
            raise OpenAIClientError(f"OpenAI API request failed: {error.reason}") from error

    def test_connection(self) -> str:
        response = self.generate_text(
            instructions="You are a connection test. Reply with exactly: ok",
            input_text="connection test",
            max_output_tokens=16,
        )
        return response.text

    def create_embeddings(self, inputs: list, model: str) -> list:
        payload = {
            "model": model,
            "input": inputs,
        }
        request = urllib.request.Request(
            url=f"{self.base_url}/embeddings",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            message = error.read().decode("utf-8", errors="replace")
            raise OpenAIClientError(f"OpenAI embeddings request failed: {error.code} {message}") from error
        except urllib.error.URLError as error:
            raise OpenAIClientError(f"OpenAI embeddings request failed: {error.reason}") from error

        data = json.loads(body)
        embeddings = [item.get("embedding") for item in data.get("data", [])]
        if len(embeddings) != len(inputs) or any(not isinstance(embedding, list) for embedding in embeddings):
            raise OpenAIClientError("OpenAI embeddings response did not include expected vectors.")
        return embeddings


def extract_output_text(data: Dict[str, Any]) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str):
        return output_text.strip()

    texts = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                texts.append(content["text"])
    return "\n".join(text.strip() for text in texts if text.strip())


def iter_sse_text_deltas(response) -> Iterator[str]:
    event_lines = []
    for raw_line in response:
        line = raw_line.decode("utf-8").rstrip("\r\n")
        if not line:
            if event_lines:
                payload = _parse_sse_data_block(event_lines)
                event_lines = []
                if payload == "[DONE]":
                    break
                if not payload:
                    continue
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                delta = extract_stream_text_delta(event)
                if delta:
                    yield delta
            continue
        if line.startswith(":"):
            continue
        event_lines.append(line)

    if event_lines:
        payload = _parse_sse_data_block(event_lines)
        if payload and payload != "[DONE]":
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                return
            delta = extract_stream_text_delta(event)
            if delta:
                yield delta


def _parse_sse_data_block(lines: list[str]) -> str:
    data_lines = []
    for line in lines:
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    return "\n".join(data_lines).strip()


def extract_stream_text_delta(event: Dict[str, Any]) -> str:
    event_type = event.get("type")
    if event_type in {"response.output_text.delta", "output_text.delta"} and isinstance(event.get("delta"), str):
        return event["delta"]
    if isinstance(event.get("delta"), str) and "output_text" in str(event_type or ""):
        return event["delta"]
    return ""
