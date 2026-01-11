from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.core.paginator import Paginator
import json

from .models import User, Post, Like, Follow


def index(request):
    # Handle new post creation
    if request.method == "POST" and request.user.is_authenticated:
        content = request.POST.get("content", "").strip()
        if content:
            Post.objects.create(user=request.user, content=content)
            return HttpResponseRedirect(reverse("index"))
    
    # Get all posts
    posts = Post.objects.all()
    
    # Pagination
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get likes for current user if authenticated
    user_likes = set()
    if request.user.is_authenticated:
        user_likes = set(Like.objects.filter(user=request.user).values_list('post_id', flat=True))
    
    return render(request, "network/index.html", {
        "page_type": "all",
        "page_obj": page_obj,
        "user_likes": user_likes
    })


def login_view(request):
    if request.method == "POST":

        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "network/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "network/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "network/register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "network/register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "network/register.html")


@login_required
def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    
    # Get follower and following counts
    followers_count = Follow.objects.filter(following=profile_user).count()
    following_count = Follow.objects.filter(follower=profile_user).count()
    
    # Get all posts by this user
    posts = Post.objects.filter(user=profile_user)
    
    # Pagination
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Check if current user follows this profile user
    is_following = False
    if request.user.is_authenticated and request.user != profile_user:
        is_following = Follow.objects.filter(follower=request.user, following=profile_user).exists()
    
    # Get likes for current user if authenticated
    user_likes = set()
    if request.user.is_authenticated:
        user_likes = set(Like.objects.filter(user=request.user).values_list('post_id', flat=True))
    
    return render(request, "network/index.html", {
        "page_type": "profile",
        "profile_user": profile_user,
        "followers_count": followers_count,
        "following_count": following_count,
        "page_obj": page_obj,
        "is_following": is_following,
        "user_likes": user_likes
    })


@login_required
def follow(request, username):
    if request.method == "POST":
        profile_user = get_object_or_404(User, username=username)
        
        # User cannot follow themselves
        if request.user == profile_user:
            return HttpResponseRedirect(reverse("profile", args=[username]))
        
        # Toggle follow status
        follow_obj, created = Follow.objects.get_or_create(
            follower=request.user,
            following=profile_user
        )
        
        if not created:
            # If it already exists, unfollow
            follow_obj.delete()
        
        return HttpResponseRedirect(reverse("profile", args=[username]))
    
    return HttpResponseRedirect(reverse("index"))


@login_required
def following(request):
    # Get all users that the current user follows
    following_users = Follow.objects.filter(follower=request.user).values_list('following', flat=True)
    
    # Get all posts from users that the current user follows
    posts = Post.objects.filter(user__in=following_users)
    
    # Pagination
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get likes for current user
    user_likes = set(Like.objects.filter(user=request.user).values_list('post_id', flat=True))
    
    return render(request, "network/index.html", {
        "page_type": "following",
        "page_obj": page_obj,
        "user_likes": user_likes
    })


@login_required
def edit_post(request, post_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST request required."}, status=400)
    
    post = get_object_or_404(Post, pk=post_id)
    
    # Security: ensure user can only edit their own posts
    if post.user != request.user:
        return JsonResponse({"error": "You can only edit your own posts."}, status=403)
    
    data = json.loads(request.body)
    content = data.get("content", "").strip()
    
    if not content:
        return JsonResponse({"error": "Content cannot be empty."}, status=400)
    
    post.content = content
    post.save()
    
    return JsonResponse({"message": "Post updated successfully.", "content": post.content})


@login_required
def like_post(request, post_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST request required."}, status=400)
    
    post = get_object_or_404(Post, pk=post_id)
    
    # Toggle like
    like_obj, created = Like.objects.get_or_create(
        user=request.user,
        post=post
    )
    
    if not created:
        # If it already exists, unlike
        like_obj.delete()
        is_liked = False
    else:
        is_liked = True
    
    # Get updated like count
    like_count = post.likes.count()
    
    return JsonResponse({
        "is_liked": is_liked,
        "like_count": like_count
    })
