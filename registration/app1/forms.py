from django import forms
from django.contrib.auth.models import User
from .models import Question, Answer, Profile

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ["title", "body", "tags", "image"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "input-field",
                "placeholder": "Enter your question title"
            }),
            "body": forms.Textarea(attrs={
                "class": "input-field",
                "placeholder": "Describe your question in detail"
            }),
            "tags": forms.TextInput(attrs={
                "placeholder": "e.g. Physics, Mathematics"
            })
        }

class AnswerForm(forms.ModelForm):
    class Meta:
        model = Answer
        fields = ["body", "image"]

class UsernameChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username']

class ProfilePictureForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar']