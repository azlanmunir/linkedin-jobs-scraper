"""Deterministic job-title classification."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Classification, RoleFamily, Seniority, Track, Workplace


@dataclass(frozen=True)
class ClassificationInput:
    run_id: str
    job_id: str
    title: str
    description: str | None = None
    workplace_hint: str | None = None


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip().lower())


def contains_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def classify_title(item: ClassificationInput) -> Classification:
    title = normalize_text(item.title)
    description = normalize_text(item.description)
    combined = f"{title} {description}".strip()

    role_family, role_reasons = classify_role_family(title)
    seniority, seniority_reasons = classify_seniority(title, role_family)
    track = classify_track(title, role_family, seniority)
    workplace, workplace_reasons = classify_workplace(item.workplace_hint or combined)

    confidence = 0.62
    if role_family != "Other":
        confidence += 0.18
    if seniority != "Mid":
        confidence += 0.08
    if workplace != "Unknown":
        confidence += 0.04
    confidence = min(confidence, 0.95)

    return Classification(
        run_id=item.run_id,
        job_id=item.job_id,
        role_family=role_family,
        seniority=seniority,
        track=track,
        workplace=workplace,
        confidence=confidence,
        reasons=[*role_reasons, *seniority_reasons, *workplace_reasons],
    )


def classify_role_family(title: str) -> tuple[RoleFamily, list[str]]:
    if contains_any(title, [r"\bchief of staff\b"]):
        return "Management", ["chief-of-staff management exception"]
    if contains_any(title, [r"\bchief\b", r"\bcto\b", r"\bciso\b", r"\bcio\b", r"\bceo\b"]):
        return "Executive", ["executive title"]
    if contains_any(title, [r"\bvp\b", r"\bvice president\b", r"\bhead of\b", r"\bdirector\b"]):
        return "Management", ["leadership title"]
    if contains_any(title, [r"\bproduct manager\b", r"\bproduct owner\b", r"\bproduct lead\b"]):
        return "Product", ["product title"]
    if contains_any(title, [r"\btechnical program manager\b", r"\btpm\b", r"\bprogram manager\b"]):
        return "Program", ["program title"]
    if contains_any(
        title,
        [r"\bengineering manager\b", r"\bdevelopment manager\b", r"\bmanager, engineering\b"],
    ):
        return "Management", ["engineering management title"]
    if contains_any(
        title,
        [
            r"\bmachine learning\b",
            r"\bml engineer\b",
            r"\bai engineer\b",
            r"\bartificial intelligence\b",
            r"\bmlops\b",
            r"\bdeep learning\b",
            r"\bcomputer vision\b",
            r"\bnlp\b",
        ],
    ):
        return "AI/ML", ["ai/ml title"]
    if contains_any(title, [r"\bdata scientist\b", r"\bdata science\b", r"\bdecision scientist\b"]):
        return "Data Science", ["data science title"]
    if contains_any(title, [r"\bdata engineer\b", r"\banalytics engineer\b", r"\betl\b"]):
        return "Data Engineering", ["data engineering title"]
    if contains_any(
        title,
        [
            r"\bdevops\b",
            r"\bsite reliability\b",
            r"\bsre\b",
            r"\bplatform engineer\b",
            r"\bcloud engineer\b",
        ],
    ):
        return "DevOps/SRE", ["infrastructure title"]
    if contains_any(
        title,
        [r"\bsecurity engineer\b", r"\bcybersecurity\b", r"\bapplication security\b"],
    ):
        return "Security", ["security title"]
    if contains_any(title, [r"\bdesigner\b", r"\bux\b", r"\bui\b", r"\buser experience\b"]):
        return "Design", ["design title"]
    if contains_any(
        title,
        [r"\brecruiter\b", r"\btalent acquisition\b", r"\bmarketing\b", r"\bcustomer success\b"],
    ):
        return "Other", ["non-technical title"]
    if contains_any(title, [r"\bsales engineer\b", r"\bsolutions engineer\b"]):
        return "Other", ["technical go-to-market title"]
    if contains_any(
        title,
        [
            r"\bsoftware engineer\b",
            r"\bsoftware developer\b",
            r"\bbackend\b",
            r"\bfrontend\b",
            r"\bfront-end\b",
            r"\bfull stack\b",
            r"\bfullstack\b",
            r"\bmobile engineer\b",
            r"\bios engineer\b",
            r"\bandroid engineer\b",
        ],
    ):
        return "SWE", ["software engineering title"]
    if contains_any(title, [r"\bmanager\b", r"\blead\b"]):
        return "Management", ["generic management title"]
    return "Other", ["no deterministic role-family match"]


def classify_seniority(title: str, role_family: RoleFamily) -> tuple[Seniority, list[str]]:
    if contains_any(title, [r"\bchief of staff\b"]):
        return "Director+", ["chief-of-staff leadership title"]
    if contains_any(title, [r"\bintern\b", r"\binternship\b"]):
        return "Intern", ["intern title"]
    if contains_any(
        title,
        [r"\bnew grad\b", r"\bentry level\b", r"\bearly career\b", r"\bjunior\b", r"\bjr\b"],
    ):
        return "Entry", ["entry title"]
    if role_family == "Executive":
        return "Executive", ["executive role family"]
    if contains_any(title, [r"\bvp\b", r"\bvice president\b", r"\bdirector\b", r"\bhead of\b"]):
        return "Director+", ["director-plus title"]
    if contains_any(title, [r"\bdistinguished\b", r"\bprincipal\b", r"\bstaff\b"]):
        return "Staff+", ["staff-plus title"]
    if contains_any(title, [r"\bsenior\b", r"\bsr\b", r"\blead\b"]):
        return "Senior", ["senior title"]
    if contains_any(title, [r"\bmanager\b", r"\blead manager\b"]):
        return "Manager", ["manager title"]
    return "Mid", ["default mid-level"]


def classify_track(title: str, role_family: RoleFamily, seniority: Seniority) -> Track:
    if role_family == "Executive" or seniority == "Executive":
        return "Executive"
    if role_family in {"Management", "Product", "Program"} or seniority in {"Manager", "Director+"}:
        return "Manager"
    if role_family in {"Design", "Other"} and contains_any(
        title,
        [r"\brecruiter\b", r"\btalent acquisition\b", r"\bmarketing\b", r"\bcustomer success\b"],
    ):
        return "Non-technical"
    return "IC"


def classify_workplace(text: str) -> tuple[Workplace, list[str]]:
    lowered = normalize_text(text)
    if contains_any(lowered, [r"\bhybrid\b"]):
        return "Hybrid", ["hybrid signal"]
    if contains_any(lowered, [r"\bremote\b", r"\bwork from home\b"]):
        return "Remote", ["remote signal"]
    if contains_any(lowered, [r"\bon-site\b", r"\bonsite\b", r"\bin office\b"]):
        return "On-site", ["on-site signal"]
    return "Unknown", ["no workplace signal"]
