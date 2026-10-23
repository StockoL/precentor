import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from .querysets import OrganisationQuerySet


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
    def get_by_natural_key(self, email):
        # Django's login looks people up through this, so signing in with
        # Anne@Example.com finds anne@example.com.
        return self.get(email__iexact=email)

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
            # Owning means owning an organisation.
            models.CheckConstraint(
                condition=Q(is_owner=False) | Q(organisation__isnull=False),
                name="user_owner_has_organisation",
                violation_error_message="Only someone in an organisation can own it.",
            ),
            # An owner runs the organisation, which a read-only role can't.
            models.CheckConstraint(
                condition=Q(is_owner=False) | ~Q(role=Role.VIEWER),
                name="user_owner_is_not_a_viewer",
                violation_error_message="An owner must be a Conductor or a Librarian.",
            ),
            # One owner per organisation, so "the owner" always means one
            # person: handing over is a swap, and there's no last owner to
            # lose by accident.
            models.UniqueConstraint(
                fields=["organisation"],
                condition=Q(is_owner=True),
                name="user_one_owner_per_organisation",
                violation_error_message="This organisation already has an owner.",
            ),
            # One account per address, however it's typed: Anne@Example.com
            # and anne@example.com are the same inbox.
            models.UniqueConstraint(
                Lower("email"),
                name="user_email_unique_ignoring_case",
                violation_error_message="Someone already has an account with this email address.",
            ),
        ]

    def save(self, *args, **kwargs):
        # Stored lowercase, so one address is always shown and looked up
        # the same way. Django's normalize_email only lowercases the domain.
        self.email = self.email.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name or self.email

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name


class Invitation(models.Model):
    """
    A link, shared by hand, that lets one person join an organisation in a
    given role. It works once and lasts a week. Only a fingerprint of its
    secret is kept, so the stored rows can't be turned back into working
    links; the link itself is shown once, when it's made.
    """

    LIFETIME = timedelta(days=7)

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="invitations")
    objects = OrganisationQuerySet.as_manager()
    role = models.CharField(max_length=20, choices=Role.choices)
    note = models.CharField(
        "who it's for", max_length=100, blank=True, help_text="Only for telling invitations apart, e.g. Anne, alto."
    )
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_by = models.ForeignKey("User", null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey("User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]  # noqa

    @staticmethod
    def _fingerprint(token):
        return hashlib.sha256(token.encode()).hexdigest()

    @classmethod
    def make(cls, *, organisation, role, created_by, note=""):
        """A new invitation and the secret for its link, which is the only
        time the secret exists outside the person's browser."""
        token = secrets.token_urlsafe(32)
        invitation = cls.objects.create(
            organisation=organisation, role=role, created_by=created_by, note=note,
            token_hash=cls._fingerprint(token), expires_at=timezone.now() + cls.LIFETIME,
        )
        return invitation, token

    @classmethod
    def usable(cls):
        return cls.objects.filter(used_at__isnull=True, expires_at__gt=timezone.now())

    @classmethod
    def find(cls, token):
        """The invitation a link's secret opens, if it still works; else None."""
        return cls.usable().select_related("organisation").filter(token_hash=cls._fingerprint(token)).first()

    def use(self, user):
        """Mark it used by this person. True only for the first caller: the
        update checks it's still unused, so two people joining at the same
        moment can't both get in."""
        now = timezone.now()
        claimed = Invitation.usable().filter(pk=self.pk).update(used_at=now, used_by=user)
        return claimed == 1

    def __str__(self):
        return f"{self.get_role_display()} invitation to {self.organisation}"
