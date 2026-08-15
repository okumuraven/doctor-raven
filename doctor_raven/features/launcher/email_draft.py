"""Drafts an email via the local LLM for you to review — never sends anything itself. On
confirm, hands the draft to your actual mail client as a pre-filled mailto: link, so the final
send is always a real action you take yourself, in your own client. No account credentials,
no SMTP, no OAuth — Doctor Raven never gains the ability to send mail on your behalf."""

import webbrowser
from dataclasses import dataclass
from urllib.parse import quote

from doctor_raven.config import Config
from doctor_raven.core import llm_router

DRAFT_SYSTEM_PROMPT = (
    "You are Doctor Raven, drafting an email on okumuraven's behalf for them to review before "
    "sending. Given a short description of what it's about, write a concise, professional email "
    "body (no more than a few short paragraphs) and a matching subject line. Output ONLY two "
    "lines in this exact format, nothing else:\n"
    "SUBJECT: <subject line>\n"
    "BODY: <body text, \\n for line breaks>"
)


@dataclass(frozen=True)
class EmailDraft:
    to: str
    subject: str
    body: str


def draft(to: str, about: str, config: Config) -> EmailDraft:
    raw = llm_router.complete(config, about, system=DRAFT_SYSTEM_PROMPT)
    subject = "Regarding your message"
    body = about
    for line in raw.splitlines():
        if line.upper().startswith("SUBJECT:"):
            subject = line.split(":", 1)[1].strip()
        elif line.upper().startswith("BODY:"):
            body = line.split(":", 1)[1].strip().replace("\\n", "\n")
    return EmailDraft(to=to, subject=subject, body=body)


def open_in_mail_client(draft_email: EmailDraft) -> bool:
    mailto = f"mailto:{quote(draft_email.to)}?subject={quote(draft_email.subject)}&body={quote(draft_email.body)}"
    return webbrowser.open(mailto)
