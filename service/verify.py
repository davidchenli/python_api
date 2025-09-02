from typing import Tuple, List, Dict
from collections import deque
from urllib.parse import urlparse

from config import config

from repository.gitlab import API
from repository.text import resolve_reference_path, extend_rule, get_rules, BranchConditionEvaluator, has_ignore_test
from .base import ProjectReport, BranchCheck, PipelineCheck, CICheck, StageIssue, Result, BranchIssue, PipelineIssue, \
    CiIssue


class Verify:
    def __init__(self):
        self.gitlab_api = API()
        self.evaluator = BranchConditionEvaluator()

        self.yaml_config = config.yaml_config
        self.default_branch = config.default_branch
        self.branch_setting = config.level_setting

    def execute(self, project_url: str) -> ProjectReport:
        project_name, project_id, _ = self.get_project_id(project_url)
        if not project_id:
            return ProjectReport(url=project_url, summary=Result.ERROR, detail="無法解析專案或不存在")

        branch_status, branch_check = self.check_branch(project_id)
        pipeline_status, pipeline_check = self.check_pipeline(project_id)
        ci_status, ci_check = self.check_yaml(project_id, project_name)

        if all([branch_status, pipeline_status, ci_status]):
            summary = Result.SUCCESS
        else:
            summary = Result.WARNING

        output = {
            "url": project_url,
            "name": project_name,
            "summary": summary,
            "detail": {
                "branch_check": branch_check,
                "pipeline_check": pipeline_check,
                "ci_check": ci_check
            }
        }
        return ProjectReport(**output)

    def get_project_id(self, project_url: str) -> Tuple[str, int, str]:
        parsed_url = urlparse(project_url)
        project_name = parsed_url.path.lstrip("/").replace(".git", "").strip()
        return self.gitlab_api.get_project_id(project_name)

    def check_branch(self, project_id: int) -> Tuple[bool, BranchCheck]:
        protected_branches = self.gitlab_api.get_protected_branches(project_id)
        expected_branches = list(self.branch_setting.keys())

        missing_branches = expected_branches.copy()
        permission_issue_branches = []

        for branch in protected_branches:
            branch_name = branch["name"]
            if branch_name not in expected_branches:
                continue

            required_level = self.branch_setting[branch_name]

            access_level = branch["push_access_levels"][0]['access_level']
            merge_level = branch["merge_access_levels"][0]['access_level']

            if access_level < required_level or merge_level < required_level:
                permission_issue_branches.append(branch_name)

            missing_branches.remove(branch_name)

        default_branch_response = self.gitlab_api.get_branch(project_id, self.default_branch)
        if default_branch_response.get("name") != self.default_branch:
            if self.default_branch not in missing_branches:
                missing_branches.append(self.default_branch)

        detail_list = []

        if missing_branches:
            detail_list.append(BranchIssue.NotExist.value.format(branches="、".join(missing_branches)))

        if permission_issue_branches:
            detail_list.append(BranchIssue.PermissionIssue.value.format(branches="、".join(permission_issue_branches)))

        check_status = len(detail_list) == 0
        check_result = Result.SUCCESS if check_status else Result.WARNING
        return check_status, BranchCheck(status=check_result, issues=detail_list)

    def check_pipeline(self, project_id: int) -> Tuple[bool, PipelineCheck]:
        pipeline = self.gitlab_api.get_latest_pipeline(project_id, self.default_branch)
        pipeline_id = pipeline.get('id')
        if not pipeline_id:
            return False, PipelineCheck(status=Result.ERROR, issues=[PipelineIssue.NotFoundError.value])

        pipeline_status = pipeline.get('status')
        pipeline_check = pipeline_status in ["success", "manual"]

        detail_list = []
        if not pipeline_check:
            detail_list.append(PipelineIssue.PipelineError.value.format(pipeline_status=pipeline_status))

        job_df = self.gitlab_api.get_pipeline_jobs(project_id, pipeline_id)
        coverage_flag = (job_df["stage"] == "coverage") & (job_df["status"] == "manual")
        other_flag = (job_df["stage"] != "coverage") & (job_df["status"] == "success")

        valid_jobs_condition = coverage_flag | other_flag
        issue_job_df = job_df[~ valid_jobs_condition]

        for _, row in issue_job_df.iterrows():
            detail_list.append(PipelineIssue.JobError.value.format(job_name=row["name"], job_status=row["status"]))

        check_status = len(detail_list) == 0
        check_result = Result.SUCCESS if check_status else Result.WARNING
        return check_status, PipelineCheck(status=check_result, issues=detail_list, pipeline_id=pipeline_id)

    def check_yaml(self, project_id: int, project_name: str) -> Tuple[bool, CICheck]:

        yaml_name = self.yaml_config["yaml_name"]
        try:
            merged_yaml = self._get_ci_yaml(project_id, project_name, self.default_branch, yaml_name)
        except:
            return False, CICheck(status=Result.ERROR, issues=[CiIssue.YamlNotFoundError.value])

        stage_status, stage_issue = self._check_stages_order(merged_yaml)
        test, coverage, build, deploy = self._get_jobs_from_stage(merged_yaml)

        test_status, test_issue = self._check_test(test, merged_yaml)
        cov_status, cov_issue = self._check_coverage(coverage, merged_yaml)
        build_status, build_issue = self._check_build(build, merged_yaml)
        deploy_status, deploy_issue = self._check_deploy(deploy, merged_yaml)

        detail_list = [stage_issue, test_issue, cov_issue, build_issue, deploy_issue]

        check_status = all([stage_status, test_status, cov_status, build_status, deploy_status])
        check_result = Result.SUCCESS if check_status else Result.WARNING
        return check_status, CICheck(status=check_result, issues=detail_list)

    def _get_ci_yaml(self, project_id: int, project_name: str, branch: str, yaml_file: str) -> dict:
        yaml_docs = self.__get_all_yaml_recursive(
            [(project_id, project_name, branch, yaml_file)]
        )

        merged_yaml = {}
        for doc in yaml_docs:
            merged_yaml.update(doc)

        return merged_yaml

    def _check_stages_order(self, main_yaml: dict) -> Tuple[bool, str]:

        stages_setting = self.yaml_config["stages"]

        stage_seq = stages_setting["stage_seq"]
        ignore_last_seq = stages_setting["ignore_last_seq"]

        test_list = main_yaml.get("stages")
        if not test_list:
            return False, CiIssue.StageMissing.value

        filtered = [step for step in test_list if step in stage_seq]

        if not set(filtered[-len(ignore_last_seq):]).issubset(ignore_last_seq):
            check_status = False
        else:
            ref_index = {name: i for i, name in enumerate(stage_seq)}
            before_last = [step for step in filtered if step not in ignore_last_seq]
            check_status = before_last == sorted(before_last, key=lambda x: ref_index[x])

        issue = ""
        if not check_status:
            issue = CiIssue.StageError.value
        return check_status, issue

    @staticmethod
    def _get_jobs_from_stage(merged_yaml: dict) -> Tuple[List, List, List, List]:
        test = []
        coverage = []
        build = []
        deploy = []

        for job_name, job_item in merged_yaml.items():
            if isinstance(job_item, dict) and "." not in job_name:
                value = extend_rule(merged_yaml, job_item)
                stage = value.get("stage")

                output = {job_name: value}
                if stage == "test":
                    test.append(output)
                elif stage == "coverage":
                    coverage.append(output)
                elif stage == "build":
                    build.append(output)
                elif stage == "deploy":
                    deploy.append(output)

        return test, coverage, build, deploy

    def _check_test(self, test: list, merged_yaml: dict) -> Tuple[bool, StageIssue]:

        stage = "test"
        stage_setting = self.yaml_config[stage]
        default_setting = stage_setting["default_setting"]
        exclude_branches = stage_setting["exclude_branches"]
        check_variable_list = stage_setting["check_variable_list"]

        matched_branches = []
        invalid_job_settings = []
        unexpected_branch_jobs = []

        ignore_result = False

        if not test:
            detail_list = [CiIssue.StageNotFoundError.value]
            check_status = False
        else:
            detail_list = []
            for job in test:
                job_name, job_dict = next(iter(job.items()))
                default_when = job_dict.get("when", config.default_when)
                rules = get_rules(job_dict, merged_yaml, default_when, stage)

                matched_branch, invalid_job_setting, unexpected_branch_job = self.__check_rules(job_name, rules,
                                                                                                default_setting,
                                                                                                exclude_branches)
                matched_branches += matched_branch
                invalid_job_settings += invalid_job_setting
                unexpected_branch_jobs += unexpected_branch_job

                before_script_list = job_dict.get("before_script", [])
                script_list = job_dict.get("script", [])
                check_script_list = before_script_list + script_list

                if check_script_list:
                    check_query = []
                    wait_query = check_script_list.copy()

                    while wait_query:
                        item = wait_query.pop(0)
                        if isinstance(item, str):
                            check_query.append(item)
                        elif isinstance(item, list):
                            item_output = resolve_reference_path(item, merged_yaml)
                            if isinstance(item_output, list):
                                wait_query += item_output
                            else:
                                wait_query += [item_output]

                    for query in check_query:
                        if has_ignore_test(query, check_variable_list):
                            ignore_result = True

            if not ignore_result:
                detail_list.append(CiIssue.IgnoreNotSetError.value)

            missing_branches = set(default_setting.keys()) - set(matched_branches)
            check_status, detail_list = self.__format_report(detail_list, missing_branches, invalid_job_settings,
                                                             unexpected_branch_jobs)

        return check_status, StageIssue(name=stage, issues=detail_list)

    def _check_coverage(self, coverage: list, merged_yaml: dict) -> Tuple[bool, StageIssue]:

        stage = "coverage"
        stage_setting = self.yaml_config[stage]
        default_setting = stage_setting["default_setting"]
        exclude_branches = stage_setting["exclude_branches"]

        matched_branches = []
        invalid_job_settings = []
        unexpected_branch_jobs = []

        if not coverage:
            detail_list = [CiIssue.StageNotFoundError.value]
            check_status = False
        else:
            detail_list = []
            for job in coverage:
                job_name, job_dict = next(iter(job.items()))
                default_when = job_dict.get("when", config.default_when)
                rules = get_rules(job_dict, merged_yaml, default_when, stage)

                matched_branch, invalid_job_setting, unexpected_branch_job = self.__check_rules(job_name, rules,
                                                                                                default_setting,
                                                                                                exclude_branches)
                matched_branches += matched_branch
                invalid_job_settings += invalid_job_setting
                unexpected_branch_jobs += unexpected_branch_job

            final_cov = coverage[0].get("coverage")
            if (final_cov is None) or len(coverage) > 1:
                detail_list.append(CiIssue.JobNameError.value)

            missing_branches = set(default_setting.keys()) - set(matched_branches)
            check_status, detail_list = self.__format_report(detail_list, missing_branches, invalid_job_settings,
                                                             unexpected_branch_jobs)

        return check_status, StageIssue(name="coverage", issues=detail_list)

    def _check_build(self, build: list, merged_yaml: dict) -> Tuple[bool, StageIssue]:

        stage = "build"
        stage_setting = self.yaml_config[stage]
        default_setting = stage_setting["default_setting"]
        exclude_branches = stage_setting["exclude_branches"]

        matched_branches = []
        invalid_job_settings = []
        unexpected_branch_jobs = []

        if not build:
            detail_list = [CiIssue.StageNotFoundError.value]
            check_status = False
        else:
            detail_list = []
            for job in build:
                job_name, job_dict = next(iter(job.items()))
                default_when = job_dict.get("when", config.default_when)
                rules = get_rules(job_dict, merged_yaml, default_when, stage)

                matched_branch, invalid_job_setting, unexpected_branch_job = self.__check_rules(job_name, rules,
                                                                                                default_setting,
                                                                                                exclude_branches)
                matched_branches += matched_branch
                invalid_job_settings += invalid_job_setting
                unexpected_branch_jobs += unexpected_branch_job

            missing_branches = set(default_setting.keys()) - set(matched_branches)
            check_status, detail_list = self.__format_report(detail_list, missing_branches, invalid_job_settings,
                                                             unexpected_branch_jobs)

        return check_status, StageIssue(name=stage, issues=detail_list)

    def _check_deploy(self, deploy: list, merged_yaml: dict) -> Tuple[bool, StageIssue]:

        stage = "deploy"
        stage_setting = self.yaml_config[stage]
        default_setting = stage_setting["default_setting"]
        exclude_branches = stage_setting["exclude_branches"]

        matched_branches = []
        invalid_job_settings = []
        unexpected_branch_jobs = []

        if not deploy:
            detail_list = [CiIssue.StageNotFoundError.value]
            check_status = False
        else:
            detail_list = []
            for job in deploy:
                job_name, job_dict = next(iter(job.items()))
                default_when = job_dict.get("when", config.default_when)
                rules = get_rules(job_dict, merged_yaml, default_when, stage)

                matched_branch, invalid_job_setting, unexpected_branch_job = self.__check_rules(job_name, rules,
                                                                                                default_setting,
                                                                                                exclude_branches)
                matched_branches += matched_branch
                invalid_job_settings += invalid_job_setting
                unexpected_branch_jobs += unexpected_branch_job

            missing_branches = set(default_setting.keys()) - set(matched_branches)
            check_status, detail_list = self.__format_report(detail_list, missing_branches, invalid_job_settings,
                                                             unexpected_branch_jobs)

        return check_status, StageIssue(name=stage, issues=detail_list)

    def __get_all_yaml_recursive(self, tasks: list[tuple[int, str, str, str]]) -> List:
        all_yaml_docs = []
        visited = set()
        tasks_checking = deque(tasks)

        while tasks_checking:
            project_id, project_name, branch, yaml_file = tasks_checking.popleft()

            key = f"{project_id}:{branch}:{yaml_file}"
            if key in visited:
                continue
            visited.add(key)

            current_yaml = self.gitlab_api.get_ci_file(project_id, yaml_file, branch)

            all_yaml_docs.append(current_yaml)

            include_list = current_yaml.get("include", [])
            if not isinstance(include_list, list):
                include_list = [include_list]

            for include in include_list:
                file_info = self.__get_file_from_include(project_id, project_name, branch, include)

                for f in file_info["files"]:
                    if "${CI_PROJECT_TITLE}" in f:
                        project_title = project_name
                        f = f.replace("${CI_PROJECT_TITLE}", project_title)
                    tasks_checking.appendleft((file_info["project_id"], file_info["branch"], file_info["branch"], f))

        return all_yaml_docs

    def __get_file_from_include(self, project_id: int, project_name: str, ref: str, include_item: dict | str) -> Dict:
        if isinstance(include_item, str):
            return {
                "project_id": project_id,
                "project_name": project_name,
                "branch": ref,
                "files": [include_item.lstrip("/")]
            }
        elif isinstance(include_item, dict):
            if "project" in include_item:
                project_name, project_id, default_branch = self.gitlab_api.get_project_id(include_item["project"])
                branch = include_item.get("ref", default_branch)
                files = include_item["file"] if isinstance(include_item["file"], list) else [include_item["file"]]
                return {
                    "project_id": project_id,
                    "project_name": project_name,
                    "branch": branch,
                    "files": [f.lstrip("/") for f in files]
                }
        raise ValueError(f"Unsupported include format: {include_item}")

    def __check_rules(self, job_name: str, rules: list, default_setting: dict, exclude_branches: set) -> Tuple[
        List, List, List]:
        matched_branch, invalid_job_setting, unexpected_branch_job = [], [], []
        for branch, allowed_whens in default_setting.items():
            for item in rules:
                if self.evaluator.evaluate(item["tree"], branch):
                    matched_branch.append(branch)
                    when = item["when"]
                    if when not in allowed_whens:
                        invalid_job_setting.append({
                            "job_name": job_name,
                            "branch_name": branch,
                            "setting": when,
                            "expect_setting": "/".join(allowed_whens)
                        })
                    break

        for exclude_branch in exclude_branches:
            for rule_item in rules:
                if self.evaluator.evaluate(rule_item["tree"], exclude_branch):
                    when = rule_item["when"]
                    if when not in ["never"]:
                        unexpected_branch_job.append({
                            "job_name": job_name,
                            "branch_name": exclude_branch,
                            "setting": when
                        })
                    break

        return matched_branch, invalid_job_setting, unexpected_branch_job

    @staticmethod
    def __format_report(detail_list: list, missing_branches: set, invalid_job_settings: list,
                        unexpected_branch_jobs: list) -> Tuple[bool, List[str]]:
        for issue_branch in missing_branches:
            detail_list.append(CiIssue.MissingBranchError.value.format(branch_name=issue_branch))

        for issue in invalid_job_settings:
            detail_list.append(CiIssue.JobError.value.format(**issue))

        for issue in unexpected_branch_jobs:
            detail_list.append(CiIssue.ExtraBranchError.value.format(**issue))

        check_status = len(detail_list) == 0
        return check_status, detail_list
