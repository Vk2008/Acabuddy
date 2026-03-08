from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from cloudinary.models import CloudinaryField
from django.utils import timezone
from datetime import timedelta
from pgvector.django import VectorField


class Question(models.Model):
    title = models.CharField(max_length=255)
    body = models.TextField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tags = models.CharField(max_length = 200, blank = True, help_text = "Comma-separated tags")
    embedding = VectorField(dimensions=384, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    image = CloudinaryField(
    'image',
    blank=True,
    null=True
    )
    def tag_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]
    
    def save(self, *args, **kwargs):

        if self.embedding is None or self.pk is None:
            from registration.embeddings import embed
            text = f"{self.title} {self.body}"
            self.embedding = embed(text)

        super().save(*args, **kwargs)


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


class MentorSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey("Question", on_delete=models.CASCADE)
    conversation = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"MentorSession {self.id} - {self.user.username}"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.user.username
    
    def update_streak(self):
        """Update user's streak based on activity"""
        today = timezone.now().date()
        
        if self.last_activity_date is None:
            # First activity
            self.current_streak = 1
            self.last_activity_date = today
        elif self.last_activity_date == today:
            # Already counted today
            return
        elif self.last_activity_date == today - timedelta(days=1):
            # Consecutive day
            self.current_streak += 1
            self.last_activity_date = today
        else:
            # Streak broken
            self.current_streak = 1
            self.last_activity_date = today
        
        # Update longest streak
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak
        
        self.save()

    def get_achievement_title(self):
        """Return achievement title based on XP"""
        # Calculate XP
        question_count = Question.objects.filter(user=self.user).count()
        
        # Count only verified answers (ai_score >= 0.6)
        answer_count = Answer.objects.filter(
            user=self.user,
            ai_score__gte=0.6
        ).count()
        
        xp = question_count * 5 + answer_count * 10
        
        achievements = [
            (2000, "Academic Authority", "/static/badges/academic_authority.png"),
            (1200, "Subject Luminary", "/static/badges/subject_luminary.png"),
            (700,  "Scholarly Anchor", "/static/badges/scholarly_anchor.png"),
            (350,  "Knowledge Architect", "/static/badges/knowledge_architect.png"),
            (150,  "Insight Crafter", "/static/badges/insight_crafter.png"),
            (50,   "Concept Seeker", "/static/badges/concept_seeker.png"),
            (0,    "Fresh Mind", "/static/badges/fresh_mind.png"),
        ]

        for threshold, title, badge in achievements:
            if xp >= threshold:
                return {"title": title, "badge_url": badge, "xp": xp}

        # Fallback
        return {"title": "Fresh Mind", "badge_url": "/static/badges/fresh_mind.png", "xp": xp}
    
    def get_xp(self):
        question_count = Question.objects.filter(user=self.user).count()
        verified_answers = Answer.objects.filter(
            user=self.user,
            ai_score__gte=0.6
        ).count()

        return question_count * 5 + verified_answers * 10
    
@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:

        Profile.objects.create(user=instance)
