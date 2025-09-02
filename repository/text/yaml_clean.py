import re
from enum import Enum
from copy import deepcopy
from collections import deque
from typing import Any, Dict, List, Tuple, Union


class RuleType(Enum):
    ALL = {"match": {"CI_COMMIT_BRANCH": ".*"}}
    NO = {"eq": {"CI_COMMIT_BRANCH": ""}}
    SKIP = {}


class BranchConditionParser:

    def parse(self, expr: str, stage: str) -> Dict:
        self.stage = stage
        expr = expr.strip()
        if not expr:
            return RuleType.SKIP.value
        return self._parse(expr)

    def _parse(self, expr: str) -> Dict:
        expr = expr.strip()
        if expr.startswith("(") and expr.endswith(")"):
            depth = 0
            i = 0
            str_len = len(expr)
            while i < str_len:
                if expr[i] == '(':
                    depth += 1
                elif expr[i] == ')':
                    depth -= 1
                i += 1
                if depth == 0 and i != str_len:
                    operator, parts = self._split_by_operator(expr)
                    return self._combine_parts(operator, parts)
            return self._parse(expr[1:-1])

        if "||" in expr or "&&" in expr:
            operator, parts = self._split_by_operator(expr)
            return self._combine_parts(operator, parts)
        return self._parse_single_condition(expr)

    def _combine_parts(self, operator: str, parts: List[str]) -> Dict:
        if operator == "||":
            return {"or": [self._parse(p) for p in parts]}
        elif operator == "&&":
            return {"and": [self._parse(p) for p in parts]}

    @staticmethod
    def _split_by_operator(expr: str) -> Tuple[str, List[str]]:
        parts, current = [], ""
        depth = 0
        i = 0
        operator = None
        while i < len(expr):
            if expr[i] == '(':
                depth += 1
            elif expr[i] == ')':
                depth -= 1
            if depth == 0 and expr[i:i + 2] in ["||", "&&"]:
                if operator and operator != expr[i:i + 2]:
                    raise Exception("混合運算符錯誤")
                operator = operator or expr[i:i + 2]
                parts.append(current.strip())
                current = ""
                i += 2
                continue
            current += expr[i]
            i += 1
        if current:
            parts.append(current.strip())
        return operator, parts

    def _parse_single_condition(self, cond: str) -> Dict:
        key = None
        value = ""

        regex_patterns = [
            (r'\$(CI_COMMIT_REF_NAME|CI_COMMIT_BRANCH)\s*=~\s*(?:"/(.+)/"|/(.+)/|"(.+)")', "match"),
            (r'\$(CI_COMMIT_REF_NAME|CI_COMMIT_BRANCH)\s*!~\s*(?:"/(.+)/"|/(.+)/|"(.+)")', "not_match"),
            (r'\$(CI_COMMIT_REF_NAME|CI_COMMIT_BRANCH)\s*==\s*["\'](.*?)["\']', "eq"),
            (r'\$(CI_COMMIT_REF_NAME|CI_COMMIT_BRANCH)\s*!=\s*["\'](.*?)["\']', "neq")
        ]

        for pattern_str, type_key in regex_patterns:
            pattern = re.compile(pattern_str)
            match_obj = re.match(pattern, cond)
            if match_obj:
                key = type_key
                value = next((g for g in match_obj.groups()[1:] if g), None)
                return {key: {"CI_COMMIT_BRANCH": value}}

        m = re.match(r'\$(\w+)\s*(==|=~|!=|!~)\s*(.+)', cond)
        if m:
            var_name, operator, raw_value = m.group(1), m.group(2), m.group(3)
            operator_type = operator in ["==", "=~"]
            value = self._normalize_value(raw_value)
            return self._parse_special_var(var_name, value, operator_type)
        return RuleType.SKIP.value

    @staticmethod
    def _normalize_value(raw_value: str) -> str:
        if re.match(r"^(['\"]).*\1$", raw_value):
            return raw_value[1:-1]
        elif re.match(r"^/.+/[a-zA-Z]*$", raw_value):
            return raw_value.strip("/").split("/")[0]
        else:
            return raw_value

    def _parse_special_var(self, var_name: str, value: str, operator_type: bool) -> Dict:
        match var_name:
            case "RMS":
                if value == "false":
                    return RuleType.NO.value if operator_type else RuleType.ALL.value
                return RuleType.ALL.value if operator_type else RuleType.NO.value
            case "CI_PIPELINE_SOURCE":
                if value in ["push", "web"]:
                    return RuleType.ALL.value if operator_type else RuleType.NO.value
                return RuleType.NO.value if operator_type else RuleType.ALL.value
            case "CI_JOB_STAGE":
                if value == self.stage:
                    return RuleType.ALL.value if operator_type else RuleType.NO.value
                return RuleType.NO.value if operator_type else RuleType.ALL.value
            case "CI_JOB_NAME":
                if self.stage in value:
                    return RuleType.SKIP.value
                return RuleType.NO.value
            case "CI_ACTION":
                return RuleType.SKIP.value
            case _:
                return RuleType.NO.value


class BranchConditionEvaluator:
    def evaluate(self, logic: Dict[str, Any], branch: str) -> bool:

        if not logic:
            return False

        if "and" in logic:
            parts = [cond for cond in logic["and"] if cond]
            return all(self.evaluate(cond, branch) for cond in parts) if parts else False
        elif "or" in logic:
            parts = [cond for cond in logic["or"] if cond]
            return any(self.evaluate(cond, branch) for cond in parts) if parts else False
        elif "match" in logic:
            return re.match(logic["match"]["CI_COMMIT_BRANCH"], branch) is not None
        elif "not_match" in logic:
            return re.match(logic["not_match"]["CI_COMMIT_BRANCH"], branch) is None
        elif "eq" in logic:
            return branch == logic["eq"]["CI_COMMIT_BRANCH"]
        elif "neq" in logic:
            return branch != logic["neq"]["CI_COMMIT_BRANCH"]
        else:
            return False


def get_rules(job_dict: dict, merged_yaml: dict, default_trigger: str, stage: str) -> List[Dict]:
    rules_setting = job_dict.get("rules")
    if not rules_setting:
        job_dict_extended = extend_rule(merged_yaml, job_dict)
        rules_setting = job_dict_extended.get("rules")

    logic_list = []

    if not rules_setting:
        only_list = job_dict.get("only")
        if only_list:
            match_list = [{"match": {"CI_COMMIT_BRANCH": item.strip("/")}} for item in only_list]
            logic_list = [{"tree": {"or": match_list}, "when": default_trigger}]
        else:
            logic_list = [{"tree": {"match": {"CI_COMMIT_BRANCH": ".*"}}, "when": default_trigger}]
    else:
        rules_queue = deque(rules_setting)
        resolved_rules = []
        while rules_queue:
            rule_item = rules_queue.popleft()
            if isinstance(rule_item, list):
                resolved = resolve_reference_path(rule_item, merged_yaml)
                if isinstance(resolved, list):
                    for r in reversed(resolved):
                        rules_queue.appendleft(r)
                elif resolved is not None:
                    rules_queue.appendleft(resolved)
            elif isinstance(rule_item, dict):
                resolved_rules.append(rule_item)

        for rule_item in resolved_rules:
            condition = rule_item.get("if")
            when = rule_item.get("when", default_trigger)
            variables = rule_item.get("variables", {})
            tree = BranchConditionParser().parse(condition, stage) if condition else {
                "match": {"CI_COMMIT_BRANCH": ".*"}}
            logic_list.append({"tree": tree, "when": when, "variable": variables})

    return logic_list


def has_ignore_test(shell_script: str, variable_list: list) -> bool:
    if_conditions = re.findall(r'if\s+(.*?)\s*;?\s*then', shell_script, flags=re.DOTALL)
    pattern_variable = re.compile(r'["\']?\$([A-Za-z_][A-Za-z0-9_]*)["\']?\s*==')

    variables_found = []
    for cond in if_conditions:
        variables_found.extend(pattern_variable.findall(cond))

    return len(set(variable_list) - set(variables_found)) == 0


def extend_rule(merged_yaml: dict, job_def: dict) -> dict:
    seen = set()
    merged = {}

    to_process = job_def.get("extends", [])
    if isinstance(to_process, str):
        to_process = [to_process]

    for parent_name in to_process:
        if parent_name in seen:
            continue
        seen.add(parent_name)
        if parent_name not in merged_yaml:
            continue

        parent_def = deepcopy(merged_yaml[parent_name])
        parent_def = extend_rule(merged_yaml, parent_def)
        merged = deep_merge_dict(merged, parent_def)

    merged = deep_merge_dict(merged, job_def)
    merged.pop("extends", None)
    return merged


def resolve_reference_path(target_list: list[str], all_yaml: dict) -> List[Union[Dict, str]]:
    check = all_yaml.get(target_list[0])
    if check:
        output = all_yaml.copy()
        for key in target_list:
            output = output[key]
        return output
    return [str(target_list)]


def deep_merge_dict(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = deep_merge_dict(result[k], v)
        else:
            result[k] = deepcopy(v)
    return result
