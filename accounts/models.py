from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Organisation(models.Model):
    """A church, music department or school, with its own people."""

    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Role(models.TextChoices):
    CONDUCTOR = "conductor", "Conductor"
    LIBRARIAN = "librarian", "Librarian"
    VIEWER = "viewer", "Viewer"


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Every user needs an email address.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        # Looks after the site from the admin pages; no organisation and no
        # role, so no powers inside the app itself.
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Someone who signs in, by email. Each belongs to one organisation with
    one role in it; accounts/permissions.py turns the role into what they
    may do.
    """

    email = models.EmailField("email address", unique=True)
    name = models.CharField(max_length=150, blank=True)
    organisation = models.ForeignKey(
        Organisation, null=True, blank=True, on_delete=models.CASCADE, related_name="users"
    )
    role = models.CharField(max_length=20, choices=Role.choices, blank=True)
    is_owner = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        constraints = [
            # In an organisation means having a role there, and the other
            # way round. A superuser has neither.
            models.CheckConstraint(
                condition=Q(organisation__isnull=True, role="") | (Q(organisation__isnull=False) & ~Q(role="")),
                name="user_organisation_and_role_together",
                violation_error_message="Someone in an organisation needs a role there, and only they can have one.",
            ),
        ]

    def __str__(self):
        return self.name or self.email

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name
