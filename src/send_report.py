"""
Email Report Sender
Sends the latest monthly recommendation report via Gmail SMTP.
"""

import json
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from config import (
    GMAIL_ADDRESS,
    GMAIL_APP_PASSWORD,
    RECIPIENT_EMAIL,
    MONTHLY_DIR,
)
from prompts import email_subject, email_body_wrapper


def get_latest_report() -> tuple[str, str]:
    """Find and load the most recent monthly report."""
    md_files = sorted(MONTHLY_DIR.glob("recommendations_*.md"), reverse=True)

    if not md_files:
        print("ERROR: No monthly reports found in data/monthly/")
        sys.exit(1)

    latest = md_files[0]
    print(f"Latest report: {latest.name}")

    with open(latest) as f:
        report_content = f.read()

    # Extract month-year for the subject line
    month_str = latest.stem.replace("recommendations_", "")
    try:
        month_date = datetime.strptime(month_str, "%Y-%m")
        month_year = month_date.strftime("%B %Y")
    except ValueError:
        month_year = month_str

    return report_content, month_year


def send_email(report: str, month_year: str):
    """Send the report via Gmail SMTP."""
    if not all([GMAIL_ADDRESS, GMAIL_APP_PASSWORD, RECIPIENT_EMAIL]):
        print("ERROR: Email credentials not fully configured.")
        print("  Set GMAIL_ADDRESS, GMAIL_APP_PASSWORD, and RECIPIENT_EMAIL")
        sys.exit(1)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = email_subject(month_year)
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = RECIPIENT_EMAIL

    # Plain text version
    body = email_body_wrapper(report)
    msg.attach(MIMEText(body, "plain"))

    print(f"Sending to {RECIPIENT_EMAIL}...")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, RECIPIENT_EMAIL, msg.as_string())
        print("✅ Email sent successfully!")
    except smtplib.SMTPAuthenticationError:
        print("ERROR: Gmail authentication failed.")
        print("  Make sure you're using an App Password, not your regular password.")
        print("  Create one at: https://myaccount.google.com/apppasswords")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR sending email: {e}")
        sys.exit(1)


def main():
    """Send the latest monthly report via email."""
    print("=" * 60)
    print("AI Investment Advisor — Email Report")
    print("=" * 60)

    report, month_year = get_latest_report()
    send_email(report, month_year)


if __name__ == "__main__":
    main()
