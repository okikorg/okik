
from transformers import pipeline
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch

app = FastAPI()
model = pipeline("text-generation", model="meta-llama/Llama-3.2-3B-Instruct")

class TextRequest(BaseModel):
    text: str
    max_length: int = 50

@app.post("/generate")
def generate_text(request: TextRequest):
    try:
        result = model(request.text, max_length=request.max_length)
        return {"generated_text": result[0]["generated_text"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    