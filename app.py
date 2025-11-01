from fastapi import FastAPI
from pydantic import BaseModel
from app_with_token import process_database_queries, call_library_bot

app = FastAPI()

class QueryRequest(BaseModel):
    prompt: str

@app.post("/query")
async def get_response(req: QueryRequest):
    prompt = req.prompt
    response = process_database_queries(prompt)
    if not response:
        response = call_library_bot(prompt)
    return {"response": response}
