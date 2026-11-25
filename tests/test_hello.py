"""The hello-world job task."""

import json

from analytics_platform.hello import build_log_line, main


def test_hello_log_line_is_json_with_the_catalog():
    assert json.loads(build_log_line("staging")) == {"event": "hello", "catalog": "staging", "status": "ok"}


def test_hello_main_prints_the_log_line(capsys):
    assert main(["--catalog", "prod"]) == 0
    assert json.loads(capsys.readouterr().out)["catalog"] == "prod"
