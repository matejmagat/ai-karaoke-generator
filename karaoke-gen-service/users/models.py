from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Django already provides is_staff and is_superuser.

    - is_staff=True: may access Django admin.
    - is_superuser=True: unrestricted admin permissions.
    """
    pass