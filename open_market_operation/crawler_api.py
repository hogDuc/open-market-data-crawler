from fastapi import FastAPI
from crawler import crawl
from typing import Optional

app = FastAPI()

@app.get('/crawl-omo')
def run_crawler(last_date: Optional[str] = None):
    try:
        data = crawl(last_date)
        return data
    except Exception as error:
        return{
            "status":"error",
            "message":str(error)
        }