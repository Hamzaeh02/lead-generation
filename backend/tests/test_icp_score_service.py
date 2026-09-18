from app.models.company import Company
from app.models.contact import Contact
from app.models.icp_profile import ICPProfile
from app.services.icp_score_service import compute_icp_score


def _company(**overrides) -> Company:
    defaults = dict(
        name="Acme Dental Group",
        industry="dental",
        city="Miami",
        state="FL",
        country="US",
        employee_count=20,
        description="A modern dental clinic",
    )
    defaults.update(overrides)
    return Company(**defaults)


def _icp(**overrides) -> ICPProfile:
    defaults = dict(
        name="Test ICP",
        industry=None,
        country=None,
        state=None,
        city=None,
        employee_count_min=None,
        employee_count_max=None,
        target_titles=[],
        keywords=[],
        weights={},
    )
    defaults.update(overrides)
    return ICPProfile(**defaults)


def test_full_match_scores_100():
    company = _company()
    icp = _icp(
        industry="dental",
        city="Miami",
        state="FL",
        country="US",
        employee_count_min=5,
        employee_count_max=50,
        target_titles=["Owner"],
        keywords=["dental"],
    )
    contacts = [Contact(job_title="Owner")]

    score, matched = compute_icp_score(company, contacts, icp)

    assert score == 100
    assert len(matched) == 5


def test_no_criteria_set_scores_zero():
    score, matched = compute_icp_score(_company(), [], _icp())
    assert score == 0
    assert matched == []


def test_industry_mismatch_scores_zero_for_that_criterion():
    icp = _icp(industry="roofing")
    score, matched = compute_icp_score(_company(), [], icp)
    assert score == 0
    assert matched == []


def test_partial_location_match_gives_partial_credit():
    icp = _icp(city="Orlando", state="FL")  # state matches, city doesn't
    score, matched = compute_icp_score(_company(), [], icp)
    # location weight (25) * 1/2 matched fields = 12.5 -> rounds to 12 or 13
    assert 10 <= score <= 15
    assert "location matches on state" in matched[0]


def test_company_size_out_of_range_scores_zero():
    icp = _icp(employee_count_min=100, employee_count_max=500)
    score, matched = compute_icp_score(_company(employee_count=20), [], icp)
    assert score == 0


def test_company_size_missing_data_scores_zero_not_penalized_elsewhere():
    icp = _icp(employee_count_min=5, employee_count_max=50, industry="dental")
    score, matched = compute_icp_score(_company(employee_count=None), [], icp)
    # industry still matches (30), size contributes 0 since data is missing
    assert score == 30


def test_decision_maker_requires_matching_contact():
    icp = _icp(target_titles=["CEO", "Owner"])
    no_match_score, _ = compute_icp_score(_company(), [Contact(job_title="Intern")], icp)
    match_score, matched = compute_icp_score(_company(), [Contact(job_title="Owner")], icp)
    assert no_match_score == 0
    assert match_score == 15


def test_custom_weights_override_defaults():
    icp = _icp(industry="dental", weights={"industry": 60})
    score, _ = compute_icp_score(_company(), [], icp)
    assert score == 60


def test_score_never_exceeds_100_even_with_inflated_weights():
    icp = _icp(industry="dental", weights={"industry": 500})
    score, _ = compute_icp_score(_company(), [], icp)
    assert score == 100
