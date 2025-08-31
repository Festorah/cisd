import logging

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import TemplateView

logger = logging.getLogger(__name__)


class CustomAuthenticationForm(AuthenticationForm):
    """
    Custom authentication form with enhanced styling and validation
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add custom CSS classes to form fields
        self.fields["username"].widget.attrs.update(
            {
                "class": "form-control-custom",
                "placeholder": "Username or Email",
                "autocomplete": "username",
            }
        )

        self.fields["password"].widget.attrs.update(
            {
                "class": "form-control-custom",
                "placeholder": "Password",
                "autocomplete": "current-password",
            }
        )

        # Update field labels
        self.fields["username"].label = "Username or Email"
        self.fields["password"].label = "Password"

    def clean_username(self):
        """Allow login with email or username"""
        username = self.cleaned_data.get("username")

        # If it looks like an email, try to find user by email
        if "@" in username:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                user = User.objects.get(email=username)
                return user.username
            except User.DoesNotExist:
                pass

        return username


class CustomLoginView(auth_views.LoginView):
    """
    Custom login view that extends Django's LoginView with enhanced features
    """

    template_name = "core/auth/login.html"
    form_class = CustomAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        """Determine where to redirect after successful login"""
        # Check for next parameter
        next_url = self.request.GET.get("next")
        if next_url:
            return next_url

        # Redirect based on user role
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return reverse_lazy("admin_dashboard")  # Your admin dashboard
        else:
            return reverse_lazy("home")  # Regular users go to homepage

    def form_valid(self, form):
        """Handle successful login"""
        user = form.get_user()

        # Log successful login
        logger.info(f"Successful login for user: {user.username}")

        # Add success message
        messages.success(
            self.request, f"Welcome back, {user.first_name or user.username}!"
        )

        return super().form_valid(form)

    def form_invalid(self, form):
        """Handle failed login attempt"""
        logger.warning(
            f"Failed login attempt for: {form.cleaned_data.get('username', 'unknown')}"
        )

        # Add error message
        messages.error(
            self.request, "Invalid username/email or password. Please try again."
        )

        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Sign In - CISD",
                "page_description": "Sign in to your Centre for Inclusive Social Development account",
                "show_remember_me": True,
                "show_forgot_password": True,
            }
        )
        return context

    @method_decorator(sensitive_post_parameters())
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class CustomLogoutView(auth_views.LogoutView):
    """Custom logout view with confirmation and messaging"""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            username = request.user.username
            logger.info(f"User logged out: {username}")
            messages.success(request, "You have been successfully logged out.")

        return super().dispatch(request, *args, **kwargs)

    def get_next_page(self):
        """Redirect to home page after logout"""
        return reverse_lazy("dashboard:home")


class CustomPasswordResetView(auth_views.PasswordResetView):
    """Custom password reset view"""

    template_name = "core/auth/password_reset.html"
    email_template_name = "core/auth/password_reset_email.html"
    subject_template_name = "core/auth/password_reset_subject.txt"
    success_url = reverse_lazy("auth:password_reset_done")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Reset Password - CISD",
                "page_description": "Reset your CISD account password",
            }
        )
        return context


class CustomPasswordResetDoneView(auth_views.PasswordResetDoneView):
    """Password reset done view"""

    template_name = "core/auth/password_reset_done.html"


class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    """Password reset confirm view"""

    template_name = "core/auth/password_reset_confirm.html"
    success_url = reverse_lazy("password_reset_complete")


class CustomPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    """Password reset complete view"""

    template_name = "core/auth/password_reset_complete.html"


@login_required
def profile_view(request):
    """Simple profile view for logged-in users"""
    context = {
        "user": request.user,
        "page_title": f"Profile - {request.user.get_full_name() or request.user.username}",
    }
    return render(request, "core/auth/profile.html", context)


# Utility function for checking login status
def login_required_message(view_func):
    """
    Decorator that adds a helpful message when login is required
    """

    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, "Please sign in to access that page.")
        return login_required(view_func)(request, *args, **kwargs)

    return wrapper
