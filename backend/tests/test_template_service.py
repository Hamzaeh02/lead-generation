from app.models.ai_generation import AIGeneration
from app.models.company import Company
from app.models.contact import Contact
from app.models.intent_signal import IntentSignal
from app.services.template_service import build_context, render_template


def test_render_fills_known_variables_from_real_data():
    contact = Contact(first_name="Jordan", last_name="Alvarez", job_title="Owner")
    company = Company(name="Acme Dental Group", city="Miami", industry="dental")
    context = build_context(
        contact=contact, company=company, personalization=None, unsubscribe_url="/unsubscribe/tok"
    )

    result = render_template(
        "Hi {{first_name}}, noticed {{company_name}} in {{city}} does {{industry}} work.", context
    )

    assert result.text == "Hi Jordan, noticed Acme Dental Group in Miami does dental work."
    assert set(result.variables_filled) == {"first_name", "company_name", "city", "industry"}
    assert result.variables_empty == []


def test_missing_data_renders_as_empty_string_never_fabricated():
    contact = Contact(first_name=None)
    context = build_context(
        contact=contact, company=None, personalization=None, unsubscribe_url="/unsubscribe/tok"
    )

    result = render_template("Hi {{first_name}}, welcome to {{company_name}}.", context)

    assert result.text == "Hi , welcome to ."
    assert "first_name" in result.variables_empty
    assert "company_name" in result.variables_empty
    assert result.variables_filled == []


def test_unrecognized_variable_left_untouched():
    contact = Contact(first_name="Jordan")
    context = build_context(
        contact=contact, company=None, personalization=None, unsubscribe_url="/unsubscribe/tok"
    )

    result = render_template("Hi {{first_name}}, {{made_up_variable}}!", context)

    assert "{{made_up_variable}}" in result.text
    assert result.unrecognized_variables == ["made_up_variable"]


def test_personalized_intro_and_outreach_angle_from_ai_generation():
    contact = Contact(first_name="Jordan")
    personalization = AIGeneration(opening_line="Saw your expansion news.", outreach_angle="Recent growth")
    context = build_context(
        contact=contact, company=None, personalization=personalization, unsubscribe_url="/unsubscribe/tok"
    )

    result = render_template("{{personalized_intro}} — {{outreach_angle}}", context)

    assert result.text == "Saw your expansion news. — Recent growth"


def test_intent_signal_variable():
    contact = Contact(first_name="Jordan")
    signal = IntentSignal(signal_text="Opened a second location")
    context = build_context(
        contact=contact, company=None, personalization=None, unsubscribe_url="/unsubscribe/tok",
        intent_signal=signal,
    )

    result = render_template("Noticed: {{intent_signal}}", context)

    assert result.text == "Noticed: Opened a second location"


def test_unsubscribe_url_always_present():
    contact = Contact(first_name="Jordan")
    context = build_context(
        contact=contact, company=None, personalization=None, unsubscribe_url="/unsubscribe/abc123"
    )

    result = render_template("Unsubscribe: {{unsubscribe_url}}", context)

    assert result.text == "Unsubscribe: /unsubscribe/abc123"
