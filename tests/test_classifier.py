from __future__ import annotations

from linkedin_jobs.classifier import ClassificationInput, classify_title


def classify(title: str):
    return classify_title(ClassificationInput(run_id="r1", job_id=title, title=title))


def test_title_classifier_edge_cases() -> None:
    assert classify("Chief Data Officer").role_family == "Executive"
    assert classify("Chief Data Officer").seniority == "Executive"

    chief_of_staff = classify("Chief of Staff, Product")
    assert chief_of_staff.role_family == "Management"
    assert chief_of_staff.track == "Manager"

    staff_swe = classify("Staff Software Engineer, Infrastructure")
    assert staff_swe.role_family == "SWE"
    assert staff_swe.seniority == "Staff+"
    assert staff_swe.track == "IC"

    tpm = classify("Technical Program Manager, AI Platform")
    assert tpm.role_family == "Program"
    assert tpm.track == "Manager"

    pm = classify("Product Manager, Growth")
    assert pm.role_family == "Product"
    assert pm.track == "Manager"

    assert classify("Software Development Engineer").role_family == "SWE"
    assert classify("Staff Engineer, Software").role_family == "SWE"
    assert classify("Data Analyst").role_family == "Analytics/BI"
    assert classify("Principal Software Automation/Test Engineer").role_family == "QA/Test"
    assert classify("Solutions Architect, Data & AI").role_family == "Solutions/Sales Engineering"
    assert classify("Cloud Infrastructure Engineer").role_family == "Infrastructure/Platform"
    assert classify("Research Scientist, Information Quality").role_family == "Research"
    assert classify("Firmware Engineer, ML Acceleration").role_family == "Hardware/Embedded"
    assert classify("AI Trainer/Data Annotator").role_family == "Data Operations/Annotation"


def test_workplace_classifier_uses_description_hint() -> None:
    result = classify_title(
        ClassificationInput(
            run_id="r1",
            job_id="j1",
            title="Senior Backend Engineer",
            description="This is a remote role.",
        )
    )

    assert result.role_family == "SWE"
    assert result.seniority == "Senior"
    assert result.workplace == "Remote"
