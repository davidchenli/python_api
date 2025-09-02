import json
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

yaml_config = {
    "yaml_name": ".gitlab-ci.yml",
    "stages": {
        "stage_seq": ['lint', 'test', 'build', 'coverage', 'deploy'],
        "ignore_last_seq": ['coverage', 'deploy']
    },
    "test": {
        "default_setting": {
            'hotfix': ['manual'],
            'prod-*': ['manual'],
            'staging-*': ['on_success', 'always'],
            'originmain': ['on_success', 'always']
        },
        "exclude_branches": set(),
        "check_variable_list": ["IGNORE_TEST"]
    },
    "coverage": {
        "default_setting": {'originmain': ['manual']},
        "exclude_branches": set(['release-*', 'prod-*', 'staging-*']),
    },
    "build": {
        "default_setting": {
            'originmain': ['on_success', 'always'],
            'hotfix': ['on_success', 'always'],
            'prod-*': ['on_success', 'always'],
            'staging-*': ['on_success', 'always']
        },
        "exclude_branches": set(),
    },
    "deploy": {
        "default_setting": {'hotfix': ['manual'], 'prod-*': ['manual'], 'staging-*': ['manual']},
        "exclude_branches": set(["originmain"]),
    }
}


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    gitlab_token: str = ""
    jira_token: str = ""
    gitlab_uri: str = "https://swissknife.vip"
    default_branch: str = "originmain"
    level_setting: dict = {"prod-*": 30, "originmain": 30, "staging-*": 30}
    default_when: str = "on_success"
    yaml_config: dict = yaml_config


config = Config()

if __name__ == '__main__':
    result = config.model_dump(
        mode='json',
    )
    print(json.dumps(result, indent=2))
