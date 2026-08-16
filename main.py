from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from src.models import RequestBody
from src.graphy import build_graph
import json
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def health():  
    return RedirectResponse(url="/docs")


@app.post("/run")
async def run_agent(req: RequestBody):
    try:
        graph = build_graph()
        state = {
            "source1_url": req.source1,
            "source2_url": req.source2,
            "target_model": req.target_model,
            "max_loops": req.max_loops,
            "loop_count": 0,
            "source1_history": [],
            "source2_history": [],
        }
        result = await graph.ainvoke(state)
     
        # Save all agent process outputs to the requested JSON file
        import json
        output_path = "/home/suresh/Desktop/trash/cantordust_task/output/agent_results.json"
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=4, default=str)
            print(f"DEBUG: Successfully saved all agent outputs to {output_path}")
        except Exception as file_err:
            print(f"DEBUG: Failed to save output file: {file_err}")

        # Save the final report as a readable markdown document
        md_path = "/home/suresh/Desktop/trash/cantordust_task/output/final_report.md"
        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(str(result.get("final_report", "No report generated.")))
            print(f"DEBUG: Successfully saved markdown report to {md_path}")
        except Exception as file_err:
            print(f"DEBUG: Failed to save markdown file: {file_err}")

        return {"final_report": result.get("final_report")}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)