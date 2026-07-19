from assistant.llm import ToolCall, _to_contents


def test_roles_map_to_gemini():
    msgs = [
        {"role": "user", "content": "add milk"},
        {"role": "assistant", "tool_calls": [ToolCall("add_tasks", {"items": []})]},
        {"role": "tool", "name": "add_tasks", "content": '{"ok": true}'},
        {"role": "assistant", "content": "Added!"},
    ]
    contents = _to_contents(msgs)
    assert [c.role for c in contents] == ["user", "model", "user", "model"]
    assert contents[1].parts[0].function_call.name == "add_tasks"
    assert contents[2].parts[0].function_response.name == "add_tasks"
    assert contents[3].parts[0].text == "Added!"


def test_thought_signature_round_trips():
    msgs = [
        {"role": "assistant", "tool_calls": [
            ToolCall("add_tasks", {"items": []}, thought_signature=b"sig-bytes"),
            ToolCall("set_reminder", {"text": "x"}),
        ]},
    ]
    (c,) = _to_contents(msgs)
    assert c.parts[0].thought_signature == b"sig-bytes"
    assert c.parts[1].thought_signature is None


def test_image_message_becomes_two_parts():
    msgs = [{"role": "user", "content": "job posting", "image": (b"\x89PNG", "image/png")}]
    (c,) = _to_contents(msgs)
    assert len(c.parts) == 2
    assert c.parts[0].inline_data.mime_type == "image/png"
    assert c.parts[1].text == "job posting"
