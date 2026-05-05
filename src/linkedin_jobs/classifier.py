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
    if contains_any(
        title,
        [
            r"\brecruiter\b",
            r"\btalent acquisition\b",
            r"\bsourcer\b",
            r"\bpeople partner\b",
            r"\bhr\b",
            r"\bhuman resources\b",
        ],
    ):
        return "People/Recruiting", ["people/recruiting title"]
    if contains_any(title, [r"\bproduct manager\b", r"\bproduct owner\b", r"\bproduct lead\b"]):
        return "Product", ["product title"]
    if contains_any(
        title,
        [
            r"\btechnical program manager\b",
            r"\btpm\b",
            r"\bprogram manager\b",
            r"\bprogram analyst\b",
            r"\bprogram coordinator\b",
            r"\bproject manager\b",
            r"\bproject analyst\b",
        ],
    ):
        return "Program", ["program title"]
    if contains_any(
        title,
        [r"\bengineering manager\b", r"\bdevelopment manager\b", r"\bmanager, engineering\b"],
    ):
        return "Management", ["engineering management title"]
    if contains_any(
        title,
        [
            r"\bdeveloper relations\b",
            r"\bdevrel\b",
            r"\bdeveloper advocate\b",
            r"\bcloud advocate\b",
            r"\bdeveloper experience\b",
        ],
    ):
        return "Developer Relations", ["developer-relations title"]
    if contains_any(
        title,
        [
            r"\bsolutions? engineer\b",
            r"\bsales engineer\b",
            r"\bpre-?sales\b",
            r"\bsolutions? architect\b",
            r"\bcustomer engineer\b",
            r"\bforward deployed engineer\b",
            r"\bforward deploy engineer\b",
            r"\bfield engineer\b",
        ],
    ):
        return "Solutions/Sales Engineering", ["customer-facing technical title"]
    if contains_any(
        title,
        [
            r"\bdata annotat",
            r"\bdata label",
            r"\bdata collector\b",
            r"\bdata collection\b",
            r"\bdata ambassador\b",
            r"\bai trainer\b",
            r"\bai training\b",
            r"\bmodel evaluation\b",
            r"\bcontent quality\b",
            r"\bsurvey participants\b",
        ],
    ):
        return "Data Operations/Annotation", ["data operations/annotation title"]
    if contains_any(
        title,
        [
            r"\bqa\b",
            r"\bquality assurance\b",
            r"\bquality engineer\b",
            r"\btest engineer\b",
            r"\bsoftware automation engineer\b",
            r"\bsoftware test\b",
            r"\bsdet\b",
            r"\bvalidation engineer\b",
            r"\bverification engineer\b",
            r"\bautomation/test\b",
            r"\btest automation\b",
        ],
    ):
        return "QA/Test", ["quality/test title"]
    if contains_any(
        title,
        [
            r"\bcybersecurity\b",
            r"\bcyber security\b",
            r"\bsecurity engineer\b",
            r"\bapplication security\b",
            r"\bproduct security\b",
            r"\bdata protection\b",
            r"\binformation security\b",
            r"\bcloud security\b",
            r"\bnetwork security\b",
            r"\bsecurity operations\b",
            r"\bvulnerability\b",
            r"\bforensic analyst\b",
        ],
    ):
        return "Security", ["security title"]
    if contains_any(
        title,
        [
            r"\bfirmware\b",
            r"\bembedded\b",
            r"\belectrical\b",
            r"\bfpga\b",
            r"\b asic\b",
            r"\bsilicon\b",
            r"\bhardware\b",
            r"\bgpu kernel\b",
            r"\bcuda\b",
            r"\bchip\b",
            r"\bemulation engineer\b",
            r"\bsystem memory\b",
        ],
    ):
        return "Hardware/Embedded", ["hardware/embedded title"]
    if contains_any(
        title,
        [
            r"\brobotics\b",
            r"\brobot\b",
            r"\bautonomous\b",
            r"\bautonomy\b",
            r"\bself-driving\b",
            r"\bperception\b",
            r"\bvehicle\b",
            r"\bdriving system\b",
        ],
    ):
        return "Robotics/Autonomy", ["robotics/autonomy title"]
    if contains_any(
        title,
        [
            r"\bmachine learning\b",
            r"\bml engineer\b",
            r"\bai engineer\b",
            r"\bartificial intelligence\b",
            r"\bmlops\b",
            r"\bml[- ]ops\b",
            r"\bdeep learning\b",
            r"\bcomputer vision\b",
            r"\bnlp\b",
            r"\bllm\b",
            r"\bgenai\b",
            r"\bgenerative ai\b",
            r"\bagentic\b",
            r"\bai/ml\b",
            r"\bai ops\b",
            r"\bai compiler\b",
            r"\bai applications engineer\b",
            r"\bai agent engineer\b",
            r"\bai applied .*engineer\b",
            r"\bai automation\b",
            r"\bai development\b",
            r"\bai infrastructure\b",
            r"\bai innovation\b",
            r"\bai production\b",
            r"\bai data\b",
            r"\bscientific ai\b",
            r"\bml product engineer\b",
            r"\bapplied scientist\b",
        ],
    ):
        return "AI/ML", ["ai/ml title"]
    if contains_any(title, [r"\bdata scientist\b", r"\bdata science\b", r"\bdecision scientist\b"]):
        return "Data Science", ["data science title"]
    if contains_any(
        title,
        [
            r"\bresearch scientist\b",
            r"\bresearch engineer\b",
            r"\bprincipal scientist\b",
            r"\bscientist\b",
        ],
    ):
        return "Research", ["research/scientist title"]
    if contains_any(
        title,
        [
            r"\bdata engineer\b",
            r"\bdata engineering\b",
            r"\banalytics engineer\b",
            r"\betl\b",
            r"\bdata infra",
            r"\bdata infrastructure\b",
            r"\bdata platform\b",
            r"\bdata solutions engineer\b",
            r"\bdata governance\b",
            r"\bdata modeler\b",
            r"\bdata scraping\b",
            r"\bdatabase engineer\b",
            r"\bdata operations\b",
            r"\bdata engineering analyst\b",
            r"\bdata and asset management\b",
            r"\bdata & identity\b",
            r"\bmicrosoft fabric\b",
            r"\binformatica\b",
            r"\bdata quality\b",
        ],
    ):
        return "Data Engineering", ["data engineering title"]
    if contains_any(
        title,
        [
            r"\bdata analyst\b",
            r"\banalyst/engineer\b",
            r"\banalytics analyst\b",
            r"\bdata analytics\b",
            r"\bdata insights\b",
            r"\bcustomer insights\b",
            r"\bfinancial analyst\b",
            r"\bmetadata analyst\b",
            r"\bbusiness intelligence\b",
            r"\benterprise intelligence\b",
            r"\bbi analyst\b",
            r"\bbi engineer\b",
            r"\bbusiness reporting analyst\b",
            r"\breporting analyst\b",
            r"\binsights analyst\b",
            r"\bstatic data\b",
            r"\bproduct analytics\b",
            r"\banalytics\b",
            r"\bdecision analytics\b",
            r"\bresearch analyst\b",
        ],
    ):
        return "Analytics/BI", ["analytics/bi title"]
    if contains_any(
        title,
        [
            r"\bdevops\b",
            r"\bsite reliability\b",
            r"\bsre\b",
            r"\breliability engineering\b",
            r"\breliability engineer\b",
            r"\bdev ops\b",
        ],
    ):
        return "DevOps/SRE", ["devops/sre title"]
    if contains_any(
        title,
        [
            r"\bplatform engineer\b",
            r"\bplatformization\b",
            r"\bcloud engineer\b",
            r"\bengineer cloud services\b",
            r"\bcloud automation\b",
            r"\bcloud infrastructure\b",
            r"\baws engineer\b",
            r"\bazure build engineer\b",
            r"\binfrastructure engineer\b",
            r"\bsystems engineer\b",
            r"\bsystem engineer\b",
            r"\bsystems analysis engineer\b",
            r"\bsystem design engineer\b",
            r"\bnetwork engineer\b",
            r"\bnetwork operations engineer\b",
            r"\bnetwork ip engineer\b",
            r"\bnetwork automation\b",
            r"\bfiber connectivity engineer\b",
            r"\bendpoint engineer\b",
            r"\bvm engineer\b",
            r"\bsoftware defined storage\b",
            r"\bhil platform\b",
            r"\bpower engineer\b",
            r"\bsystems architect\b",
            r"\bsystem architect\b",
            r"\bsite infrastructure\b",
            r"\bdata center\b",
        ],
    ):
        return "Infrastructure/Platform", ["infrastructure/platform title"]
    if contains_any(
        title,
        [
            r"\bsupport engineer\b",
            r"\btechnical support\b",
            r"\bsoftware support\b",
            r"\bnetwork support\b",
            r"\bcontact center engineer\b",
            r"\bsoftware installation engineer\b",
            r"\bhelp desk\b",
            r"\bit support\b",
            r"\bdesktop support\b",
            r"\bsystems administrator\b",
            r"\bsystem administrator\b",
            r"\bsysadmin\b",
        ],
    ):
        return "IT/Support", ["it/support title"]
    if contains_any(title, [r"\bdesigner\b", r"\bux\b", r"\bui\b", r"\buser experience\b"]):
        return "Design", ["design title"]
    if contains_any(title, [r"\bproduct analyst\b", r"\bproduct expert\b"]):
        return "Product", ["product analyst/expert title"]
    if contains_any(
        title,
        [
            r"\bcustomer success\b",
            r"\bimplementation\b",
            r"\bsolutions consultant\b",
            r"\btechnical consultant\b",
            r"\bclient advisor\b",
            r"\bcustomer service\b",
            r"\bcustomer support/applications engineer\b",
        ],
    ):
        return "Customer Success/Implementation", ["customer implementation/success title"]
    if contains_any(
        title,
        [
            r"\bproduct marketing\b",
            r"\bmarketing\b",
            r"\bgrowth\b",
            r"\bdemand generation\b",
            r"\bgo[- ]to[- ]market\b",
        ],
    ):
        return "Marketing/Growth", ["marketing/growth title"]
    if contains_any(
        title,
        [
            r"\bclinician\b",
            r"\bclinical\b",
            r"\bbehavior interventionist\b",
            r"\bpharmacy technician\b",
            r"\bnurse\b",
            r"\bpatient\b",
            r"\btherapist\b",
            r"\bmedical\b",
        ],
    ):
        return "Healthcare/Clinical", ["healthcare/clinical title"]
    if contains_any(
        title,
        [
            r"\bcashier\b",
            r"\bcar washer\b",
            r"\bclub attendant\b",
            r"\bculinary\b",
            r"\bretail\b",
            r"\bsales associate\b",
            r"\bcounter sales\b",
            r"\bstore\b",
            r"\bhost\b",
        ],
    ):
        return "Retail/Service", ["retail/service title"]
    if contains_any(
        title,
        [
            r"\binvestor\b",
            r"\binvestment\b",
            r"\bcommercial analyst\b",
            r"\bprocurement\b",
            r"\bbuyer\b",
            r"\bconsignment\b",
        ],
    ):
        return "Finance/Investment", ["finance/investment title"]
    if contains_any(
        title,
        [
            r"\bcamera operator\b",
            r"\bcamera support technician\b",
            r"\btransportation planner\b",
            r"\bconstruction\b",
            r"\bunion relief engineer\b",
            r"\bmechanical engineer\b",
            r"\bfield technician\b",
        ],
    ):
        return "Facilities/Field Ops", ["facilities/field operations title"]
    if contains_any(
        title,
        [
            r"\bbusiness operations\b",
            r"\bbusiness systems\b",
            r"\boperations analyst\b",
            r"\boperations associate\b",
            r"\bbusiness analyst\b",
            r"\bbusiness management analyst\b",
            r"\bstrategy\b",
            r"\bcontract management\b",
            r"\basset management analyst\b",
            r"\btransaction analytics\b",
        ],
    ):
        return "Business/Ops", ["business/operations title"]
    if contains_any(
        title,
        [
            r"\boffice assistant\b",
            r"\baccount coordinator\b",
            r"\bnavigator coordinator\b",
            r"\bcoordinator\b",
            r"\bsurveys\b",
            r"\bsurvey\b",
            r"\bposted job description\b",
        ],
    ):
        return "Admin/Operations", ["admin/operations title"]
    if contains_any(
        title,
        [
            r"\beducation\b",
            r"\bteacher\b",
            r"\btutor\b",
            r"\binstructor\b",
            r"\btrainer\b",
            r"\btraining\b",
        ],
    ):
        return "Education/Training", ["education/training title"]
    if contains_any(
        title,
        [
            r"\bsoftware engineer",
            r"\bengineer software\b",
            r"\bsoftware developer\b",
            r"\bsoftware development engineer\b",
            r"\bsoftware dev(?:elopment)? engineer\b",
            r"\bsoftware dev\.? engineer\b",
            r"\bsoftware engin+er\b",
            r"\bsoftware design engineer\b",
            r"\bsoftware integration\b",
            r"\bsoftware architect\b",
            r"\bprincipal engineer software\b",
            r"\bstaff engineer, software\b",
            r"\bengineer, software\b",
            r"\bengineer.*software\b",
            r"\bmember of technical staff\b",
            r"\bchromium\b",
            r"\bcef\b",
            r"\bapplication engineer\b",
            r"\bapplication .*engineer\b",
            r"\bgraphics programmer\b",
            r"\bprogrammer\b",
            r"\bbackend\b",
            r"\bfrontend\b",
            r"\bfront-end\b",
            r"\bfront end\b",
            r"\bback-end\b",
            r"\bback end\b",
            r"\bfull stack\b",
            r"\bfullstack\b",
            r"\bfull-stack\b",
            r"\bmobile engineer\b",
            r"\bios engineer\b",
            r"\bandroid engineer\b",
            r"\bjava(?:script)? developer\b",
            r"\bjavascript engineer\b",
            r"\bpython developer\b",
            r"\breact(?: js)? developer\b",
            r"\breact\.js\b",
            r"\bdeveloper\b",
            r"\bfounding engineer\b",
            r"\bcreator services\b",
            r"\brust software\b",
            r"\bc\+\+\b",
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
        [
            r"\bnew grad\b",
            r"\bnew college grad\b",
            r"\bentry level\b",
            r"\bearly career\b",
            r"\bjunior\b",
            r"\bjr\b",
        ],
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
    if role_family in {
        "People/Recruiting",
        "Business/Ops",
        "Admin/Operations",
        "Marketing/Growth",
        "Customer Success/Implementation",
        "Education/Training",
        "Healthcare/Clinical",
        "Retail/Service",
        "Finance/Investment",
        "Facilities/Field Ops",
    }:
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
