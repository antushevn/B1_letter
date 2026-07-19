from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .nodes import await_letter, check_letter, generate_topic
from .state import PracticeState


def create_graph():
    builder = StateGraph(PracticeState)

    builder.add_node("generate_topic", generate_topic)
    builder.add_node("await_letter", await_letter)
    builder.add_node("check_letter", check_letter)

    builder.set_entry_point("generate_topic")
    builder.add_edge("generate_topic", "await_letter")
    builder.add_edge("await_letter", "check_letter")
    builder.add_edge("check_letter", END)

    return builder.compile(checkpointer=MemorySaver())
