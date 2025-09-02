import pytest
import pandas as pd
from unittest.mock import Mock
from pytest_mock import MockerFixture

from repository.gitlab import API


@pytest.fixture
def mock_gitlab_api(mocker: MockerFixture) -> Mock:
    get_project_id = mocker.patch.object(
        API, 'get_project_id',
        return_value=("example_project", 123, "originmain")
    )

    get_protected_branches = mocker.patch.object(
        API, 'get_protected_branches',
        return_value=[
            {"name": "main", "push_access_levels": [{"access_level": 40}],
             "merge_access_levels": [{"access_level": 30}]}
        ]
    )

    get_branch = mocker.patch.object(
        API, 'get_branch',
        return_value={"name": "main"}
    )

    get_latest_pipeline = mocker.patch.object(
        API, 'get_latest_pipeline',
        return_value={"id": 1, "status": "success"}
    )

    get_pipeline_jobs = mocker.patch.object(
        API, 'get_pipeline_jobs',
        return_value=pd.DataFrame([
            {"stage": "coverage", "status": "manual", "name": "cov_job"},
            {"stage": "build", "status": "success", "name": "build_job"}
        ])
    )

    get_ci_file = mocker.patch.object(
        API, 'get_ci_file',
        return_value={
            "content": "image: python:3.9\n"
        }
    )

    api_mock = Mock()
    api_mock.attach_mock(get_project_id, "GetProjectId")
    api_mock.attach_mock(get_branch, "GetBranch")
    api_mock.attach_mock(get_protected_branches, "GetProtectedBranches")
    api_mock.attach_mock(get_latest_pipeline, "GetLatestPipeline")
    api_mock.attach_mock(get_pipeline_jobs, "GetPipelineJobs")
    api_mock.attach_mock(get_ci_file, "GetCIFile")

    return api_mock
