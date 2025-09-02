from enum import Enum
from typing import List, Optional, Union
from pydantic import BaseModel


class Result(Enum):
    SUCCESS = "正常 ✅"
    WARNING = "異常 ⚠️"
    ERROR = "錯誤 ❌"


class BranchIssue(Enum):
    NotExist = "缺少 {branches}"
    PermissionIssue = "{branches} 權限不足"


class PipelineIssue(Enum):
    NotFoundError = "無法取得最新 pipeline"
    PipelineError = "pipeline 狀態異常，目前為：{pipeline_status}"
    JobError = "job {job_name} 狀態異常，目前為：{job_status}"


class CiIssue(Enum):
    StageError = "Stage 執行順序異常"
    StageMissing = "無法取得 Stage 執行順序"
    JobNameError = "job 名稱或數量錯誤錯誤"
    YamlNotFoundError = "無法取得 .gitlab-ci.yml"
    StageNotFoundError = "無法取得 對應job"
    MissingBranchError = "{branch_name} 未設定"
    ExtraBranchError = "{job_name} {branch_name}，目前為 {setting} ，預期為 never"
    JobError = "{job_name} {branch_name}  設定錯誤，目前為 {setting} ，預期為 {expect_setting} "
    IgnoreNotSetError = "未判斷 $IGNORE_TEST 參數"


class StageIssue(BaseModel):
    name: str
    issues: List[str]


class BranchCheck(BaseModel):
    status: Result
    issues: List[str] = []


class PipelineCheck(BaseModel):
    status: Result
    pipeline_id: Optional[int] = None
    issues: List[str] = []


class CICheck(BaseModel):
    status: Result
    issues: List[Union[StageIssue | str]] = []


class ProjectDetail(BaseModel):
    branch_check: BranchCheck
    pipeline_check: PipelineCheck
    ci_check: CICheck


class ProjectReport(BaseModel):
    url: str
    name: Optional[str] = ""
    summary: Result
    detail: Optional[Union[ProjectDetail | str]]


class ApiInput(BaseModel):
    issueId: int
    issueKey: str
