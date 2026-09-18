from app.services.nl_icp_parser import parse_nl_icp


def test_parses_industry_state_and_employee_range():
    result = parse_nl_icp("Find dental clinic owners in Florida with 5 to 50 employees.")

    assert result.suggested.industry == "dental"
    assert result.suggested.state == "Florida"
    assert result.suggested.country == "US"
    assert result.suggested.employee_count_min == 5
    assert result.suggested.employee_count_max == 50
    assert "Owner" in result.suggested.target_titles
    assert result.unparsed_hints == []


def test_parses_state_abbreviation():
    result = parse_nl_icp("Roofing contractors in TX")
    assert result.suggested.state == "TX"
    assert result.suggested.country == "US"
    assert result.suggested.industry == "roofing"


def test_under_employees_sets_max_only():
    result = parse_nl_icp("Software agencies with under 20 employees")
    assert result.suggested.employee_count_min is None
    assert result.suggested.employee_count_max == 20


def test_over_employees_sets_min_only():
    result = parse_nl_icp("Manufacturing companies with over 200 employees")
    assert result.suggested.employee_count_min == 200
    assert result.suggested.employee_count_max is None


def test_plus_notation_sets_min_only():
    result = parse_nl_icp("Companies with 50+ employees")
    assert result.suggested.employee_count_min == 50
    assert result.suggested.employee_count_max is None


def test_no_recognized_fields_returns_hints():
    result = parse_nl_icp("Find companies that might be interested")
    assert result.suggested.industry is None
    assert result.suggested.state is None
    assert len(result.unparsed_hints) == 4


def test_never_auto_populates_keywords_or_name():
    result = parse_nl_icp("Find dental clinic owners in Florida")
    assert result.suggested.keywords == []
    assert result.suggested.name == "Parsed from natural language"


def test_multiple_titles_detected():
    result = parse_nl_icp("Find CEOs and CTOs at software companies in California")
    assert set(result.suggested.target_titles) >= {"Ceo", "Cto"}
