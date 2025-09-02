import re
import pytest
from freezegun import freeze_time
from pytest_mock import MockerFixture

from service.report_format import ReportFormat
from service.base import Result, BranchCheck, PipelineCheck, CICheck, StageIssue, ProjectReport, ProjectDetail


@pytest.fixture
def sample_projects():
    branch_check = BranchCheck(status=Result.ERROR, issues=["分支命名錯誤"])
    pipeline_check = PipelineCheck(status=Result.WARNING, pipeline_id=123, issues=["Pipeline 錯誤"])
    ci_check = CICheck(status=Result.SUCCESS, issues=[StageIssue(name="build", issues=["timeout 過短"]), "未設定變數"])

    project_detail = ProjectDetail(
        branch_check=branch_check,
        pipeline_check=pipeline_check,
        ci_check=ci_check
    )

    p1 = ProjectReport(url="http://gitlab.com/p1", name="Project1", summary=Result.ERROR, detail="找不到設定檔")
    p2 = ProjectReport(url="http://gitlab.com/p2", name="Project2", summary=Result.WARNING, detail=project_detail)
    p3 = ProjectReport(url="http://gitlab.com/p3", name="Project3", summary=Result.SUCCESS, detail=project_detail)
    return [p1, p2, p3]


def test_generate_overall_result_counts(sample_projects: MockerFixture):
    rf = ReportFormat()
    summary, counts, sorted_projects = rf.generate_overall_result(sample_projects)

    assert summary == Result.ERROR
    assert counts[Result.ERROR] == 1
    assert counts[Result.WARNING] == 1
    assert counts[Result.SUCCESS] == 1
    assert sorted_projects[0].summary == Result.ERROR


def test_generate_overall_result_empty():
    rf = ReportFormat()
    summary, detail, projects = rf.generate_overall_result([])

    assert summary == Result.ERROR
    assert detail == "未找到 專案 URL"
    assert projects == []


@freeze_time("2024-10-15 10:00:00")
def test_get_title_error_message():
    rf = ReportFormat()
    title = rf.get_title(Result.ERROR, "未找到 專案 URL")
    assert title == '[RMS 簽核模組] 專案設定檢查 ：錯誤 ❌\n\n' \
                    '📅 檢查時間：2024-10-15 10:00:00\n\n' \
                    '❌ 未找到 專案 URL\n\n'


@freeze_time("2024-10-15 10:00:00")
def test_get_title_counts():
    rf = ReportFormat()
    detail = {Result.SUCCESS: 2, Result.WARNING: 1, Result.ERROR: 0}
    title = rf.get_title(Result.SUCCESS, detail)
    assert title == '[RMS 簽核模組] 專案設定檢查 ：正常 ✅\n\n' \
                    '📅 檢查時間：2024-10-15 10:00:00\n\n' \
                    '✅ 正常專案：2\n' \
                    '⚠️ 異常專案：1\n' \
                    '❌ 錯誤專案：0\n\n'


def test_get_content_error_project():
    rf = ReportFormat()
    p_error = ProjectReport(
        url="http://gitlab.com/p1",
        name="Project1",
        summary=Result.ERROR,
        detail="缺少設定檔"
    )
    content = rf.get_content(p_error)
    assert content == "💼 專案：http://gitlab.com/p1 錯誤 ❌\n" \
                      "🔷 專案名稱：Project1\n❌ 缺少設定檔\n\n"


def test_get_content_normal_project():
    rf = ReportFormat()

    branch_check = BranchCheck(status=Result.SUCCESS)
    pipeline_check = PipelineCheck(status=Result.SUCCESS, issues=[], pipeline_id=999)
    ci_check = CICheck(status=Result.WARNING, issues=[StageIssue(name="deploy", issues=["缺少 job"]), "未設定變數"])

    project_detail = ProjectDetail(
        branch_check=branch_check,
        pipeline_check=pipeline_check,
        ci_check=ci_check
    )

    p = ProjectReport(
        url="http://gitlab.com/p2",
        name="Project2",
        summary=Result.SUCCESS,
        detail=project_detail
    )

    content = rf.get_content(p)

    assert content == "💼 專案：http://gitlab.com/p2 正常 ✅\n" \
                      "🔷 專案名稱：Project2\n🔸分支設定檢查 正常 ✅\n" \
                      "🔸Pipeline 檢查 正常 ✅ (pipeline_id: 999)\n" \
                      "🔸CI 設定檢查 異常 ⚠️\n" \
                      "    ❗Stage: deploy 設定異常\n" \
                      "        ・缺少 job\n" \
                      "    ❗未設定變數\n\n"


@freeze_time("2024-10-15 10:00:00")
def test_generate_report_integration(sample_projects):
    rf = ReportFormat()
    report_text = rf.generate_report(sample_projects)
    expected_report = ("[RMS 簽核模組] 專案設定檢查 ：錯誤 ❌\n\n"
                       "📅 檢查時間：2024-10-15 10:00:00\n\n"
                       "✅ 正常專案：1\n"
                       "⚠️ 異常專案：1\n"
                       "❌ 錯誤專案：1\n\n"
                       "💼 專案：http://gitlab.com/p1 錯誤 ❌\n"
                       "🔷 專案名稱：Project1\n"
                       "❌ 找不到設定檔\n\n\n"
                       "💼 專案：http://gitlab.com/p2 異常 ⚠️\n"
                       "🔷 專案名稱：Project2\n🔸分支設定檢查 錯誤 ❌\n"
                       "    ❗分支命名錯誤\n"
                       "🔸Pipeline 檢查 異常 ⚠️ (pipeline_id: 123)\n"
                       "    ❗Pipeline 錯誤\n"
                       "🔸CI 設定檢查 正常 ✅\n"
                       "    ❗Stage: build 設定異常\n"
                       "        ・timeout 過短\n"
                       "    ❗未設定變數\n\n\n"
                       "💼 專案：http://gitlab.com/p3 正常 ✅\n"
                       "🔷 專案名稱：Project3\n🔸分支設定檢查 錯誤 ❌\n"
                       "    ❗分支命名錯誤\n"
                       "🔸Pipeline 檢查 異常 ⚠️ (pipeline_id: 123)\n"
                       "    ❗Pipeline 錯誤\n"
                       "🔸CI 設定檢查 正常 ✅\n"
                       "    ❗Stage: build 設定異常\n"
                       "        ・timeout 過短\n"
                       "    ❗未設定變數\n\n")

    assert report_text == expected_report
    date_match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", report_text)
    assert date_match is not None
