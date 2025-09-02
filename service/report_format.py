from datetime import datetime
from collections import Counter
from typing import List, Dict, Tuple, Union

from .base import Result, ProjectReport, StageIssue


class ReportFormat:

    def generate_report(self, project_results: list[ProjectReport]):

        summary, detail, projects = self.generate_overall_result(project_results)
        header = self.get_title(summary, detail)
        blocks = [self.get_content(proj) for proj in projects]
        return header + "\n".join(blocks)

    @staticmethod
    def generate_overall_result(projects: list[ProjectReport]) -> Tuple[
        Result, Union[Dict[Result, int], str], List[ProjectReport]]:

        if not projects:
            return Result.ERROR, "未找到 專案 URL", []

        order = {Result.ERROR: 0, Result.WARNING: 1, Result.SUCCESS: 2}

        summary_counts = Counter(p.summary for p in projects)

        counts = {
            Result.ERROR: summary_counts.get(Result.ERROR, 0),
            Result.WARNING: summary_counts.get(Result.WARNING, 0),
            Result.SUCCESS: summary_counts.get(Result.SUCCESS, 0)
        }

        if counts[Result.ERROR] > 0:
            check_status = Result.ERROR
        elif counts[Result.WARNING] > 0:
            check_status = Result.WARNING
        else:
            check_status = Result.SUCCESS

        sorted_projects = sorted(projects, key=lambda p: order[p.summary])
        return check_status, counts, sorted_projects

    @staticmethod
    def get_title(summary: Result, detail: dict | str) -> str:

        header = f"[RMS 簽核模組] 專案設定檢查 ：{summary.value}\n\n" \
                 f"📅 檢查時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        if (summary == Result.ERROR) and (isinstance(detail, str)):
            header += f'❌ {detail}\n\n'
        else:
            header += f"✅ 正常專案：{detail[Result.SUCCESS]}\n" \
                      f"⚠️ 異常專案：{detail[Result.WARNING]}\n" \
                      f"❌ 錯誤專案：{detail[Result.ERROR]}\n\n"
        return header

    def get_content(self, report_data: ProjectReport) -> str:
        url = report_data.url
        name = report_data.name
        summary = report_data.summary
        detail = report_data.detail

        content = f"💼 專案：{url} {summary.value}\n" \
                  f"🔷 專案名稱：{name}\n"

        if (summary == Result.ERROR) and (isinstance(detail, str)):
            content += f'❌ {detail}\n\n'
        else:
            content += self._get_content_by_project(detail)
        return content

    def _get_content_by_project(self, project):
        #  分支設定檢查
        branch_status = project.branch_check.status
        branch_issues = project.branch_check.issues

        block = f"🔸分支設定檢查 {branch_status.value}\n"
        for issue in branch_issues:
            block += f"    ❗{issue}\n"

        # Pipeline 檢查
        pipeline_status = project.pipeline_check.status
        pipeline_id = project.pipeline_check.pipeline_id
        pipeline_issues = project.pipeline_check.issues

        pipeline_id_str = f" (pipeline_id: {pipeline_id})" if pipeline_id else ""
        block += f"🔸Pipeline 檢查 {pipeline_status.value}{pipeline_id_str}\n"

        for issue in pipeline_issues:
            block += f"    ❗{issue}\n"

        # CI 設定檢查
        ci_status = project.ci_check.status
        ci_issues = project.ci_check.issues

        block += f"🔸CI 設定檢查 {ci_status.value}\n"

        for issue in ci_issues:
            if isinstance(issue, StageIssue):
                block += self.__format_stage_issues(issue.name, issue.issues)
            elif isinstance(issue, str) and issue:
                block += f"    ❗{issue}\n"

        return block + "\n"

    @staticmethod
    def __format_stage_issues(stage_name, issues):
        if not issues:
            return ""
        result = f"    ❗Stage: {stage_name} 設定異常\n"
        for issue in issues:
            result += f"        ・{issue}\n"
        return result
