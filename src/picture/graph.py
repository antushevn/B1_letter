from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .nodes import await_description, check_description, pick_picture
from .state import PictureState


def create_picture_graph():
    builder = StateGraph(PictureState)

    builder.add_node("pick_picture", pick_picture)
    builder.add_node("await_description", await_description)
    builder.add_node("check_description", check_description)

    builder.set_entry_point("pick_picture")
    builder.add_edge("pick_picture", "await_description")
    builder.add_edge("await_description", "check_description")
    builder.add_edge("check_description", END)

    return builder.compile(checkpointer=MemorySaver())
