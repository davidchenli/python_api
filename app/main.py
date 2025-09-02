import os
import logging
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from service import ApiInput, Destruct, Verify, ReportFormat

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

app = FastAPI()

input_destruct = Destruct()
repo_check = Verify()
report_format = ReportFormat()


@app.middleware("http")
async def log_request_time(request: Request, call_next):
    start_time = datetime.now()
    response = await call_next(request)
    process_time = datetime.now() - start_time
    logging.info(f"✅ Request: {request.method} {request.url} completed in {process_time}")
    return response


@app.exception_handler(Exception)
def global_exception_handler(request: Request, exc: Exception):
    logging.exception(f"Unhandled Exception on {request.method} {request.url}")
    logging.exception(f"{exc}")
    return JSONResponse(
        status_code=500,
        content={"message": f"{exc}"}
    )


@app.get("/")
def health_check():
    return {"status": "OK"}


@app.post("/check_rms_report", response_class=PlainTextResponse)
async def check_rms_report(data: ApiInput):
    # issue_id, issue_key, project_list = input_destruct.get_project_list(data)
    # project_output_list = []
    # for project in project_list:
    #     project_output_list.append(repo_check.execute(project))
    # text_output = report_format.generate_report(project_output_list)

    print(data)
    # return data
