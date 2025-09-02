from .client import Client

import base64
import pandas as pd
import yaml
from typing import Tuple, Dict
from urllib.parse import quote


class GitLabCILoader(yaml.SafeLoader):
    pass


def unknown_constructor(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    else:
        return None


GitLabCILoader.add_multi_constructor('', unknown_constructor)


class API(Client):

    def get_project_id(self, project_name: str) -> Tuple[str, int, str]:
        proj_enc = quote(project_name, safe="")
        url = self._get_url(f"projects/{proj_enc}")
        response = self.get(url)
        return response.get("name"), response.get("id"), response.get("default_branch")

    def get_protected_branches(self, project_id: int) -> Dict:
        url = self._get_url(f"projects/{project_id}/protected_branches")
        response = self.get(url)
        return response

    def get_branch(self, project_id: int, branch: str) -> Dict:
        url = self._get_url(f"/projects/{project_id}/repository/branches/{branch}")
        response = self.get(url)
        return response

    def get_latest_pipeline(self, project_id: int, branch: str) -> Dict:
        url = self._get_url(f"projects/{project_id}/pipelines/latest?ref={branch}")
        response = self.get(url)
        return response

    def get_pipeline_jobs(self, project_id: int, pipeline_id: int) -> pd.DataFrame:
        url = self._get_url(f"projects/{project_id}/pipelines/{pipeline_id}/jobs")
        response = self.get(url)
        return pd.DataFrame(response)

    def get_ci_file(self, project_id: int, file_path: str, branch: str)-> Dict:
        file_enc = quote(file_path, safe="")
        url = self._get_url(f"projects/{project_id}/repository/files/{file_enc}?ref={branch}")
        response = self.get(url)
        content = response.get("content", "")
        decoded_str = base64.b64decode(content).decode("utf-8")
        return yaml.load(decoded_str, Loader=GitLabCILoader)
