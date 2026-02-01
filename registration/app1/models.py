from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from cloudinary.models import CloudinaryField


class Question(models.Model):
    title = models.CharField(max_length=255)
    body = models.TextField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tags = models.CharField(max_length = 200, blank = True, help_text = "Comma-separated tags")
    created_at = models.DateTimeField(auto_now_add=True)
    image = CloudinaryField(
    'image',
    blank=True,
    null=True
)
    def tag_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]

class Answer(models.Model):
    question = models.ForeignKey(Question, related_name="answers", on_delete=models.CASCADE)
    body = models.TextField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    ai_score = models.FloatField(null=True, blank=True)
    ai_reasoning = models.TextField(blank=True)
    ai_audit = models.TextField(blank=True)

    image = CloudinaryField(
    'image',
    blank=True,
    null=True
)
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)

    def __str__(self):
        return self.user.username
    
@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:

        Profile.objects.create(user=instance)
