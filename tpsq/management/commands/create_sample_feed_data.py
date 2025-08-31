import random
import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from tpsq.models import (
    PretotypeComment,
    PretotypeIssue,
    PretotypeIssueStatus,
    PretotypeReaction,
    PretotypeSession,
)


class Command(BaseCommand):
    help = "Create sample data for pretotype feed"

    def handle(self, *args, **options):
        # Create sample sessions
        sessions = []
        for i in range(20):
            session = PretotypeSession.objects.create(
                session_id=uuid.uuid4(),
                device_type=random.choice(["mobile", "desktop", "tablet"]),
                started_at=timezone.now() - timedelta(days=random.randint(0, 30)),
            )
            sessions.append(session)

        # Create sample issues
        issue_types = [
            "light",
            "roads",
            "waste",
            "water",
            "security",
            "healthcare",
            "education",
            "others",
        ]
        sample_descriptions = [
            "This has been ongoing for weeks now. Very frustrating for our community.",
            "Urgent attention needed. Affects daily life significantly.",
            "Similar issue reported before but no action taken.",
            "Hope this gets resolved soon.",
            "Community members are very concerned about this.",
            "",  # Some issues have no additional details
        ]

        issues = []
        for i, session in enumerate(sessions[:15]):  # Create 15 sample issues
            issue = PretotypeIssue.objects.create(
                session=session,
                issue_type=random.choice(issue_types),
                issue_details=random.choice(sample_descriptions),
                submitted_at=session.started_at
                + timedelta(minutes=random.randint(5, 30)),
                time_to_submit=random.randint(30, 300),
            )
            issues.append(issue)

        # Create sample comments
        sample_comments = [
            "I'm experiencing the exact same issue in my area!",
            "This has been a problem for months. When will it be fixed?",
            "Thank you for reporting this. We need more people to speak up.",
            "Has anyone contacted the local authorities about this?",
            "This is affecting our children's safety. Urgent action needed.",
            "I can confirm this issue exists in multiple locations.",
            "Thank you for bringing this to our attention. We are investigating.",
            "Update: Work has begun on addressing this issue.",
        ]

        for issue in issues[:10]:  # Add comments to first 10 issues
            num_comments = random.randint(1, 5)
            for j in range(num_comments):
                commenter_session = random.choice(sessions)
                is_govt = random.random() < 0.1  # 10% chance of government response

                PretotypeComment.objects.create(
                    issue=issue,
                    session=commenter_session,
                    content=random.choice(sample_comments),
                    commenter_name=(
                        f"Citizen {str(commenter_session.session_id)[:8]}"
                        if not is_govt
                        else "Lagos State Ministry"
                    ),
                    commenter_type="government" if is_govt else "citizen",
                    is_government_response=is_govt,
                    created_at=issue.submitted_at
                    + timedelta(hours=random.randint(1, 48)),
                )

        # Create sample reactions
        reaction_types = ["like", "support", "me_too", "heart", "angry", "sad"]
        for issue in issues:
            num_reactions = random.randint(2, 15)
            reacting_sessions = random.sample(
                sessions, min(num_reactions, len(sessions))
            )

            for session in reacting_sessions:
                PretotypeReaction.objects.create(
                    issue=issue,
                    session=session,
                    reaction_type=random.choice(reaction_types),
                )

        # Create some status updates
        status_types = [
            "reported",
            "acknowledged",
            "investigating",
            "in_progress",
            "resolved",
        ]
        for issue in random.sample(issues, 8):  # Update status for 8 issues
            status = random.choice(status_types[1:])  # Don't use 'reported'
            PretotypeIssueStatus.objects.create(
                issue=issue,
                status=status,
                message=f"Status update: Issue is now {status.replace('_', ' ')}.",
                updated_by="Lagos State Government",
                created_at=issue.submitted_at + timedelta(days=random.randint(1, 7)),
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created sample data: {len(issues)} issues, with comments and reactions"
            )
        )
