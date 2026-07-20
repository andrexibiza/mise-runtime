import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "hermes-plugin"))

from agent.memory_manager import MemoryManager, build_memory_context_block
from mise import MiseMemoryProvider


NONCE = "MISE_PRETOOL_NONCE_7f52c5"
QUERY = "Which Mise pre-tool nonce belongs to the Agents Dashboard probe?"


class RecordingClient:
    def __init__(self, events):
        self.events = events

    def query(self, request):
        self.events.append("mise_prefetch")
        return {
            "results": [{
                "Name": "Agents Dashboard pre-tool probe",
                "Memory Key": "probe:agents-dashboard-pretool",
                "Abstract": f"The exact probe nonce is {NONCE}.",
                "Agent Brief": "Use the nonce to prove memory reached the model request before tool choice.",
                "Origin": "Human",
                "url": "https://notion.so/agents-dashboard-pretool-probe",
                "Updated": "2026-07-19T23:40:00Z",
            }]
        }


def run_first_decision_probe(events, *, omit_context=False):
    provider = MiseMemoryProvider(
        RecordingClient(events),
        "collection://00000000-0000-4000-8000-000000000001",
    )
    provider.active = True
    manager = MemoryManager()
    manager.add_provider(provider)

    prefetched = manager.prefetch_all(QUERY)
    if omit_context:
        prefetched = ""

    api_user_message = QUERY
    fenced = build_memory_context_block(prefetched)
    if fenced:
        api_user_message += "\n\n" + fenced

    events.append("model_request")
    assert NONCE in api_user_message, "relevant Mise context was absent at model-request time"
    assert events == ["mise_prefetch", "model_request"], "prefetch must finish before the first model request"

    # A tool choice can only be emitted by the model after this request.
    events.append("tool_choice")
    return api_user_message


class PreToolContextContractTests(unittest.TestCase):
    def test_hermes_core_injects_prefetch_before_model_execution_boundary(self):
        from agent.conversation_loop import run_conversation
        from agent.turn_context import build_turn_context

        turn_source = inspect.getsource(build_turn_context)
        loop_source = inspect.getsource(run_conversation)

        self.assertLess(
            turn_source.index(".prefetch_all("),
            turn_source.index("return TurnContext("),
        )
        self.assertLess(
            loop_source.index("build_memory_context_block(_ext_prefetch_cache)"),
            loop_source.index("run_llm_execution_middleware("),
        )

    def test_relevant_mise_context_reaches_model_before_tool_choice(self):
        events = []

        api_user_message = run_first_decision_probe(events)

        self.assertIn("<memory-context>", api_user_message)
        self.assertIn(NONCE, api_user_message)
        self.assertEqual(events, ["mise_prefetch", "model_request", "tool_choice"])

    def test_probe_fails_red_before_tool_choice_when_context_is_missing(self):
        events = []

        with self.assertRaisesRegex(AssertionError, "context was absent"):
            run_first_decision_probe(events, omit_context=True)

        self.assertEqual(events, ["mise_prefetch", "model_request"])
        self.assertNotIn("tool_choice", events)


if __name__ == "__main__":
    unittest.main()
