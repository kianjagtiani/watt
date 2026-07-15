from assistant import agent
from assistant.config import Settings
from assistant.db import connect
from assistant.llm import LLMResponse, ToolCall
from assistant.store import history, tasks, users

SETTINGS = Settings("", "", "", "", "gemini-2.5-flash", "task_reminder",
                    "1555", ":memory:", "America/Los_Angeles")


class FakeLLM:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def chat(self, system, messages, tools):
        self.calls.append((system, messages))
        return self.script.pop(0)


class BoomLLM:
    def chat(self, *a, **k):
        raise RuntimeError("quota")


def _conn():
    conn = connect(":memory:")
    users.add_user(conn, "1555", name="Kian", is_admin=True)
    return conn


def test_tool_call_then_reply():
    conn = _conn()
    llm = FakeLLM([
        LLMResponse(None, [ToolCall("add_tasks", {"items": [{"text": "buy milk"}]})]),
        LLMResponse("Added: buy milk ✅", []),
    ])
    reply = agent.handle_message(conn, SETTINGS, llm, "1555", text="add buy milk")
    assert reply == "Added: buy milk ✅"
    assert tasks.list_tasks(conn, "1555")[0]["text"] == "buy milk"
    assert history.recent(conn, "1555")[-1] == {"role": "assistant",
                                                "content": "Added: buy milk ✅"}
    system = llm.calls[0][0]
    assert "buy milk" not in system  # task added after prompt built is fine
    assert "Kian" in system


def test_open_tasks_appear_in_system_prompt():
    conn = _conn()
    tasks.add_task(conn, "1555", "finish PRA draft", category="Research")
    llm = FakeLLM([LLMResponse("You have 1 task", [])])
    agent.handle_message(conn, SETTINGS, llm, "1555", text="what's left?")
    assert "finish PRA draft" in llm.calls[0][0]


def test_image_gets_attached_and_logged():
    conn = _conn()
    llm = FakeLLM([LLMResponse("Got the screenshot 👍", [])])
    agent.handle_message(conn, SETTINGS, llm, "1555", image=(b"png", "image/png"))
    msgs = llm.calls[0][1]
    assert msgs[-1]["image"] == (b"png", "image/png")
    assert history.recent(conn, "1555")[0]["content"] == "[sent an image]"


def test_llm_error_message():
    conn = _conn()
    reply = agent.handle_message(conn, SETTINGS, BoomLLM(), "1555", text="hi")
    assert "snag" in reply


def test_reminder_time_localization_instruction():
    conn = _conn()
    llm = FakeLLM([LLMResponse("Got it", [])])
    agent.handle_message(conn, SETTINGS, llm, "1555", text="hi")
    system = llm.calls[0][0]
    assert "convert" in system
    assert "UTC" in system
    assert "local timezone" in system
