from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    # make email unique so we can login with email
    email = models.EmailField(unique=True)

    # optional phone field (premium account info)
    phone = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return self.email or self.username
