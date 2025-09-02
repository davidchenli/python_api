from pytest_mock import MockerFixture

from service.destruct import Destruct
from service.base import ApiInput
from repository.jira import API

sample_description = {
    "content": [
        {
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "專案列表"}
                            ]
                        },
                        {
                            "type": "bulletList",
                            "content": [
                                {
                                    "type": "listItem",
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {"type": "text", "text": "https://example.com/project1"}
                                            ]
                                        }
                                    ]
                                },
                                {
                                    "type": "listItem",
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {"type": "text", "text": "https://example.com/project2"}
                                            ]
                                        }
                                    ]
                                },
                                {
                                    "type": "listItem",
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "content": [
                                                {"type": "text", "text": "not-a-url"}
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ]
}


def test_get_project_list_full_parsing(mocker: MockerFixture):
    # 準備輸入資料
    data = ApiInput(
        issueId=123,
        issueKey="PROJ-456"
    )

    mocker.patch.object(
        API, 'get_jira_content',
        return_value=sample_description
    )

    issue_id, issue_key, project_list = Destruct().get_project_list(data)

    assert issue_id == 123
    assert issue_key == "PROJ-456"
    assert project_list == [
        "https://example.com/project1",
        "https://example.com/project2"
    ]
