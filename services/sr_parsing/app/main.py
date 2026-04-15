from fastapi import FastAPI

app = FastAPI(title="sr_parsing service")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "sr_parsing"
    }


@app.post("/process")
def process(data: dict):
    return {
        "status": "processed",
        "service": "sr_parsing",
        "input": data
    }
