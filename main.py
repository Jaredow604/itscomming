from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "El motor de It's Coming esta en linea"}