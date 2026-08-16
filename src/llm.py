import json
import os
from dotenv import load_dotenv

load_dotenv()
from typing import Type, Optional, Any, Union, Dict
import asyncio
from pydantic import BaseModel
from google import genai as google_genai
from google.genai import types as genai_types
from src.agents import AgentNode

class GeminiEngine:
    def __init__(self, api_key: str = None):
        self.api_key = api_key

    async def call(self,system_instruction: str,user_prompt: str,pdf_url: Optional[str] = None,response_model: Optional[Type[BaseModel]] = None, use_thinking: bool = False):
        client = google_genai.Client(api_key=self.api_key or os.environ.get("GEMINI_API_KEY"))
        parts = [genai_types.Part.from_text(text=user_prompt)]
        
        if pdf_url:
            if isinstance(pdf_url, list):
                for url in pdf_url:
                    parts.append(genai_types.Part.from_uri(file_uri=url, mime_type="application/pdf"))
            else:
                parts.append(genai_types.Part.from_uri(file_uri=pdf_url, mime_type="application/pdf"))

        # If a response_model is provided, we tell Gemini to follow that schema
        if response_model:
            schema_json = json.dumps(response_model.model_json_schema())
            system_instruction += f"\n\nOutput must be valid JSON matching this schema: {schema_json}. Return ONLY the JSON object."

        config_kwargs = {
            "system_instruction": system_instruction,
            "temperature": 0.1,
        }
        
        if use_thinking:
            config_kwargs["thinking_config"] = {"thinking_budget": 1024}
            config_kwargs["temperature"] = 0.7  # Thinking generally requires higher temperature
            
        config = genai_types.GenerateContentConfig(**config_kwargs)

        print("Sending API request to Google")
        # 4. Execute Async Call
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[genai_types.Content(role="user", parts=parts)],
            config=config
        )
        print("Gemini response")

      
        raw_text = response.text.strip().replace("```json", "").replace("```", "")
        
        if response_model:
            try:
                return response_model.model_validate_json(raw_text)
            except Exception as e:
                print(f"Validation Error: {e}")
                return {"error": "parsing_failed", "raw": raw_text}
        
        return raw_text 


# async def run_pipeline(max_loops: int = 4, source1: str = "", source2: str = "", target_model: str = "") -> Dict[str, Any]:
#     from src.graphy import build_graph
#     app = build_graph()
#     initial_state = {
#         "target_model": target_model,
#         "source1_history": [],
#         "source2_history": [],
#         "loop_count": 0,
#         "max_loops": max_loops,
#         "review_passed": False
#     }

#     # 3. Invoke the graph (LangGraph handles the loops and conditions automatically)
#     final_state = await app.ainvoke(initial_state)
    
#     return final_state

