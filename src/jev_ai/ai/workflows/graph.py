"""Construcción del grafo de chat con LangGraph."""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from jev_ai.ai.jev.intents import IntentClassifier
from jev_ai.ai.llm.base import LLMProvider
from jev_ai.ai.workflows.nodes import ChatNodes
from jev_ai.ai.workflows.state import ChatState


def build_chat_graph(
    classifier: IntentClassifier,
    llm: LLMProvider,
) -> CompiledStateGraph:
    """Compila el flujo classify → route → plan → validate → execute → respond.

    La sesión de base de datos se pasa en ``config["configurable"]["session"]`` para
    que el grafo pueda compilarse una sola vez y seguir siendo stateless.
    """
    nodes = ChatNodes(classifier, llm)
    graph = StateGraph(ChatState)

    graph.add_node("classify_intent", nodes.classify_intent)
    graph.add_node("help", nodes.help)
    graph.add_node("clarify", nodes.clarify)
    graph.add_node("error", nodes.error)
    graph.add_node("propose_plan", nodes.propose_plan)
    graph.add_node("validate_plan", nodes.validate_plan)
    graph.add_node("execute_service", nodes.execute_service)
    graph.add_node("generate_response", nodes.generate_response)

    graph.add_edge(START, "classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        nodes.route_after_classify,
        {"help": "help", "clarify": "clarify", "plan": "propose_plan"},
    )
    graph.add_conditional_edges(
        "propose_plan",
        nodes.route_after_propose,
        {"validate": "validate_plan", "clarify": "clarify", "error": "error"},
    )
    graph.add_conditional_edges(
        "validate_plan",
        nodes.route_after_validate,
        {"execute": "execute_service", "clarify": "clarify", "finish": END},
    )
    graph.add_conditional_edges(
        "execute_service",
        nodes.route_after_execute,
        {"respond": "generate_response", "clarify": "clarify"},
    )
    graph.add_edge("help", END)
    graph.add_edge("clarify", END)
    graph.add_edge("error", END)
    graph.add_edge("generate_response", END)

    return graph.compile()
