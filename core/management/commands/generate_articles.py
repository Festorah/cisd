import random
from datetime import datetime, timedelta

from core.models import Article, Author, Category, CloudinaryMedia, ContentSection, Tag
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify


class Command(BaseCommand):
    help = "Generate 25 sample articles with varied content for testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing articles before generating new ones",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing existing articles...")
            Article.objects.all().delete()
            ContentSection.objects.all().delete()

        self.stdout.write("Creating sample data...")

        # Create sample users, categories, authors, tags, and media
        self.create_base_data()

        # Generate 25 articles
        self.generate_articles()

        self.stdout.write(
            self.style.SUCCESS("Successfully generated 25 sample articles!")
        )

    def create_base_data(self):
        """Create categories, authors, tags, and media files"""

        # Create admin user if doesn't exist
        self.admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@cisd.org",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            self.admin_user.set_password("admin123")
            self.admin_user.save()

        # Create categories
        self.categories = []
        category_data = [
            (
                "analysis",
                "Analysis",
                "#dc2626",
                "Deep dive into policy and social issues",
            ),
            ("campaign", "Campaign", "#059669", "Advocacy and campaign initiatives"),
            (
                "explainer",
                "Explainer",
                "#2563eb",
                "Clear explanations of complex topics",
            ),
            ("qna", "Q&A", "#7c3aed", "Question and answer sessions"),
            ("news", "News", "#ea580c", "Latest news and updates"),
            ("research", "Research", "#0891b2", "Research findings and reports"),
            ("opinion", "Opinion", "#be185d", "Opinion pieces and commentary"),
        ]

        for name, display_name, color, description in category_data:
            category, created = Category.objects.get_or_create(
                name=name,
                defaults={
                    "display_name": display_name,
                    "color_code": color,
                    "description": description,
                    "is_active": True,
                    "sort_order": len(self.categories),
                },
            )
            self.categories.append(category)

        # Create authors
        self.authors = []
        author_data = [
            (
                "Michael Daramola",
                "Senior Policy Analyst",
                "Leading expert in governance and civic participation",
            ),
            (
                "Folahan Johnson",
                "Gender & Inclusion Specialist",
                "Advocate for gender equity and social inclusion",
            ),
            (
                "Adebayo Toyosi",
                "Tax Justice Researcher",
                "Expert in fiscal policy and tax reform",
            ),
            (
                "Elisha Ekong",
                "Systems Change Coordinator",
                "Specialist in organizational development",
            ),
            (
                "Chioma Okafor",
                "Youth Engagement Lead",
                "Advocate for youth participation in governance",
            ),
            (
                "Kemi Adesanya",
                "Research Director",
                "Expert in behavioral science and policy research",
            ),
        ]

        for name, title, bio in author_data:
            author, created = Author.objects.get_or_create(
                name=name,
                defaults={
                    "title": title,
                    "bio": bio,
                    "is_active": True,
                    "is_featured": True,
                },
            )
            self.authors.append(author)

        # Create tags
        self.tags = []
        tag_names = [
            "Civic Participation",
            "Electoral Reform",
            "Gender Equality",
            "Youth Engagement",
            "Tax Justice",
            "System Change",
            "Behavioral Science",
            "Human-Centered Design",
            "Governance",
            "Policy Analysis",
            "Democracy",
            "Inclusion",
            "Social Development",
            "Community Engagement",
            "Transparency",
            "Accountability",
            "Public Policy",
            "Women Empowerment",
            "Fiscal Policy",
            "Civil Society",
        ]

        for tag_name in tag_names:
            tag, created = Tag.objects.get_or_create(
                name=tag_name,
                defaults={
                    "slug": slugify(tag_name),
                    "is_featured": random.choice([True, False]),
                    "usage_count": random.randint(1, 15),
                },
            )
            self.tags.append(tag)

        # Create sample media files
        self.media_files = []
        media_data = [
            (
                "Featured Article Hero",
                "https://res.cloudinary.com/demo/image/upload/w_1200,h_800/sample.jpg",
            ),
            (
                "Youth Engagement Campaign",
                "https://res.cloudinary.com/demo/image/upload/w_1200,h_800/sample2.jpg",
            ),
            (
                "Gender Tech Innovation",
                "https://res.cloudinary.com/demo/image/upload/w_1200,h_800/sample3.jpg",
            ),
            (
                "Tax Justice Report",
                "https://res.cloudinary.com/demo/image/upload/w_1200,h_800/sample4.jpg",
            ),
            (
                "Education Reform",
                "https://res.cloudinary.com/demo/image/upload/w_1200,h_800/sample5.jpg",
            ),
            (
                "Civic Empowerment",
                "https://res.cloudinary.com/demo/image/upload/w_1200,h_800/sample6.jpg",
            ),
            (
                "Systems Change Training",
                "https://res.cloudinary.com/demo/image/upload/w_1200,h_800/sample7.jpg",
            ),
            (
                "Democracy Conference",
                "https://res.cloudinary.com/demo/image/upload/w_1200,h_800/sample8.jpg",
            ),
        ]

        for title, url in media_data:
            media, created = CloudinaryMedia.objects.get_or_create(
                title=title,
                defaults={
                    "cloudinary_url": url,
                    "cloudinary_public_id": f"sample_{slugify(title)}",
                    "file_type": "image",
                    "file_format": "jpg",
                    "file_size": random.randint(500000, 2000000),
                    "width": 1200,
                    "height": 800,
                    "alt_text": title,
                    "uploaded_by": self.admin_user,
                },
            )
            self.media_files.append(media)

    def generate_articles(self):
        """Generate 25 diverse articles"""

        article_templates = [
            {
                "title": "Prototyping Water Access in Karamajiji Using Human-Centered Design",
                "category": "analysis",
                "excerpt": "Using human-centered design, CISD worked alongside the Karamajiji community to co-create and test water solutions that are affordable, sustainable, and truly meet local needs.",
                "tags": [
                    "Human-Centered Design",
                    "Community Engagement",
                    "Social Development",
                ],
            },
            {
                "title": "Youth Engagement Beyond the Ballot Box: A New Campaign Framework",
                "category": "campaign",
                "excerpt": "This campaign equips young Nigerians with the tools, platforms, and confidence to shape policies and participate meaningfully in governance processes.",
                "tags": ["Youth Engagement", "Civic Participation", "Democracy"],
            },
            {
                "title": "Gender Civic Tech Innovation: Centering Women's Voices",
                "category": "analysis",
                "excerpt": "Designing civic technology platforms that put women's voices and needs at the center of governance and policy engagement initiatives.",
                "tags": ["Gender Equality", "Civic Participation", "Women Empowerment"],
            },
            {
                "title": "Tackling Tax Evasion in Nigeria: New Strategies for 2025",
                "category": "research",
                "excerpt": "New strategies for combating illicit financial flows and strengthening domestic resource mobilization in Nigeria's evolving economic landscape.",
                "tags": ["Tax Justice", "Fiscal Policy", "Governance"],
            },
            {
                "title": "Where is the Empathy in Government? A Behavioral Analysis",
                "category": "explainer",
                "excerpt": "Nigeria continues to grapple with deep-rooted poverty. This analysis explores how behavioral science can foster more empathetic governance approaches.",
                "tags": ["Behavioral Science", "Governance", "Policy Analysis"],
            },
            {
                "title": "Electoral Reform and Democratic Consolidation",
                "category": "opinion",
                "excerpt": "Examining the critical reforms needed to strengthen Nigeria's democratic institutions and ensure free, fair, and credible elections.",
                "tags": ["Electoral Reform", "Democracy", "Governance"],
            },
            {
                "title": "Q&A: Building Inclusive Communities Through Policy",
                "category": "qna",
                "excerpt": "A conversation with community leaders about creating inclusive policies that address the needs of marginalized populations.",
                "tags": ["Inclusion", "Community Engagement", "Policy Analysis"],
            },
            {
                "title": "The Role of Civil Society in Democratic Governance",
                "category": "analysis",
                "excerpt": "Exploring how civil society organizations can strengthen democratic institutions and promote citizen participation in governance.",
                "tags": ["Civil Society", "Democracy", "Civic Participation"],
            },
            # Continue with more varied titles...
        ]

        # Extended article data with more variations
        additional_articles = [
            (
                "Budget Transparency: Lessons from Global Best Practices",
                "research",
                "Analyzing international approaches to budget transparency and their applicability to Nigeria.",
                ["Transparency", "Fiscal Policy", "Governance"],
            ),
            (
                "Women in Leadership: Breaking Barriers in Nigerian Politics",
                "analysis",
                "Examining the challenges and opportunities for women's political participation in Nigeria.",
                ["Gender Equality", "Women Empowerment", "Democracy"],
            ),
            (
                "Digital Governance: Technology for Citizen Engagement",
                "explainer",
                "How digital platforms can enhance citizen participation and government responsiveness.",
                ["Civic Participation", "Governance"],
            ),
            (
                "Community-Led Development: A Case Study from Rural Nigeria",
                "campaign",
                "Documenting successful community-led initiatives that drive sustainable development.",
                ["Community Engagement", "Social Development"],
            ),
            (
                "Anti-Corruption Strategies: Beyond Enforcement",
                "opinion",
                "Exploring preventive approaches to corruption through systemic and behavioral interventions.",
                ["Transparency", "Governance", "Behavioral Science"],
            ),
            (
                "Youth Political Participation: Trends and Challenges",
                "research",
                "Comprehensive analysis of youth engagement in Nigerian politics and recommendations for improvement.",
                ["Youth Engagement", "Democracy", "Civic Participation"],
            ),
            (
                "Inclusive Budgeting: Participatory Approaches to Public Finance",
                "explainer",
                "Understanding how participatory budgeting can make public finance more inclusive and responsive.",
                ["Fiscal Policy", "Inclusion", "Community Engagement"],
            ),
            (
                "Gender-Responsive Budgeting in Nigerian States",
                "analysis",
                "Evaluating the implementation of gender-responsive budgeting across Nigerian state governments.",
                ["Gender Equality", "Fiscal Policy", "Policy Analysis"],
            ),
            (
                "Climate Justice and Community Resilience",
                "campaign",
                "Building community capacity to address climate change impacts through inclusive adaptation strategies.",
                ["Social Development", "Community Engagement"],
            ),
            (
                "Behavioral Insights for Better Policy Implementation",
                "research",
                "Applying behavioral science to improve policy design and implementation effectiveness.",
                ["Behavioral Science", "Policy Analysis", "Governance"],
            ),
            (
                "Accountability Mechanisms in Local Government",
                "explainer",
                "Understanding the tools and processes that promote accountability at the local government level.",
                ["Accountability", "Governance", "Transparency"],
            ),
            (
                "Women's Economic Empowerment: Policy Interventions That Work",
                "analysis",
                "Evaluating successful policy interventions for women's economic empowerment in Nigeria.",
                ["Women Empowerment", "Gender Equality", "Policy Analysis"],
            ),
            (
                "Digital Literacy and Democratic Participation",
                "opinion",
                "Exploring the connection between digital literacy and meaningful democratic participation.",
                ["Democracy", "Civic Participation"],
            ),
            (
                "Strengthening Electoral Integrity Through Technology",
                "research",
                "Examining how technology can enhance electoral processes while maintaining democratic principles.",
                ["Electoral Reform", "Democracy"],
            ),
            (
                "Community Feedback Mechanisms in Public Service Delivery",
                "explainer",
                "How citizen feedback can improve public service quality and government responsiveness.",
                ["Accountability", "Governance", "Community Engagement"],
            ),
            (
                "Tax Policy and Social Equity in Nigeria",
                "analysis",
                "Analyzing the distributional effects of tax policy and recommendations for more equitable taxation.",
                ["Tax Justice", "Fiscal Policy"],
            ),
            (
                "Youth-Led Social Innovation: Lessons from Nigerian Entrepreneurs",
                "campaign",
                "Showcasing young social entrepreneurs who are driving innovation and social change.",
                ["Youth Engagement", "Social Development"],
            ),
        ]

        # Combine templates with additional articles
        all_articles = article_templates + [
            {"title": title, "category": cat, "excerpt": excerpt, "tags": tags}
            for title, cat, excerpt, tags in additional_articles
        ]

        # Generate exactly 25 articles
        for i in range(25):
            template = all_articles[i % len(all_articles)]

            # Add variation to titles if needed
            if i >= len(all_articles):
                template["title"] = (
                    f"{template['title']} - Part {i // len(all_articles) + 1}"
                )

            article = self.create_article(template, i)
            self.create_content_sections(article)

    def create_article(self, template, index):
        """Create a single article with varied fields"""

        category = next(
            (c for c in self.categories if c.name == template["category"]),
            random.choice(self.categories),
        )
        author = random.choice(self.authors)
        featured_image = (
            random.choice(self.media_files)
            if random.choice([True, False, True])
            else None
        )

        # Vary publish dates over the last 6 months
        base_date = timezone.now() - timedelta(days=180)
        publish_date = base_date + timedelta(days=random.randint(0, 180))

        article = Article.objects.create(
            title=template["title"],
            excerpt=template["excerpt"],
            category=category,
            author=author,
            featured_image=featured_image,
            status="published",
            published_date=publish_date,
            view_count=random.randint(50, 5000),
            share_count=random.randint(5, 500),
            comment_count=random.randint(0, 100),
            is_featured=random.choice([True, False, False, False]),  # 25% chance
            is_breaking=random.choice([True, False, False, False, False]),  # 20% chance
            allow_comments=random.choice([True, True, True, False]),  # 75% chance
            created_by=self.admin_user,
            last_modified_by=self.admin_user,
        )

        # Add tags
        article_tags = [tag for tag in self.tags if tag.name in template["tags"]]
        article_tags.extend(
            random.sample(
                [t for t in self.tags if t not in article_tags], random.randint(1, 3)
            )
        )
        article.tags.set(article_tags[:5])  # Max 5 tags per article

        return article

    def create_content_sections(self, article):
        """Create varied content sections for an article"""

        sample_content = {
            "paragraphs": [
                "Nigeria, home to over 210 million people, continues to grapple with deep-rooted poverty and inequality. According to the National Bureau of Statistics, over 40% of the population lives in extreme poverty, highlighting the urgent need for comprehensive policy interventions.",
                "The Centre for Inclusive Social Development (CISD) has been at the forefront of developing innovative approaches to address these challenges. Through human-centered design and behavioral science, we work alongside communities to co-create sustainable solutions.",
                "Our research demonstrates that when communities are actively involved in designing solutions to their own problems, the outcomes are more sustainable and effective. This participatory approach ensures that interventions are culturally appropriate and contextually relevant.",
                "Policy makers often overlook the importance of community input in the design phase. By centering the voices of those most affected by policies, we can create more inclusive and effective governance systems.",
                "The evidence is clear: participatory development approaches lead to better outcomes. Communities that are involved in designing their own development strategies show higher rates of success and sustainability.",
            ],
            "quotes": [
                "True development happens when communities are empowered to shape their own futures.",
                "Inclusion is not just a moral imperative; it is a practical necessity for sustainable development.",
                "When we design with communities rather than for them, we create solutions that last.",
                "Behavioral science helps us understand not just what people need, but how they make decisions.",
            ],
            "headings": [
                "Understanding Community Needs",
                "Policy Implications",
                "Implementation Challenges",
                "Measuring Impact",
                "Future Directions",
                "Lessons Learned",
                "Recommendations",
            ],
            "interview_questions": [
                "What are the main challenges facing your community?",
                "How can policy makers better engage with local communities?",
                "What role does technology play in modern governance?",
                "How do you measure the success of community interventions?",
                "What advice would you give to other community leaders?",
            ],
            "interview_answers": [
                "The biggest challenge is ensuring that community voices are heard and acted upon by policy makers. We need more systematic approaches to community engagement.",
                "Policy makers need to move beyond consultation to genuine collaboration. This means involving communities in the design phase, not just seeking feedback after policies are drafted.",
                "Technology can be a powerful tool for engagement, but it must be accessible and user-friendly. We need to bridge the digital divide to ensure inclusive participation.",
                "Success should be measured not just by outputs, but by outcomes and impact. We need to track both quantitative and qualitative indicators of community well-being.",
                "My advice is to start small, build trust, and always remember that sustainable change takes time. Be patient but persistent in your advocacy efforts.",
            ],
        }

        section_order = 0

        # Always start with an introductory paragraph
        ContentSection.objects.create(
            article=article,
            section_type="paragraph",
            order=section_order,
            content=random.choice(sample_content["paragraphs"]),
            is_visible=True,
        )
        section_order += 1

        # Create 4-8 varied content sections
        num_sections = random.randint(4, 8)
        section_types = ["paragraph", "heading", "quote", "interview", "image"]

        for i in range(num_sections):
            section_type = random.choice(section_types)

            section_data = {
                "article": article,
                "section_type": section_type,
                "order": section_order,
                "is_visible": True,
            }

            if section_type == "paragraph":
                section_data["content"] = random.choice(sample_content["paragraphs"])

            elif section_type == "heading":
                section_data["title"] = random.choice(sample_content["headings"])
                section_data["content"] = random.choice(sample_content["headings"])

            elif section_type == "quote":
                section_data["content"] = random.choice(sample_content["quotes"])

            elif section_type == "interview":
                section_data["question"] = random.choice(
                    sample_content["interview_questions"]
                )
                section_data["answer"] = random.choice(
                    sample_content["interview_answers"]
                )
                section_data["interviewer"] = "CISD Staff"
                section_data["interviewee"] = random.choice(
                    [author.name for author in self.authors]
                )

            elif section_type == "image" and self.media_files:
                media_file = random.choice(self.media_files)
                section_data["media_file"] = media_file
                section_data["caption"] = (
                    f"Illustrating key concepts discussed in {article.title}"
                )
                section_data["alt_text"] = media_file.alt_text

            ContentSection.objects.create(**section_data)
            section_order += 1

        self.stdout.write(
            f"Created article: {article.title} with {section_order} sections"
        )
