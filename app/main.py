from fastapi import FastAPI
import random
from datetime import datetime

app = FastAPI()


@app.get("/")
def health_check():
    return {"status": "OK"}


@app.get("/endpoint")
def endpoint():
    max = 1000
    min = 1
    rand = random.randint(min, max)
    time = str(datetime.now())
    output = f'''{time}_{rand}'''
    return {"status": "OK", "output": output}

@app.post("/test")
def test(data):
    # max = 1000
    # min = 1
    # rand = random.randint(min, max)
    # time = str(datetime.now())
    # output = f'''{time}_{rand}'''
    return {"status": "OK", "output": data}
