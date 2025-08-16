from celery import shared_task
from core.models import Newsletter, Subscriber
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone


@shared_task
def send_newsletter(newsletter_id):
    """Send newsletter to all active subscribers"""
    try:
        newsletter = Newsletter.objects.get(id=newsletter_id)
        subscribers = Subscriber.objects.filter(
            is_active=True, confirmed_at__isnull=False
        )

        sent_count = 0
        for subscriber in subscribers:
            try:
                send_mail(
                    subject=newsletter.subject,
                    message=newsletter.content,
                    from_email="newsletter@cisd.org",
                    recipient_list=[subscriber.email],
                    html_message=render_to_string(
                        "emails/newsletter.html",
                        {"newsletter": newsletter, "subscriber": subscriber},
                    ),
                )
                sent_count += 1
            except Exception as e:
                print(f"Failed to send to {subscriber.email}: {e}")

        newsletter.total_sent = sent_count
        newsletter.is_sent = True
        newsletter.sent_date = timezone.now()
        newsletter.save()

        return f"Newsletter sent to {sent_count} subscribers"

    except Exception as e:
        return f"Failed to send newsletter: {e}"


@shared_task
def optimize_uploaded_images():
    """Background task to optimize uploaded images"""
    from core.models import MediaFile
    from core.utils import optimize_image

    unoptimized_images = MediaFile.objects.filter(
        file_type="image",
        # Add criteria for unoptimized images
    )

    for media_file in unoptimized_images:
        try:
            optimized = optimize_image(media_file.file)
            # Save optimized version
            # Implementation depends on your storage setup
        except Exception as e:
            print(f"Failed to optimize {media_file.title}: {e}")
