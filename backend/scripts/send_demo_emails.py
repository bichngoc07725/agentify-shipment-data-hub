from __future__ import annotations

import argparse
import os
import smtplib
import ssl
import time
from dataclasses import dataclass
from email import policy
from email.generator import BytesGenerator
from email.parser import BytesParser
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = ROOT / "demo_email"
DEFAULT_FROM = "minhvu2592005@gmail.com"
DEFAULT_TO = "vuphungminh250@gmail.com"
DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 465
DEFAULT_PASSWORD_ENV = "GMAIL_APP_PASSWORD"


@dataclass(frozen=True)
class EmailJob:
    folder_name: str
    eml_path: Path


def discover_email_jobs(source_dir: Path) -> list[EmailJob]:
    jobs: list[EmailJob] = []
    for child in sorted(source_dir.iterdir()):
        if not child.is_dir() or not child.name.startswith("email_"):
            continue
        eml_path = child / "email.eml"
        if eml_path.exists():
            jobs.append(EmailJob(folder_name=child.name, eml_path=eml_path))
    return jobs


def prepare_message_for_send(
    eml_path: Path,
    *,
    from_email: str,
    to_email: str,
) -> bytes:
    message = BytesParser(policy=policy.default).parsebytes(eml_path.read_bytes())
    original_from = message.get("From", "")
    original_to = message.get("To", "")

    if "From" in message:
        message.replace_header("From", from_email)
    else:
        message["From"] = from_email

    if "To" in message:
        message.replace_header("To", to_email)
    else:
        message["To"] = to_email

    if "X-Agentify-Original-From" in message:
        message.replace_header("X-Agentify-Original-From", original_from)
    else:
        message["X-Agentify-Original-From"] = original_from

    if "X-Agentify-Original-To" in message:
        message.replace_header("X-Agentify-Original-To", original_to)
    else:
        message["X-Agentify-Original-To"] = original_to

    buffer = BytesIO()
    BytesGenerator(buffer, policy=policy.default).flatten(message)
    return buffer.getvalue()


def send_jobs(
    jobs: list[EmailJob],
    *,
    from_email: str,
    to_email: str,
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    delay_seconds: float,
    dry_run: bool,
) -> int:
    sent_count = 0

    if dry_run:
        for job in jobs:
            prepare_message_for_send(job.eml_path, from_email=from_email, to_email=to_email)
            print(f"DRY RUN {job.folder_name} -> {to_email}")
            sent_count += 1
        return sent_count

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as smtp:
        smtp.login(smtp_username, smtp_password)
        for index, job in enumerate(jobs):
            raw_message = prepare_message_for_send(
                job.eml_path,
                from_email=from_email,
                to_email=to_email,
            )
            parsed = BytesParser(policy=policy.default).parsebytes(raw_message)
            smtp.send_message(parsed, from_addr=from_email, to_addrs=[to_email])
            sent_count += 1
            print(f"SENT {job.folder_name} -> {to_email}")
            if delay_seconds > 0 and index < len(jobs) - 1:
                time.sleep(delay_seconds)
    return sent_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send generated demo emails over SMTP.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--from-email", default=DEFAULT_FROM)
    parser.add_argument("--to-email", default=DEFAULT_TO)
    parser.add_argument("--smtp-host", default=DEFAULT_SMTP_HOST)
    parser.add_argument("--smtp-port", type=int, default=DEFAULT_SMTP_PORT)
    # No default here: it follows --from-email below. Defaulting it to the
    # module-level DEFAULT_FROM meant passing --from-email alone silently kept
    # logging in as somebody else's account, which surfaces only as an
    # unhelpful SMTP 535.
    parser.add_argument("--smtp-username", default=None)
    parser.add_argument("--smtp-password-env", default=DEFAULT_PASSWORD_ENV)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.smtp_username is None:
        args.smtp_username = args.from_email
    return args


def main() -> None:
    args = parse_args()
    jobs = discover_email_jobs(args.source_dir)
    if args.limit is not None:
        jobs = jobs[: args.limit]
    if not jobs:
        raise SystemExit(f"No email.eml files found in {args.source_dir}")

    smtp_password = ""
    if not args.dry_run:
        smtp_password = os.environ.get(args.smtp_password_env, "")
        if not smtp_password:
            raise SystemExit(
                f"Missing SMTP password in environment variable {args.smtp_password_env}"
            )

    sent_count = send_jobs(
        jobs,
        from_email=args.from_email,
        to_email=args.to_email,
        smtp_host=args.smtp_host,
        smtp_port=args.smtp_port,
        smtp_username=args.smtp_username,
        smtp_password=smtp_password,
        delay_seconds=args.delay_seconds,
        dry_run=args.dry_run,
    )
    print(f"Processed {sent_count} emails")


if __name__ == "__main__":
    main()
