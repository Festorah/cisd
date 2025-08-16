import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class EmailManager:
    """Manager for sending various types of emails"""

    @staticmethod
    def send_newsletter(newsletter, subscribers):
        """Send newsletter to list of subscribers"""
        sent_count = 0
        failed_count = 0

        for subscriber in subscribers:
            try:
                # Render email content
                html_content = render_to_string(
                    "emails/newsletter.html",
                    {
                        "newsletter": newsletter,
                        "subscriber": subscriber,
                        "unsubscribe_url": f"{settings.SITE_URL}/unsubscribe/{subscriber.id}/",
                    },
                )

                text_content = render_to_string(
                    "emails/newsletter.txt",
                    {
                        "newsletter": newsletter,
                        "subscriber": subscriber,
                    },
                )

                # Create email
                email = EmailMultiAlternatives(
                    subject=newsletter.subject,
                    body=text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[subscriber.email],
                )
                email.attach_alternative(html_content, "text/html")

                # Send email
                email.send()
                sent_count += 1

                # Update subscriber last_sent
                subscriber.last_sent = timezone.now()
                subscriber.save(update_fields=["last_sent"])

            except Exception as e:
                logger.error(
                    f"Failed to send newsletter to {subscriber.email}: {str(e)}"
                )
                failed_count += 1

        # Update newsletter statistics
        newsletter.total_sent = sent_count
        newsletter.is_sent = True
        newsletter.sent_date = timezone.now()
        newsletter.save()

        return {
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_attempted": len(subscribers),
        }

    @staticmethod
    def send_welcome_email(subscriber):
        """Send welcome email to new subscriber"""
        try:
            html_content = render_to_string(
                "emails/welcome.html", {"subscriber": subscriber, "site_name": "CISD"}
            )

            text_content = render_to_string(
                "emails/welcome.txt", {"subscriber": subscriber, "site_name": "CISD"}
            )

            email = EmailMultiAlternatives(
                subject="Welcome to CISD Newsletter",
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[subscriber.email],
            )
            email.attach_alternative(html_content, "text/html")
            email.send()

            return True

        except Exception as e:
            logger.error(
                f"Failed to send welcome email to {subscriber.email}: {str(e)}"
            )
            return False
