"""Send independent email and ntfy alerts for a failed Actions run."""

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from urllib.request import Request, urlopen


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing GitHub Actions secret: {name}")
    return value


def send_email(subject, body):
    host = required("ALERT_SMTP_HOST")
    port = int(os.environ.get("ALERT_SMTP_PORT") or "465")
    user = required("ALERT_SMTP_USER")
    password = required("ALERT_SMTP_PASSWORD")
    recipient = required("ALERT_EMAIL_TO")

    message = EmailMessage()
    message["From"] = user
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=20, context=context) as smtp:
            smtp.login(user, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.starttls(context=context)
            smtp.login(user, password)
            smtp.send_message(message)


def send_push(subject, body):
    url = required("ALERT_NTFY_URL")
    if not url.startswith("https://"):
        raise ValueError("ALERT_NTFY_URL must start with https://")
    headers = {"Title": subject, "Priority": "high", "Tags": "warning"}
    token = os.environ.get("ALERT_NTFY_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
    with urlopen(request, timeout=20) as response:
        response.read()


def main():
    run_url = required("ALERT_RUN_URL")
    subject = "LeetCode Daily workflow failed"
    body = f"The daily workflow failed. Open the run for details:\n{run_url}\n"
    failed = False
    for name, sender in (("Email", send_email), ("Phone push", send_push)):
        try:
            sender(subject, body)
            print(f"{name} alert sent")
        except Exception as exc:
            print(f"{name} alert failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
