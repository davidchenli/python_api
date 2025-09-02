import pytest
from repository.text import (
    BranchConditionEvaluator,
    get_rules,
    extend_rule,
    resolve_reference_path,
    has_ignore_test
)


@pytest.mark.parametrize(
    "logic,branch,expected",
    [
        ({"match": {"CI_COMMIT_BRANCH": "main"}}, "main", True),
        ({"match": {"CI_COMMIT_BRANCH": "main"}}, "dev", False),
        ({"not_match": {"CI_COMMIT_BRANCH": "main"}}, "dev", True),
        ({"and": [{"match": {"CI_COMMIT_BRANCH": "main"}}, {"not_match": {"CI_COMMIT_BRANCH": "dev"}}]}, "main", True),
        ({"or": [{"match": {"CI_COMMIT_BRANCH": "main"}}, {"match": {"CI_COMMIT_BRANCH": "dev"}}]}, "feature", False),
    ]
)
def test_branch_condition_evaluator(logic, branch, expected):
    evaluator = BranchConditionEvaluator()
    result = evaluator.evaluate(logic, branch)
    assert result == expected


def test_get_rules_only_branches():
    job_dict = {"only": ["main", "dev"]}
    merged_yaml = {}
    result = get_rules(job_dict, merged_yaml, default_trigger="always", stage="build")
    assert len(result) == 1
    tree = result[0]["tree"]
    assert "or" in tree or "match" in tree


def test_extend_rule_merging():
    merged_yaml = {
        "parent": {"script": ["echo parent"], "variables": {"A": "1"}},
    }
    job_def = {"extends": ["parent"], "script": ["echo child"], "variables": {"C": "3"}}
    result = extend_rule(merged_yaml, job_def)
    assert result["script"] == ["echo child"]
    assert result["variables"]["C"] == "3"
    assert "A" in result["variables"]


def test_resolve_reference_path_found():
    yaml_dict = {"a": {"b": {"c": 1}}}
    result = resolve_reference_path(["a", "b"], yaml_dict)
    assert result == {"c": 1}


def test_resolve_reference_path_not_found():
    yaml_dict = {}
    result = resolve_reference_path(["missing"], yaml_dict)
    assert isinstance(result, list)


def test_has_ignore_test_true():
    shell_script = """
    if [ "$VAR1" == "1" ] && [ "$VAR2" == "2" ]; then
        echo "do something"
    fi
    """
    variables_list = ["VAR1", "VAR2"]
    assert has_ignore_test(shell_script, variables_list) is True


def test_has_ignore_test_false():
    shell_script = """
    if [ "$VAR1" == "1" ]; then
        echo "do something"
    fi
    """
    variables_list = ["VAR1", "VAR2"]
    assert has_ignore_test(shell_script, variables_list) is False
