from .client import Client
from typing import Dict


class API(Client):

    def get_jira_content(self, issue_key: str) -> Dict:
        url = self._get_url(f"issue/{issue_key}")
        response = self.get(url)
        return response["fields"]["description"]
