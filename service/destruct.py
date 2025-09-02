import re
from typing import List, Tuple

from repository.jira import API
from .base import ApiInput


class Destruct:

    def __init__(self):
        self.api = API()

    def get_project_list(self, data: ApiInput) -> Tuple[int, str, List[str]]:
        issue_id = data.issueId
        issue_key = data.issueKey
        project_list = []
        try:
            description = self.api.get_jira_content(issue_key)
            project_list = self._get_from_text(description)
        except:
            pass
        return issue_id, issue_key, project_list

    @staticmethod
    def _get_from_text(description: dict) -> List[str]:
        project_list = []
        for content in description.get('content', []):
            if content.get("type") == 'bulletList':
                for item in content.get("content", []):
                    if item.get("type") == 'listItem':

                        item_check = False
                        for block in item.get("content", []):
                            block_type = block.get("type")
                            block_content = block.get("content")

                            if (block_type == "paragraph") and block_content:
                                check_dict = block_content[0]
                                if (check_dict.get("type") == "text") and ("專案列表" in check_dict.get("text", "")):
                                    item_check = True

                            if block_type == "bulletList" and item_check:
                                for url_block in block_content:
                                    if url_block.get("type") == "listItem":
                                        try:
                                            url_text = url_block["content"][0]["content"][0]["text"]
                                            if Destruct.is_valid_url(url_text):
                                                project_list.append(url_text)

                                        except (KeyError, IndexError):
                                            continue
        return [url for url in project_list if url]

    @staticmethod
    def is_valid_url(text: str) -> bool:
        URL_REGEX = re.compile(
            r'https?://'
            r'(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
            r'(?:[/?#][^\s]*)?'
        )
        return bool(URL_REGEX.match(text))
