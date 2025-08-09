import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from aiosmtplib.errors import SMTPConnectError, SMTPException, SMTPRecipientsRefused
from fastapi import HTTPException
from jinja2 import Template

from ska_oso_services.common.error_handling import UnprocessableEntityError
from ska_oso_services.pht.utils.constants import HTML_TEMPLATE

LOGGER = logging.getLogger(__name__)




# Email rendering
def render_email(prsl_id: str, link: str) -> str:
    """
    Renders an HTML email template with dynamic data.

    Args:
        prsl_id (str): Proposal ID to include in the email.
        link (str): Accept/reject action link.

    Returns:
        str: Rendered HTML content.
    """
    template = Template(HTML_TEMPLATE)
    return template.render(prsl_id=prsl_id, link=link)


async def send_email_async(email: str, prsl_id: str):
    """
    Sends an email asynchronously using SMTP.
    Args:
        email (str): Recipient's email address.
        prsl_id (str): Proposal ID to include in the email.
    Raises:
        HTTPException: If there is an error in sending the email.
    """
    subject = f"Invitation to participate in the SKAO proposal - {prsl_id}"
    link = f"https://example.com/respond?prsl_id={prsl_id}"
    smtp_server = "eu-smtp-outbound-1.mimecast.com"
    smtp_port = 587
    smtp_user = "proposal-preparation-tool@skao.int"
    smtp_password = os.getenv("SMTP_PASSWORD", "SMTP_PASSWORD")

    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_user
    msg["To"] = email
    msg["Subject"] = subject

    plain_text = (
        f"You have been invited to participate in the SKAO proposal with ID {prsl_id}. "
        f"Visit {link} to respond."
    )
    html_content = render_email(prsl_id, link)

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=smtp_server,
            port=smtp_port,
            start_tls=True,
            username=smtp_user,
            password=smtp_password,
        )
        LOGGER.info("Email sent to %s for proposal %s", email, prsl_id)

    except SMTPConnectError as err:
        LOGGER.error("SMTP connection error: %s", str(err))
        raise HTTPException(status_code=503, detail="SMTP connection failed") from err

    except SMTPRecipientsRefused as err:
        LOGGER.error("Recipient refused: %s", str(err))
        raise UnprocessableEntityError(
            detail="Unable to send email for this recipient."
        ) from err

    except SMTPException as err:
        LOGGER.error("SMTP error for %s: %s", email, str(err))
        raise HTTPException(status_code=502, detail="SMTP send failed") from err
