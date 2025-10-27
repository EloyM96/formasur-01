from datetime import date, timedelta
from pathlib import Path

from app.rules.engine import RuleSet


def test_ruleset_evaluates_yaml_expressions(tmp_path: Path):
    yaml_content = """
    rules:
      - id: vencido
        when: "today() > parse_date(row['certificate_expires_at'])"
      - id: proximo
        when: "0 <= days_until(parse_date(row['certificate_expires_at'])) <= 15"
    """
    ruleset_file = tmp_path / "rules.yaml"
    ruleset_file.write_text(yaml_content, encoding="utf-8")

    ruleset = RuleSet.from_yaml(ruleset_file)

    expired_row = {"certificate_expires_at": (date.today() - timedelta(days=1)).isoformat()}
    upcoming_row = {"certificate_expires_at": (date.today() + timedelta(days=7)).isoformat()}

    assert ruleset.evaluate({"row": expired_row}) == {"vencido": True, "proximo": False}
    assert ruleset.evaluate({"row": upcoming_row}) == {"vencido": False, "proximo": True}
