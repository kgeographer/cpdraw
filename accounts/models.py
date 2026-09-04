from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.TextField(max_length=200, null=False, blank=False)
    affiliation = models.TextField(max_length=200, blank=True)
    web_page = models.URLField(null=True)
    # user_type dropped in WO-0.5 §1.5 — used nowhere but its own form/template.


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # get_or_create guards a User that predates this app (e.g. a bare-DB
    # `createsuperuser`) and so has no Profile row yet.
    profile, _ = Profile.objects.get_or_create(user=instance)
    profile.save()
