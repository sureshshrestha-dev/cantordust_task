from langgraph.graph import END, START, StateGraph
from src.llm import GeminiEngine
from src.models import ProductData, ReviewResultSchema
from src.agents import AgentNode
from enum import Enum
from typing import TypedDict, Annotated, List, Dict, Any
import operator

# SOURCE_1_URL = "https://www.deyeinverter.com/deyeinverter/2023/10/07/datasheet_sun-4-12k-g06p3-eu-am2-p1_231007_en.pdf"
# SOURCE_1_LABEL = "Manufacturer datasheet -- AM2-P1 variant (Oct 2023)"

# SOURCE_2_URL = "https://www.deyeinverter.com/deyeinverter/2024/03/20/datasheet_sun-4-15k-g06p3-eu-am2_240318_en.pdf"
# SOURCE_2_LABEL = "Manufacturer datasheet -- AM2 variant (Mar 2024)"
# # 

class Agents(Enum):
    agent1 = "agent1"
    agent2 = "agent2"

class AgentState(TypedDict, total=False):
    source1_history: Annotated[List[Dict[str, Any]], operator.add] 
    source2_history: Annotated[List[Dict[str, Any]], operator.add] 
    source1_url: str
    source2_url: str
    target_model: str
    final_report: dict = {}
    review_result: dict = {}
    review_instruction: str=""
    refetch_Result: Agents 
    review_passed: bool = False
    loop_count: int = 0
    max_loops: int = 4




def should_continue(state: AgentState):
    review_res = state.get("review_result", {})
    if isinstance(review_res, dict) and review_res.get("review_passed"):
        return "success" 
    
    max_loops = state.get("max_loops", 4)
    if state.get("loop_count", 0) >= max_loops:
        return "max_retries" 
    
    return "retry" 



import json
import os

# Initialize your engine once
engine = GeminiEngine()

# Load prompts
prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompt.json')
with open(prompt_path, 'r') as f:
    prompts = json.load(f).get("prompt", {})

extraction_prompt = prompts.get("extraction_agent_prompt", "")
review_prompt = prompts.get("Review_agent_prompt", "")
reporter_prompt = prompts.get("final_report_prompt", "")

agent1 = AgentNode(
    engine=engine,
    name="Agent1_Extractor",
    instructions=extraction_prompt,
    output_key="source1_history",
    url_key="source1_url",
    response_model=ProductData
)

agent2 = AgentNode(
    engine=engine,
    name="Agent2_Extractor",
    instructions=extraction_prompt,
    output_key="source2_history",
    url_key="source2_url",
    response_model=ProductData
)
reviewer = AgentNode(
    engine=engine,
    name="Reviewer",
    instructions=review_prompt,
    output_key="review_result", 
    response_model=ReviewResultSchema, 
    use_thinking=True
)

reporter = AgentNode(
    engine=engine,
    name="Reporter",
    instructions=reporter_prompt,
    output_key="final_report",
    use_thinking=True
)

# def final_report_writer(state: AgentState):
#     s1_final = state["source1_result"][-1]
#     s2_final = state["source2_result"][-1]
    
#     report = f"""
#     --- SUNBRIDGE IMPORT DRAFT ---
#     5kW Inverter Analysis
    
#     SOURCE 1 (AM2-P1): {s1_final['voltage']}
#     SOURCE 2 (AM2): {s2_final['voltage']}
    
#     ADVISORY FOR AGENT: 
#     There is a conflict between the 2023 and 2024 datasheets regarding [Feature]. 
#     The pipeline performed {state['loop_count']} cross-checks to verify these values.
#     """
#     return {"final_report": report}

def router_node(state: AgentState):
    return {"loop_count": state.get("loop_count", 0) + 1}

def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("agent_1", agent1)
    workflow.add_node("agent_2", agent2)
    workflow.add_node("reviewer", reviewer)
    workflow.add_node("final_report", reporter)
    workflow.add_node("router", router_node)

    workflow.add_edge(START, "agent_1")
    workflow.add_edge(START, "agent_2")
    workflow.add_edge(["agent_1", "agent_2"], "reviewer")
    workflow.add_conditional_edges(
        "reviewer",
        should_continue,      
        {                    
            "success": "final_report", 
            "max_retries": "final_report", 
            "retry": "router"
        }
    )
    workflow.add_edge("router", "agent_1")
    workflow.add_edge("router", "agent_2")

    workflow.add_edge("final_report", END)
    return workflow.compile()
