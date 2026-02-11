from django.shortcuts import render, redirect, HttpResponse, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from .models import Question, Answer
from .forms import QuestionForm, AnswerForm, ProfilePictureForm, UsernameChangeForm
from collections import Counter
from django.db.models import Count
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator
from ai_pipelines.ai_verifier import verify_answer
from django.contrib import messages
from django.http import JsonResponse
# Create your views here.

@login_required(login_url = 'login')
def HomePage(request):

    tag = request.GET.get('tag')

    if tag:
        questions = Question.objects.filter(tags__icontains=tag).order_by('-created_at')
    else:
        questions = Question.objects.select_related('user').order_by("-created_at")

    for q in questions:
        if q.tags:
            q.tag_list = [t.strip() for t in q.tags.split(',') if t.strip()]
        else:
            q.tag_list = []
    
    tag_counter = Counter()

    for q in Question.objects.exclude(tags=''):
        tags = [t.strip() for t in q.tags.split(',') if t.strip()]
        tag_counter.update(tags)
    top_tags = [tag for tag, count in tag_counter.most_common(3)]

    context = {
        'questions': questions,
        'active_tag': tag,
        'top_tags': top_tags
    }
    return render(request, 'home.html', context)

@login_required(login_url='login')
def ask_question(request):
    if request.method == "POST":
        form = QuestionForm(request.POST, request.FILES)
        if form.is_valid():
            q = form.save(commit=False)
            q.user = request.user
            q.save()
            return redirect("home")
    else:
        form = QuestionForm()
    return render(request, "ask_question.html", {"form": form})

@login_required(login_url='login')
def question_detail(request, question_id):
    question = get_object_or_404(Question, id=question_id)
    answers = question.answers.all().order_by("-created_at")

    if request.method == "POST":
        form = AnswerForm(request.POST, request.FILES)
        if form.is_valid():
            a = form.save(commit=False)
            a.user = request.user
            a.question = question
            a.save()

            from ai_pipelines.dispatcher import run_ai_verification
            run_ai_verification(a)

            return redirect("question_detail", question_id=question.id)
    else:
        form = AnswerForm()

    return render(request, "question_detail.html", {
        "question": question,
        "answers": answers,
        "form": form,
    })

@login_required(login_url='login')
def ProfilePage(request):
    user = request.user

    # total questions by user
    my_questions = Question.objects.filter(user=user)
    question_count = my_questions.count()

    # total questions answered by user
    my_answers = Answer.objects.filter(user=user)
    answer_count = my_answers.count()

    # points
    xp = question_count * 5 + answer_count * 10

    achievement_title = user.profile.get_achievement_title()

    # Get streak data
    current_streak = user.profile.current_streak
    longest_streak = user.profile.longest_streak

    # Generate streak calendar data (last 30 days)
    from datetime import date, timedelta
    today = date.today()
    streak_data = []
    
    # Get all activity dates for the user
    question_dates = set(Question.objects.filter(user=user).values_list('created_at__date', flat=True))
    answer_dates = set(Answer.objects.filter(user=user).values_list('created_at__date', flat=True))
    activity_dates = question_dates.union(answer_dates)
    
    for i in range(30):
        day = today - timedelta(days=29-i)
        has_activity = day in activity_dates
        streak_data.append({
            'date': day,
            'has_activity': has_activity,
            'day_name': day.strftime('%a')[:1]  # First letter of day
        })

    users = User.objects.filter(is_superuser = False)
    leaderboard = []
    for u in users:
        q_count = Question.objects.filter(user=u).count()
        a_count = Answer.objects.filter(user=u).count()
        xp_count = q_count * 5 + a_count * 10
        leaderboard.append({'user': u, 'xp': xp_count})

    rank = next((i+1 for i, entry in enumerate(sorted(leaderboard, key=lambda x: x['xp'], reverse=True)) if entry['user'] == user), None)
    leaderboard = sorted(leaderboard, key = lambda x: x['xp'], reverse = True)[:10]
    context = {
        'profile_name': user.username,
        'question_count': question_count,
        'answer_count': answer_count,
        'xp': xp,
        'my_questions': my_questions,
        'leaderboard': leaderboard,
        'rank': rank,
        'achievement_title': achievement_title,
        'current_streak': current_streak,
        'longest_streak': longest_streak,
        'streak_data': streak_data,
    }

    return render(request, 'profile.html', context)

@login_required(login_url='login')
def account_settings(request):
    user = request.user
    profile = user.profile

    username_form = UsernameChangeForm(instance=user)
    picture_form = ProfilePictureForm(instance=profile)
    password_form = PasswordChangeForm(user=user)

    if request.method == "POST":
        if "update_username" in request.POST:
            username_form = UsernameChangeForm(request.POST, instance=user)
            if username_form.is_valid():
                username_form.save()
                return redirect('account_settings')

        elif "update_picture" in request.POST:
            picture_form = ProfilePictureForm(
                request.POST, request.FILES, instance=profile
            )
            if picture_form.is_valid():
                picture_form.save()
                return redirect('account_settings')

        elif "update_password" in request.POST:
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                return redirect('account_settings')

    return render(request, "account_settings.html", {
        "username_form": username_form,
        "picture_form": picture_form,
        "password_form": password_form,
    })

@login_required(login_url="login")
def LeaderboardPage(request):
    users = User.objects.exclude(is_superuser=True)

    leaderboard = []
    for user in users:
        question_count = Question.objects.filter(user=user).count()
        answer_count = Answer.objects.filter(user=user).count()
        xp = question_count * 5 + answer_count * 10

        leaderboard.append({
            "user": user,
            "xp": xp
        })

    leaderboard.sort(key=lambda x: x["xp"], reverse=True)

    for idx, entry in enumerate(leaderboard, start=1):
        entry["rank"] = idx

    paginator = Paginator(leaderboard, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "leaderboard.html", {
        "page_obj": page_obj
    })

@login_required(login_url='login')
def delete_question(request, question_id):
    """Delete a question (only by owner)"""
    question = get_object_or_404(Question, id=question_id)
    
    if request.user == question.user:
        question.delete()
        messages.success(request, 'Question deleted successfully!')
        return redirect('home')
    else:
        messages.error(request, 'You can only delete your own questions!')
        return redirect('question_detail', question_id=question_id)

@login_required(login_url='login')
def delete_answer(request, answer_id):
    """Delete an answer (only by owner)"""
    answer = get_object_or_404(Answer, id=answer_id)
    question_id = answer.question.id
    
    if request.user == answer.user:
        answer.delete()
        messages.success(request, 'Answer deleted successfully!')
    else:
        messages.error(request, 'You can only delete your own answers!')
    
    return redirect('question_detail', question_id=question_id)

@login_required(login_url='login')
def edit_question(request, question_id):
    """Edit a question (only by owner)"""
    question = get_object_or_404(Question, id=question_id)
    
    if request.user != question.user:
        messages.error(request, 'You can only edit your own questions!')
        return redirect('question_detail', question_id=question_id)
    
    if request.method == "POST":
        form = QuestionForm(request.POST, request.FILES, instance=question)
        if form.is_valid():
            form.save()
            messages.success(request, 'Question updated successfully!')
            return redirect('question_detail', question_id=question_id)
    else:
        form = QuestionForm(instance=question)
    
    return render(request, "edit_question.html", {
        "form": form,
        "question": question
    })

@login_required(login_url='login')
def edit_answer(request, answer_id):
    """Edit an answer (only by owner)"""
    answer = get_object_or_404(Answer, id=answer_id)
    
    if request.user != answer.user:
        messages.error(request, 'You can only edit your own answers!')
        return redirect('question_detail', question_id=answer.question.id)
    
    if request.method == "POST":
        form = AnswerForm(request.POST, request.FILES, instance=answer)
        if form.is_valid():
            form.save()
            
            # Re-run AI verification
            from ai_pipelines.dispatcher import run_ai_verification
            run_ai_verification(answer)
            
            messages.success(request, 'Answer updated and re-verified!')
            return redirect('question_detail', question_id=answer.question.id)
    else:
        form = AnswerForm(instance=answer)
    
    return render(request, "edit_answer.html", {
        "form": form,
        "answer": answer
    })

def LoginPage(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('pass')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            return HttpResponse('User not found.')
    return render(request, 'login.html')

def SignupPage(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        pass1 = request.POST.get('password1')
        pass2 = request.POST.get('password2')

        if pass1!= pass2:
            return HttpResponse("Passwords do not match")
        else:
            user = User.objects.create_user(username, email, pass1)
            user.save()
            return redirect('login')


    return render(request, 'signup.html')

def Logout(request):
    logout(request)
    return redirect('login')

def landing_page(request):
    return render(request, 'landing_page.html')


def derive_domain_from_tags(tags):
    """
    Converts tags like 'Physics, Quantum Mechanics'
    into a domain string usable by the AI.
    """
    if not tags:
        return "General"

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    return ", ".join(tag_list[:3])  # limit to top 3

