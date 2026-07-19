from dataclasses import dataclass, field

from google import genai
from google.genai import types


@dataclass
class ToolCall:
    name: str
    args: dict
    # Gemini 3 rejects replayed function calls without their thought signature.
    thought_signature: bytes | None = None


@dataclass
class LLMResponse:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


def _to_contents(messages: list[dict]) -> list[types.Content]:
    contents = []
    for m in messages:
        if m["role"] == "tool":
            parts = [types.Part.from_function_response(
                name=m["name"], response={"result": m["content"]}
            )]
            contents.append(types.Content(role="user", parts=parts))
        elif m["role"] == "assistant":
            if m.get("tool_calls"):
                parts = []
                for c in m["tool_calls"]:
                    p = types.Part.from_function_call(name=c.name, args=c.args)
                    p.thought_signature = c.thought_signature
                    parts.append(p)
            else:
                parts = [types.Part.from_text(text=m["content"])]
            contents.append(types.Content(role="model", parts=parts))
        else:
            parts = []
            if m.get("image"):
                data, mime = m["image"]
                parts.append(types.Part.from_bytes(data=data, mime_type=mime))
            if m.get("content"):
                parts.append(types.Part.from_text(text=m["content"]))
            contents.append(types.Content(role="user", parts=parts))
    return contents


class GeminiProvider:
    def __init__(self, api_key: str, model: str):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def chat(self, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters=t["parameters"],
                )
                for t in tools
            ])] if tools else None,
        )
        resp = self._client.models.generate_content(
            model=self._model, contents=_to_contents(messages), config=config
        )
        text_parts, calls = [], []
        for part in resp.candidates[0].content.parts:
            if part.function_call:
                calls.append(ToolCall(
                    part.function_call.name,
                    dict(part.function_call.args),
                    part.thought_signature,
                ))
            elif part.text:
                text_parts.append(part.text)
        return LLMResponse("\n".join(text_parts) or None, calls)
