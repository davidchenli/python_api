import requests
import json
from typing import Optional, Dict

from .retry import retry
from config import config


class Client:
    def __init__(self):
        self._url = f"{config.gitlab_uri}/api/v4"
        self._token = config.gitlab_token

        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def _get_url(self, path: str) -> str:
        return f'{self._url}/{path}'

    @retry(max_retries=3, retry_delay=1)
    def get(self, url: str, params: Optional[Dict] = None) -> Dict:
        headers = {"PRIVATE-TOKEN": self._token}
        response = self._session.get(
            url=url,
            headers=headers,
            params=params,
        )
        return self._check_and_decode_response(response)

    @staticmethod
    def _check_and_decode_response(response: requests.Response) -> Dict:

        result = {}
        if response.status_code in [403, 404]:
            result = {"description": "data not found"}

        elif not response.ok:
            response.raise_for_status()
        else:
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                raise Exception(f"Failed to decode JSON response: {e}")
        return result
