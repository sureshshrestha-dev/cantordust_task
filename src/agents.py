from typing import Optional, Type, Any, Dict
import asyncio
from pydantic import BaseModel

class AgentNode:
    def __init__(self, engine, name: str, instructions: str, output_key: str, pdf_url: Optional[list[str]] = None, url_key: Optional[str] = None, response_model: Optional[Type[BaseModel]] = None, use_thinking: bool = False):
        self.engine = engine
        self.name = name
        self.instructions = instructions
        self.output_key = output_key
        self.pdf_url = pdf_url
        self.url_key = url_key
        self.response_model = response_model
        self.use_thinking = use_thinking

    async def __call__(self, state: Any):
        print(f"agent {self.name} started")
        user_context = f"Current Loop: {state.get('loop_count', 0)}\n"
        
        target = state.get("target_model")
        if target:
            user_context = f"Target Model: {target}\n" + user_context
            
        if state.get("review_instruction"):
            user_context += f"Feedback: {state['review_instruction']}\n"
        if self.name == "Reviewer":
            user_context += f"Data 1: {state.get('source1_history', [])[-1:]}\n"
            user_context += f"Data 2: {state.get('source2_history', [])[-1:]}\n"
        import json
        
        # Build formatting dictionary for the instructions
        fmt_args = {
            "target_model": state.get("target_model", "Unknown Model"),
            "variant_name": "AM2-P1" if self.name == "Agent1_Extractor" else "AM2",
            "date": "Oct 2023" if self.name == "Agent1_Extractor" else "Mar 2024",
            "source1_data": json.dumps(state.get("source1_history", [{}])[-1]) if state.get("source1_history") else "{}",
            "source2_data": json.dumps(state.get("source2_history", [{}])[-1]) if state.get("source2_history") else "{}",
            "review_findings": json.dumps(state.get("review_result", {}))
        }
        
        # Format the system instruction dynamically
        system_instruction = self.instructions
        try:
            for key, value in fmt_args.items():
                system_instruction = system_instruction.replace(f"{{{key}}}", str(value))
        except Exception as e:
            print(f"Warning: Prompt formatting failed: {e}")

        # 2. Resolve PDF URLs dynamically if url_key is provided
        current_pdf_urls = self.pdf_url
        if self.url_key and state.get(self.url_key):
            current_pdf_urls = [state.get(self.url_key)]

        print(f"{self.name} - Calling Gemini...")
        result = await self.engine.call(
            system_instruction=system_instruction,
            user_prompt=user_context,
            pdf_url=current_pdf_urls,
            response_model=self.response_model,
            use_thinking=self.use_thinking
        )
        print(f"DEBUG: {self.name} - Gemini Engine responded successfully!")

        # 3. Format the update for the state
        # If the output_key is a history list (Source 1 or 2), we wrap in a list
        if "history" in self.output_key:
            val = result.model_dump() if hasattr(result, "model_dump") else result
            return {self.output_key: [val]}

        val = result.model_dump() if hasattr(result, "model_dump") else result
        print(f"DEBUG: {self.name} - Returning parsed state update.")
        return {self.output_key: val}




