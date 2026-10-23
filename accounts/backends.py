from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class UserWithOrganisationBackend(ModelBackend):
    """
    Django's own sign-in, except that loading the signed-in person on each
    request brings their organisation in the same query. Nearly every page
    needs the organisation, so this saves a second query on every request.
    """

    def get_user(self, user_id):
        User = get_user_model()
        try:
            user = User._default_manager.select_related("organisation").get(pk=user_id)
        except User.DoesNotExist:
            return None
        return user if self.user_can_authenticate(user) else None
