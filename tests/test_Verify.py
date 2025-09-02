import pytest
from unittest.mock import Mock
from pytest_mock import MockerFixture
import pandas as pd

from service.base import Result, BranchIssue, PipelineIssue, CiIssue, ProjectReport, BranchCheck, PipelineCheck, \
    CICheck, StageIssue
from service.verify import Verify
from repository.gitlab import API


def test_execute_success_flow(mocker: MockerFixture, mock_gitlab_api: Mock):
    check_branch = mocker.patch.object(Verify, 'check_branch',
                                       return_value=(True, BranchCheck(status=Result.SUCCESS, issues=[])))
    check_pipeline = mocker.patch.object(Verify, 'check_pipeline',
                                         return_value=(True, PipelineCheck(status=Result.SUCCESS, issues=[])))
    check_yaml = mocker.patch.object(Verify, 'check_yaml',
                                     return_value=(True, CICheck(status=Result.SUCCESS, issues=[])))

    v = Verify()
    report = v.execute("http://gitlab.com/group/proj")

    assert isinstance(report, ProjectReport)
    assert report.summary == Result.SUCCESS
    check_branch.assert_called_once_with(123)
    check_pipeline.assert_called_once_with(123)
    check_yaml.assert_called_once_with(123, "example_project")


def test_execute_with_branch_warning(mocker: MockerFixture, mock_gitlab_api: Mock):
    mocker.patch.object(Verify, 'check_branch',
                        return_value=(False, BranchCheck(status=Result.WARNING, issues=["warn"])))
    mocker.patch.object(Verify, 'check_pipeline',
                        return_value=(True, PipelineCheck(status=Result.SUCCESS, issues=[])))
    mocker.patch.object(Verify, 'check_yaml',
                        return_value=(True, CICheck(status=Result.SUCCESS, issues=[])))

    v = Verify()
    report = v.execute("url")
    assert report.summary == Result.WARNING
    assert len(report.detail.branch_check.issues) == 1
    assert report.detail.branch_check.issues[0] == "warn"


def test_execute_project_not_found_sets_error(mocker: MockerFixture):
    mocker.patch.object(
        API, 'get_project_id',
        return_value=(None, None, None)
    )

    v = Verify()
    report = v.execute("url")
    assert report.summary == Result.ERROR
    assert report.detail == '無法解析專案或不存在'


def test_check_branch_permission_issue_detected(mock_gitlab_api: Mock):
    v = Verify()
    v.branch_setting = {"main": 40}
    v.default_branch = "main"

    status, check = v.check_branch(1)

    assert not status
    assert any(BranchIssue.PermissionIssue.value.split("{")[0] in issue for issue in check.issues)


def test_check_branch_success_when_settings_match(mock_gitlab_api: Mock):
    v = Verify()
    v.branch_setting = {"main": 30}
    v.default_branch = "main"

    status, check = v.check_branch(1)

    assert status
    assert check.status == Result.SUCCESS


#

def test_check_branch_reports_missing_branch(mock_gitlab_api: Mock):
    v = Verify()
    v.branch_setting = {"dev": 40}
    v.default_branch = "main"
    status, check = v.check_branch(1)

    assert not status
    assert any(BranchIssue.NotExist.value.split("{")[0] in issue for issue in check.issues)


def test_check_pipeline_all_success(mock_gitlab_api: Mock):
    v = Verify()

    status, check = v.check_pipeline(1)

    assert status
    assert check.status == Result.SUCCESS


def test_check_pipeline_with_failed_job(mocker: MockerFixture):
    v = Verify()
    mocker.patch.object(
        API, 'get_latest_pipeline',
        return_value={"id": 1, "status": "failed"}
    )
    mocker.patch.object(
        API, 'get_pipeline_jobs',
        return_value=pd.DataFrame({"stage": "build", "status": "failed", "name": "build_job"}, index=[0])
    )

    status, check = v.check_pipeline(1)

    assert not status
    assert any(PipelineIssue.JobError.value.split("{")[0] in issue for issue in check.issues)


def test_check_pipeline_not_found_sets_error(mocker: MockerFixture):
    v = Verify()
    mocker.patch.object(
        API, 'get_latest_pipeline',
        return_value={}
    )

    status, check = v.check_pipeline(1)

    assert not status
    assert check.status == Result.ERROR


@pytest.fixture
def yaml_base_config():
    return {
        "yaml_name": ".gitlab-ci.yml",
        "stages": {"stage_seq": ["test", "coverage", "build", "deploy"], "ignore_last_seq": ["deploy"]},
        "test": {"default_setting": {"main": ["manual"]}, "exclude_branches": [], "check_variable_list": []},
        "coverage": {"default_setting": {"main": ["manual"]}, "exclude_branches": []},
        "build": {"default_setting": {"main": ["manual"]}, "exclude_branches": []},
        "deploy": {"default_setting": {"main": ["manual"]}, "exclude_branches": []},
    }


def test_check_yaml_all_passes(mocker: MockerFixture, yaml_base_config: MockerFixture):
    merged_yaml = {
        "stages": ["test", "coverage", "build", "deploy"],
        "job_test": {"stage": "test", "when": "manual", "script": ["test"]},
        "coverage": {"stage": "coverage", "when": "manual", "coverage": "regex"},
        "job_build": {"stage": "build", "when": "manual"},
        "job_deploy": {"stage": "deploy", "when": "manual"},
    }

    mocker.patch.object(Verify, '_get_ci_yaml', return_value=merged_yaml)
    mocker.patch("repository.text.get_rules", return_value=[{"tree": {}, "when": "manual"}])
    mocker.patch("repository.text.has_ignore_test", return_value=True)

    v = Verify()
    v.yaml_config = yaml_base_config
    status, check = v.check_yaml(project_id=1, project_name="proj")

    assert status
    assert isinstance(check, CICheck)
    assert check.status == Result.SUCCESS
    assert any(isinstance(issue, StageIssue) for issue in check.issues)


def test_check_yaml_detects_stage_order_problem(mocker: MockerFixture, yaml_base_config: MockerFixture):
    merged_yaml = {"stages": ["build", "test", "deploy"]}
    mocker.patch.object(
        Verify, '_get_ci_yaml', return_value=merged_yaml
    )

    v = Verify()
    v.yaml_config = yaml_base_config

    status, check = v.check_yaml(1, "proj")

    assert not status
    assert any(CiIssue.StageError.value in issue for issue in check.issues)


def test_check_yaml_error_when_yaml_missing(mocker: MockerFixture, yaml_base_config: MockerFixture):
    mocker.patch.object(
        Verify, '_get_ci_yaml', side_effect=Exception("no file")
    )

    v = Verify()
    v.yaml_config = yaml_base_config

    status, check = v.check_yaml(1, "proj")

    assert not status
    assert check.status == Result.ERROR
