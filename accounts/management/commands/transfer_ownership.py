from django.core.management.base import BaseCommand, CommandError

from accounts.models import Organisation, Role, User


def describe(user):
    if user is None:
        return "nobody"
    who = f"{user.name} <{user.email}>" if user.name else user.email
    state = "" if user.is_active else ", account switched off"
    return f"{who}, {user.get_role_display()}{state}"


class Command(BaseCommand):
    help = (
        "Make one of a church's Conductors or Librarians its owner, for when the "
        "owner can't do it from Members. Run it only on a written request from "
        "someone with authority over the church, as the README describes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--church", type=int, required=True, help="The church's id, as the admin site shows it.")
        parser.add_argument("--to", required=True, dest="email", help="The new owner's email address.")

    def handle(self, *args, church, email, **options):
        organisation = Organisation.objects.filter(pk=church).first()
        if organisation is None:
            raise CommandError(f"No church has the id {church}.")
        members = User.objects.filter(organisation=organisation)
        successor = members.filter(email__iexact=email).first()
        if successor is None:
            raise CommandError(f"Nobody in {organisation} has the address {email}.")
        owner = members.filter(is_owner=True).first()
        if successor == owner:
            raise CommandError(f"{successor} is already the owner.")
        if not successor.is_active or successor.role not in (Role.CONDUCTOR, Role.LIBRARIAN):
            raise CommandError(f"{describe(successor)} can't be the owner: only an active Conductor or Librarian can.")

        self.stdout.write(f"{organisation}. Owner before: {describe(owner)}")
        if owner is None:
            # Left without one, as between two saves in the admin site.
            successor.is_owner = True
            successor.save(update_fields=["is_owner"])
        else:
            # The same swap as Members uses, in one transaction; the old
            # owner keeps their role, even if their account is switched off.
            owner.hand_ownership_to(successor)
        self.stdout.write(self.style.SUCCESS(f"{organisation}. Owner after: {describe(successor)}"))
