from core.models import Article, Author, Category
from dashboard.managers import DashboardStatsManager
from dashboard.utils.file_processors import FileProcessor
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse


class DashboardViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser("admin", "admin@test.com", "password")
        self.category = Category.objects.create(
            name="analysis", display_name="Analysis"
        )
        self.author = Author.objects.create(name="Test Author", email="author@test.com")

    def test_dashboard_home_view(self):
        self.client.login(username="admin", password="password")
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard Overview")

    def test_article_creation(self):
        self.client.login(username="admin", password="password")

        article_data = {
            "title": "Test Article",
            "excerpt": "Test excerpt",
            "category_id": str(self.category.id),
            "author_id": str(self.author.id),
            "status": "draft",
            "content_sections": [
                {"type": "paragraph", "content": "Test paragraph content"}
            ],
        }

        response = self.client.post(
            reverse("dashboard:save_article_ajax"),
            data=article_data,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

    def test_file_upload(self):
        self.client.login(username="admin", password="password")

        # Create a test file
        test_file = SimpleUploadedFile(
            "test.txt", b"Test file content for processing.", content_type="text/plain"
        )

        response = self.client.post(
            reverse("dashboard:upload_file_ajax"), {"file": test_file}
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])


class FileProcessorTest(TestCase):
    def test_text_file_processing(self):
        test_file = SimpleUploadedFile(
            "test.txt",
            b"This is a test paragraph.\n\nThis is another paragraph.",
            content_type="text/plain",
        )

        result = FileProcessor.process_file(test_file)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["sections"]), 2)


class DashboardStatsTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="analysis", display_name="Analysis"
        )
        self.author = Author.objects.create(name="Test Author", email="author@test.com")

    def test_overview_stats(self):
        # Create test articles
        Article.objects.create(
            title="Test Article 1",
            excerpt="Test excerpt",
            category=self.category,
            author=self.author,
            status="published",
        )

        stats = DashboardStatsManager.get_overview_stats()

        self.assertIn("articles", stats)
        self.assertEqual(stats["articles"]["total"], 1)
        self.assertEqual(stats["articles"]["published"], 1)
