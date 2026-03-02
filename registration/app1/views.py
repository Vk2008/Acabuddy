import json
from django.shortcuts import render, redirect, HttpResponse, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from .models import Question, Answer, MentorSession
from .forms import QuestionForm, AnswerForm, ProfilePictureForm, UsernameChangeForm
from collections import Counter
from django.db.models import Count
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator
from ai_pipelines.ai_verifier import verify_answer
from ai_pipelines.mentor import call_free_model
from django.contrib import messages
from django.http import JsonResponse
from .similarity import find_similar_questions
from datetime import date, timedelta
from django .views.decorators.csrf import csrf_exempt
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
            title = form.cleaned_data['title']
            body = form.cleaned_data['body']
            combined_text = title + ' ' + body

            if "force_post" not in request.POST:
                similar_questions = find_similar_questions(combined_text)

                if similar_questions:
                    return render(request, 'similar_questions.html', {'form': form, 'similar_questions': similar_questions})
            
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

MENTOR_SYSTEM_PROMPT = """
You are Acabuddy Mentor.

Rules:
- Guide step by step.
- Ask ONE question at a time.
- NEVER give the full solution.
- Encourage thinking.
- Be collaborative and natural.
- If student struggles, give small hints. Motivate.
- Always end with a question UNLESS THE ANSWER IS COMPLETE.

If student asks for full solution:
Encourage them to try once more before revealing.
"""

@csrf_exempt
def start_mentor(request):
    if request.method == "POST":
        data = json.loads(request.body)
        question_id = data.get("question_id")

        question = get_object_or_404(Question, id=question_id)

        # Only question owner allowed
        if request.user != question.user:
            return JsonResponse({"error": "Unauthorized"}, status=403)

        system_msg = {"role": "system", "content": MENTOR_SYSTEM_PROMPT}
        user_msg = {
            "role": "user",
            "content": f"The student asked: {question.title}. Start guiding them."
        }

        conversation = [system_msg, user_msg]

        mentor_reply = call_free_model(conversation)

        conversation.append({"role": "assistant", "content": mentor_reply})

        session = MentorSession.objects.create(
            user=request.user,
            question=question,
            conversation=conversation
        )

        return JsonResponse({
            "session_id": session.id,
            "mentor_message": mentor_reply
        })


@csrf_exempt
def mentor_chat(request):
    if request.method == "POST":
        data = json.loads(request.body)
        session_id = data.get("session_id")
        user_input = data.get("message")

        session = get_object_or_404(MentorSession, id=session_id)

        if request.user != session.user:
            return JsonResponse({"error": "Unauthorized"}, status=403)

        session.conversation.append({
            "role": "user",
            "content": user_input
        })

        # Limit context size
        if len(session.conversation) > 12:
            session.conversation = session.conversation[-12:]

        mentor_reply = call_free_model(session.conversation)

        session.conversation.append({
            "role": "assistant",
            "content": mentor_reply
        })

        session.save()

        return JsonResponse({"mentor_message": mentor_reply})

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

    achievement = user.profile.get_achievement_title()

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
        'achievement_title': achievement['title'],
        'badge_url': achievement['badge_url'],
        'current_streak': current_streak,
        'longest_streak': longest_streak,
        'streak_data': streak_data,
    }

    return render(request, 'profile.html', context)


@login_required(login_url='login')
def ProgressPage(request):
    user = request.user
    profile = user.profile

    # Basic counts
    question_count = Question.objects.filter(user=user).count()
    answer_count = Answer.objects.filter(user=user).count()
    verified_answers = Answer.objects.filter(
        user=user,
        ai_score__gte=0.6
    ).count()

    # XP Calculation
    xp = question_count * 5 + answer_count * 10

    achievement = user.profile.get_achievement_title()

    # Level thresholds
    LEVELS = [0, 50, 150, 350, 700, 1200, 2000]

    level = 1
    current_level_xp = 0
    next_level_xp = None

    for i in range(len(LEVELS)):
        if xp >= LEVELS[i]:
            level = i + 1
            current_level_xp = LEVELS[i]
            if i + 1 < len(LEVELS):
                next_level_xp = LEVELS[i + 1]
            else:
                next_level_xp = None

    if next_level_xp:
        xp_into_level = xp - current_level_xp
        xp_required = next_level_xp - current_level_xp
        progress_percent = int((xp_into_level / xp_required) * 100)
        xp_to_next = next_level_xp - xp
    else:
        xp_into_level = 0
        xp_required = 0
        progress_percent = 100
        xp_to_next = 0

    # AI Verified %
    ai_verified_percent = 0
    if answer_count > 0:
        ai_verified_percent = int((verified_answers / answer_count) * 100)
    from datetime import date, timedelta
    # Weekly Activity (Last 7 days)
    today = date.today()
    weekly_data = []

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)

        q_count = Question.objects.filter(
            user=user,
            created_at__date=day
        ).count()

        a_count = Answer.objects.filter(
            user=user,
            created_at__date=day
        ).count()

        weekly_data.append({
            "day": day.strftime("%a"),
            "questions": q_count,
            "answers": a_count,
        })

    # Subject Breakdown
    tag_counter = Counter()

    user_questions = Question.objects.filter(user=user).exclude(tags='')
    for q in user_questions:
        tags = [t.strip() for t in q.tags.split(',') if t.strip()]
        tag_counter.update(tags)

    total_tagged = sum(tag_counter.values())
    subjects = []

    for tag, count in tag_counter.items():
        percent = int((count / total_tagged) * 100) if total_tagged > 0 else 0
        subjects.append({
            "name": tag,
            "percent": percent
        })

    context = {
        "xp": xp,
        "level": level,
        "progress_percent": progress_percent,
        "xp_to_next": xp_to_next,
        "current_streak": profile.current_streak,
        "question_count": question_count,
        "answer_count": answer_count,
        "verified_answers": verified_answers,
        "ai_verified_percent": ai_verified_percent,
        "weekly_data": weekly_data,
        "subjects": subjects,
        'achievement_title': achievement['title'],
        'badge_url': achievement['badge_url'],
    }

    return render(request, "progress.html", context)

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
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('pass')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            error = "Incorrect username or password."
    return render(request, 'login.html', {"error": error})

def SignupPage(request):
    error = None
    success = None
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        pass1 = request.POST.get('password1')
        pass2 = request.POST.get('password2')

        if pass1!= pass2:
            error = "Passwords do not match"
        elif User.objects.filter(username=username).exists():
            error = "Username already exists."
        elif User.objects.filter(email=email).exists():
            error = "Email already registered."
        else:
            user = User.objects.create_user(username, email, pass1)
            user.save()
            success = "Account created successfully! You can now log in."


    return render(request, 'signup.html', {'error': error, 'success': success})

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

