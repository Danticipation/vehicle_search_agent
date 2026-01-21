import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List
from src.storage.database import Listing
import structlog

logger = structlog.get_logger()

class EmailClient:
    def __init__(self, hostname: str, port: int, username: str, password: str, use_tls: bool = True):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    async def send_listing_alerts(self, to_emails: List[str], agent_name: str, listings: List[Listing]):
        if not listings:
            return

        subject = f"New Matches for {agent_name}: {len(listings)} vehicles found"
        
        # Create HTML body
        html_content = f"<h2>New Vehicle Matches for {agent_name}</h2>"
        html_content += "<ul>"
        for l in listings:
            price_fmt = f"${l.price:,.2f}" if l.price else "Contact for Price"
            mileage_fmt = f"{int(l.mileage):,} miles" if l.mileage else "N/A"
            html_content += f"""
                <li>
                    <strong>{l.year} {l.title}</strong><br>
                    Price: {price_fmt} | Mileage: {mileage_fmt}<br>
                    Source: {l.source}<br>
                    <a href="{l.url}">View Listing</a>
                </li>
                <hr>
            """
        html_content += "</ul>"

        message = MIMEMultipart("alternative")
        message["From"] = self.username
        message["To"] = ", ".join(to_emails)
        message["Subject"] = subject
        message.attach(MIMEText(html_content, "html"))

        try:
            # For port 587, we should use STARTTLS instead of direct TLS
            # aiosmtplib.send handles this automatically if use_tls=False and we call starttls later,
            # or we can use the explicit parameters.
            await aiosmtplib.send(
                message,
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=True if self.port == 587 else False,
                use_tls=True if self.port == 465 else False,
            )
            logger.info("email_sent", to=to_emails, count=len(listings))
        except Exception as e:
            logger.error("email_failed", error=str(e))
