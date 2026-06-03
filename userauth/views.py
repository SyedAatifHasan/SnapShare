import re
from django.http import JsonResponse
from django.shortcuts import get_object_or_404,render, redirect
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import *
from .models import Profile
import datetime
from .utils import *
from copy import deepcopy
from django.db.models import Prefetch
# Create your views here.
@login_required(login_url='/login/')
def home(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    following_user_ids = Followers.objects.filter(
        follower=request.user
    ).values_list('user_id', flat=True)

    following_users = User.objects.filter(id__in=following_user_ids)
    posts = Post.objects.filter(user__in=following_users, is_active=True).prefetch_related(
        Prefetch('images', queryset=PostImage.objects.filter(is_active=True))
    ).order_by('-created_at')
    for post in posts:
            if post.images.exists():
                active_images = post.images.filter(is_active=True)
            elif post.image:
                class DummyImage:
                    def __init__(self, image):
                        self.image = image
                active_images = [DummyImage(post.image)]
            else:
                active_images = []

            post.active_images = active_images
            post.first_active_image = active_images[0] if active_images else None
            post.has_images = bool(active_images)

            post.text_content = post.text_content or ""
            post.caption = post.caption or ""
            post.liked = post.liked_by_user(request.user)
            post.comment_count = post.comments_count()
            post.reposted = post.reposted_by_user(request.user)
    reposts = Repost.objects.filter(user__in=following_users,original_post__is_active=True).select_related('original_post')
    reposts_as_posts = []
    for r in reposts:
        original_post = r.original_post
        active_images = original_post.images.filter(is_active=True)
        original_post.active_images = active_images
        original_post.first_active_image = active_images.first() if active_images.exists() else None
        original_post.has_images = active_images.exists()

        p = deepcopy(original_post)
        p.is_repost = True
        p.reposted_by = r.user
        p.repost_of = original_post
        p.no_of_reposts = original_post.reposts.filter(original_post__is_active=True).count()
        reposts_as_posts.append(p)
    from itertools import chain
    feed_items = sorted(
        chain(posts, reposts_as_posts),
        key=lambda x: x.created_at,
        reverse=True
    )
    comments = Comments.objects.all()

    suggested_users = User.objects.filter(
        profile__location=profile.location
    ).exclude(
        id=request.user.id
    ).exclude(
        is_staff=True
    )[:5]

    for p in feed_items:
        p.liked = LikePost.objects.filter(
            post=p,
            user=request.user
        ).exists()

        p.comment_count = Comments.objects.filter(
            post=p
        ).count()
        
        p.reposted = Repost.objects.filter(original_post=p, user=request.user).exists()

        p.commented = Comments.objects.filter(
            post=p,
            user=request.user
        ).exists()


    for u in suggested_users:
        if Followers.objects.filter(
            follower=request.user,
            user=u
        ).exists():
            u.follow_status = "unfollow"
        else:
            u.follow_status = "follow"

    context = {
        "page": "Home",
        "profile": profile,
        "posts": posts,
        "feed_items": feed_items,
        "comments": comments,
        "suggested_users": suggested_users,
    }
    return render(request, 'home.html', context)
def login_user(request):
    context = {"page": "Login"}

    if request.method == "POST":
        username = request.POST.get('login_input')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user:
            if not user.is_active:
                messages.error(request, "Your account is inactive. Please verify your email.")
                return redirect('/login/')
            send_otp(user,request)
            request.session['otp_user_id'] = user.id
            request.session['otp_type'] = 'login'
            return redirect('verify_otp') 
        else:
            messages.error(request, "Invalid username or password.")
            return redirect('/login/')

    return render(request, 'login.html', context)

@login_required(login_url='/login/')
def logout_page(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('/login/')
def register_user(request):
    context = {"page": "Register"}
    if request.method == "POST":
        full_name = request.POST.get('full_name')
        username = request.POST.get('username').lower().strip()
        location = request.POST.get('location')
        email = request.POST.get('email')
        password = request.POST.get('password')

        if " " in username:
            messages.error(request, "Username must not contain spaces.")
            return redirect('/register/')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('/register/')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return redirect('/register/')
        try:
            validate_password(password)
            if password.lower() in [username.lower(), email.lower(), location.lower()]:
                messages.error(request, "Password cannot be same as username, email, or location.")
                return redirect('/register/')
        except ValidationError as e:
            messages.error(request, "; ".join(e.messages))
            return redirect('/register/')
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            is_active=True
        )
        user.first_name = full_name
        Profile.objects.get_or_create(
            user=user,
            location=location
        )
        user.save()

        Profile.objects.create(user=user)

        send_otp(user, request)
        request.session['otp_user_id'] = user.id

        return redirect('verify_otp')

    return render(request, 'register.html', context)

@login_required(login_url='/login/')
def profile_details(request):
    context = {"page": "Profile Details"}
    profile = Profile.objects.get(user=request.user)
    if profile.is_completed:
        return redirect('/')
    if request.method == "POST":
        profile.profileimg = request.FILES.get('image')
        
        facebook = request.POST.get('facebook')
        insta = request.POST.get('instagram')
        linkedin = request.POST.get('linkedin')
        x = request.POST.get('x')
        
        if facebook and not is_valid_social_link(facebook, 'facebook'):
            messages.error(request, "Invalid Facebook link!")
            return redirect('profile_details')
        if insta and not is_valid_social_link(insta, 'instagram'):
            messages.error(request, "Invalid Instagram link!")
            return redirect('profile_details')
        if linkedin and not is_valid_social_link(linkedin, 'linkedin'):
            messages.error(request, "Invalid LinkedIn link!")
            return redirect('profile_details')
        if x and not is_valid_social_link(x, 'x'):
            messages.error(request, "Invalid X/Twitter link!")
            return redirect('profile_details')
        profile.fb = facebook
        profile.insta = insta
        profile.linkedin = linkedin
        profile.x = x

        profile.is_completed = True
        profile.save()
        return redirect('home')

    return render(request, 'profile_details.html', context)
def is_valid_social_link(link, platform):
    if not link:
        return True
    link = link.lower().strip()
    if platform == 'linkedin':
        return 'linkedin.com' in link
    elif platform == 'facebook':
        return 'facebook.com' in link
    elif platform == 'instagram':
        return 'instagram.com' in link
    elif platform == 'x':
        return 'x.com' in link or 'twitter.com' in link
    return False

@login_required(login_url='/login/')
def skip_profile(request):
    profile = Profile.objects.get(user=request.user)
    profile.is_completed = True
    profile.save()
    return redirect('/')

def verify_otp(request):
    user_id = request.session.get('otp_user_id')
    otp_type = request.session.get('otp_type')

    if not user_id:
        messages.error(request, "Session expired. Please login.")
        return redirect('login')

    user = get_object_or_404(User, id=user_id)
    otp_sent_time = request.session.get('otp_sent_time')
    time_left = 0
    if otp_sent_time:
        import time
        elapsed = time.time() - otp_sent_time

        time_left = max(0, 300 - int(elapsed))
    if request.method == "POST":
        entered_otp = request.POST.get('otp')
        try:
            otp_obj = EmailOTP.objects.get(user=user)
        except EmailOTP.DoesNotExist:
            messages.error(request, "OTP not found. Please request a new OTP. Please click on Resend OTP.")
            return redirect('verify_otp')
        if otp_obj.otp == entered_otp:
            if otp_type == 'register':
                user.is_active = True
                user.save()

            login(request, user)
            
            profile, created = Profile.objects.get_or_create(user=user)
            request.session.pop('otp_user_id', None)
            request.session.pop('otp_type', None)
            request.session.pop('otp_sent_time', None)
            
            messages.success(request, "Your account has been verified.")
            if not profile.is_completed:
                return redirect('profile_details')
            return redirect('/')
        else:
            messages.error(request, "Invalid OTP. Please try again.")

    return render(request, 'verify_otp.html', {"page": "Verify OTP", "time_left": time_left})
def resend_otp(request):
    user_id = request.session.get('otp_user_id')
    
    if not user_id:
        messages.error(request, "OTP expired. Please log in again.")
        return redirect('/login/')
    
    otp_sent_time = request.session.get('otp_sent_time')
    if otp_sent_time:
        elapsed = datetime.datetime.now().timestamp() - otp_sent_time
        if elapsed < 300:
            messages.error(request, f"Please wait {int(300 - elapsed)} seconds before resending OTP.")
            return redirect('verify_otp')
    user = get_object_or_404(User, id=user_id)
    send_otp(user,request)
    messages.success(request, "A new OTP has been sent to your email.")
    return redirect('verify_otp')
@login_required(login_url='/login/')
def create_text_post(request):
    if request.method == 'POST':
        text_content = request.POST.get('text_content')
        # caption = request.POST.get('text_content')
        allow_repost = request.POST.get('allow_repost') == 'on'

        Post.objects.create(
            user=request.user,
            post_type='text',
            text_content=text_content,
            # caption=caption,
            allow_repost=allow_repost
        )
      
        return redirect('/profile/' + request.user.username)

    return render(request, 'create_text_post.html',{'page':'Create Text Post'})

@login_required(login_url='/login/')
def select_post_type(request):
    return render(request, 'select_post_type.html', {"page": "Select Post Type"})
@login_required(login_url='/login/')
def create_image_post(request):
    if request.method == 'POST':
        images = request.FILES.getlist('images')
        caption = request.POST.get('caption')
        allow_repost = request.POST.get('allow_repost') == 'on'

        post = Post.objects.create(
            user=request.user,
            post_type="image",
            caption=caption,
            allow_repost=allow_repost
        )

        for img in images:
            PostImage.objects.create(post=post, image=img)

        return redirect('/profile/' + request.user.username)

    return render(request, 'create_image_post.html',{'page':'Create Image Post'})
@login_required(login_url='/login/')
def create_video_post(request):
    if request.method == 'POST':
        video = request.FILES.get('video')
        caption = request.POST.get('caption')
        allow_repost = request.POST.get('allow_repost') == 'on'

        Post.objects.create(
            user=request.user,
            post_type='video',
            video=video,
            caption=caption,
            allow_repost=allow_repost
        )
        return redirect('/profile/' + request.user.username)

    return render(request, 'create_video_post.html',{'page':'Create Video Post'})
@login_required(login_url='/login/')
def repost(request, post_id):
    username = request.user.username
    post = get_object_or_404(Post, id=post_id, is_active=True)

    existing_repost = Repost.objects.filter(user=request.user, original_post=post).first()

    if existing_repost:
        existing_repost.delete()
        if post.no_of_reposts > 0:
            post.no_of_reposts -= 1
            post.save()
    else:
        Repost.objects.create(user=request.user, original_post=post)
        post.no_of_reposts += 1
        post.save()
        if post.user.email and post.user != request.user:
            send_mail(
                subject="Someone Reposted your post 🔁",
                message=(
                    f"{username} Reposted your post.\n\n"
                    f"View post: http://127.0.0.1:8000/post_details/{post.id}/"
                    f"\n\nThank you for being part of our community!"
                ),
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[post.user.email],
                fail_silently=True,
        )
        if post.user.email and post.user != request.user:
            notify(post.user, f"{request.user.username} Reposted your post!", sender=request.user, link=f"/post_details/{post.id}/")

    return redirect(request.META.get('HTTP_REFERER', '/'))

@login_required(login_url='/login/')
def like_post(request):
    post_id = request.GET.get('post_id')
    post = get_object_or_404(Post, id=post_id)

    like = LikePost.objects.filter(
        post_id=post_id,
        user=request.user
    ).first()

    if like is None:
        LikePost.objects.create(post=post, user=request.user)
        post.no_of_likes += 1
        
        if post.user.email and post.user != request.user:
            send_mail(
                subject="Someone liked your post ❤️",
                message=(
                    f"{request.user.username} liked your post.\n\n"
                    f"View post: http://127.0.0.1:8000/post_details/{post.id}/"
                    f"\n\nThank you for being part of our community!"
                ),
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[post.user.email],
                fail_silently=True,
            )
            if post.user.email and post.user != request.user:
                notify(post.user, f"{request.user.username} liked your post!", sender=request.user, link=f"/post_details/{post.id}/")
    else:
        like.delete()
        post.no_of_likes -= 1

    post.save()
    return redirect(f'/post_details/{post.id}/')

@login_required(login_url='/login/')
def explore(request):
    user_location = request.user.profile.location
    posts = Post.objects.filter(is_active=True).order_by('-created_at').exclude(user=request.user)
    if user_location:
        posts = posts.filter(user__profile__location=user_location)
    posts = posts.prefetch_related(
        Prefetch(
            'images',
            queryset=PostImage.objects.filter(is_active=True)
        )
    )
    for post in posts:
        if post.images.exists():
            active_images = post.images.filter(is_active=True)

        elif post.image:
            class DummyImage:
                def __init__(self, image):
                    self.image = image
            active_images = [DummyImage(post.image)]
        else:
            active_images = []

        post.active_images = active_images
        post.has_images = len(active_images) > 0
        post.first_active_image = active_images[0] if post.has_images else None

    context = {
        'page': 'Explore',
        'posts': posts,
        'user_location': user_location,
        }
    return render(request, 'explore.html', context)

from django.db.models import Q, Prefetch
@login_required(login_url='/login/')
def profile_view(request, pk):
    user_object = get_object_or_404(User, username=pk)
    current_profile, _ = Profile.objects.get_or_create(user=request.user)
    viewed_profile, _ = Profile.objects.get_or_create(user=user_object)

    tab = request.GET.get('tab', 'posts')

    posts =  Post.objects.filter(
        user=user_object,
        is_active = True
    ).order_by('-created_at')
    
    if tab == 'images':
        posts = posts.filter(
            Q(image__isnull=False) | Q(images__isnull=False)
        ).distinct()

        posts = posts.prefetch_related(
            Prefetch('images', queryset=PostImage.objects.filter(is_active=True))
        )

        for post in posts:
            if post.images.exists():
                post.first_active_image = post.images.first()
                post.has_images = True
            elif post.image:
                post.first_active_image = type('Obj', (), {'image': post.image})
                post.has_images = True
            else:
                post.first_active_image = None
                post.has_images = False

    elif tab == 'videos':
        posts = posts = posts.filter(video__isnull=False).order_by('-created_at')
    elif tab == 'text':
        posts = Post.objects.filter(
            user=user_object,
            post_type='text',
            is_active=True,
        ).order_by('-created_at')
    elif tab == 'reposts':
        posts = Post.objects.none()
    else:
        posts = Post.objects.filter(user= user_object, is_active=True).order_by('-created_at')
    for post in posts:
        active_images = post.images.filter(is_active=True)

        post.first_active_image = (
            active_images.first()
            if active_images.exists()
            else None
        )
        post.has_images = bool(post.first_active_image)
    post_count = posts.count()
    reposts = Repost.objects.filter(user=user_object, original_post__is_active=True).select_related('original_post').order_by('-created_at')
    for r in reposts:
        original_post = r.original_post
        active_images = original_post.images.filter(is_active=True)
        original_post.active_images = active_images
        original_post.first_active_image = active_images.first() if active_images.exists() else None
        original_post.has_images = bool(original_post.first_active_image)

    follow_unfollow = 'unfollow' if Followers.objects.filter(follower=request.user, user=user_object).exists() else 'follow'

    user_followers = Followers.objects.filter(user=user_object).count()
    user_following = Followers.objects.filter(follower=user_object).count()
    followers_qs = Followers.objects.filter(user=user_object)
    followers = [f.follower for f in followers_qs]
    following = Followers.objects.filter(follower=user_object)
    is_following = Followers.objects.filter(
        follower=request.user,
        user=user_object).exists()

    is_followed_by = Followers.objects.filter(
        follower=user_object,
        user=request.user
    ).exists()

    if is_following and is_followed_by:
        relation = 'mutual'
    elif is_following:
        relation = 'you_follow'
    elif is_followed_by:
        relation = 'follows_you'
    else:
        relation = 'none'
        

    viewed_user_posts = Post.objects.filter(user=user_object, is_active=True)
    for f in followers:
        f.liked_posts_by_request_user = list(LikePost.objects.filter(user=f, post__in=viewed_user_posts).select_related('post'))
        for like in f.liked_posts_by_request_user:
            post = like.post
            if post.images.filter(is_active=True).exists():
                post.first_active_image = post.images.filter(is_active=True).first()
            elif post.image:
                post.first_active_image = type('Obj', (), {'image': post.image})
            elif post.video:
                post.first_active_image = type('Obj', (), {'video': post.video})
            else:
                post.first_active_image = None
            post.has_content = bool(post.first_active_image)

        f.commented_posts_by_request_user = list(Comments.objects.filter(user=f, post__in=viewed_user_posts).select_related('post'))
        for comment in f.commented_posts_by_request_user:
            post = comment.post
            if post.images.filter(is_active=True).exists():
                post.first_active_image = post.images.filter(is_active=True).first()
            elif post.image:
                post.first_active_image = type('Obj', (), {'image': post.image})
            elif post.video:
                post.first_active_image = type('Obj', (), {'video': post.video})
            else:
                post.first_active_image = None
            post.has_content = bool(post.first_active_image)
        f.reposted_posts_by_request_user = list(
        Repost.objects.filter(user=f, original_post__in=viewed_user_posts).select_related('original_post')
        )
        for repost in f.reposted_posts_by_request_user:
            post = repost.original_post
            if post.images.filter(is_active=True).exists():
                post.first_active_image = post.images.filter(is_active=True).first()
            elif post.image:
                post.first_active_image = type('Obj', (), {'image': post.image})
            elif post.video:
                post.first_active_image = type('Obj', (), {'video': post.video})
            else:
                post.first_active_image = None
            post.has_content = bool(post.first_active_image)
    

    context = {
        'page': 'Profile',
        'user_object': user_object,
        'current_profile': current_profile,
        'viewed_profile': viewed_profile,
        'posts': posts,
        'reposts': reposts,
        'tab': tab,
        'post_count': post_count,
        'follow_unfollow': follow_unfollow,
        'user_followers': user_followers,
        'user_following': user_following,
        'followers': followers,
        'following_users': following,
        'relation': relation,
        'show_report': relation in ['mutual', 'you_follow'],
    }

    return render(request, 'profile.html', context)
@login_required(login_url='/login/')
def edit_profile(request):
    user_profile = Profile.objects.get(user=request.user)

    if request.method == 'POST':
        bio = request.POST.get('bio')
        fb = request.POST.get('fb')
        insta = request.POST.get('insta')
        twitter = request.POST.get('twitter')
        linkedin = request.POST.get('linkedin')
        location = request.POST.get('location')

        if fb and not is_valid_social_link(fb, 'facebook'):
            messages.error(request, "Invalid Facebook link!")
            return redirect('/edit_profile/')
        if insta and not is_valid_social_link(insta, 'instagram'):
            messages.error(request, "Invalid Instagram link!")
            return redirect('/edit_profile/')
        if linkedin and not is_valid_social_link(linkedin, 'linkedin'):
            messages.error(request, "Invalid LinkedIn link!")
            return redirect('/edit_profile/')
        if twitter and not is_valid_social_link(twitter, 'x'):
            messages.error(request, "Invalid X/Twitter link!")
            return redirect('/edit_profile/')

        user_profile.bio = bio
        user_profile.fb = fb
        user_profile.insta = insta
        user_profile.twitter = twitter
        user_profile.linkedin = linkedin
        user_profile.location = location

        if request.FILES.get('image'):
            user_profile.profileimg = request.FILES.get('image')

        user_profile.save()
        return redirect(f'/profile/{request.user.username}')

    context = {
        'page': 'Edit Profile',
        'user_profile': user_profile
    }
    return render(request, 'edit_profile.html', context)

@login_required(login_url='/login/')
def delete_post(request, pk):
    post = get_object_or_404(Post, id=pk)
    if request.user == post.user:
        post.is_active = False  
        post.save()
        messages.success(request, "Post deleted successfully.")
    else:
        messages.error(request, "You are not authorized to remove this post.")
    return redirect(f'/profile/{request.user.username}')

@login_required(login_url='/login/')
def update_post(request, pk):
    post = get_object_or_404(Post, id=pk, is_active=True)

    if request.user != post.user:
        messages.error(request, "You are not authorized to edit this post.")
        return redirect(f'/profile/{request.user.username}')

    if request.method == 'POST':
        post.caption = request.POST.get('caption', post.caption)

        if post.post_type.lower() == 'text':
            post.text_content = request.POST.get('text_content', post.text_content)

        if post.post_type.lower() == 'image':
            if 'hide_current_image' in request.POST:
                post.image = None

            if request.FILES.get('new_image'):
                post.image = request.FILES.get('new_image')

            hide_ids = request.POST.getlist('hide_images')
            if hide_ids:
                PostImage.objects.filter(id__in=hide_ids, post=post).update(is_active=False)

            new_images = request.FILES.getlist('new_images')
            for img in new_images:
                PostImage.objects.create(
                    post=post,
                    image=img,
                    is_active=True   # 🚨 THIS IS REQUIRED
                )

        # Video posts
        if post.post_type.lower() == 'video':
            # Hide video if requested
            if 'hide_video' in request.POST:
                post.video = None

            # Replace video if new one is uploaded
            if request.FILES.get('new_video'):
                post.video = request.FILES.get('new_video')

        post.save()
        messages.success(request, "Post updated successfully.")
        return redirect(f'/post_details/{post.id}/')

    # Render the update form
    context = {
        'page': 'Update Post',
        'post': post
    }
    return render(request, 'update_post.html', context)

@login_required(login_url='/login/')
def post_detail(request, pk):
    post = Post.objects.filter(id=pk, is_active=True).prefetch_related(
        Prefetch('images', queryset=PostImage.objects.filter(is_active=True))
    ).first()
    if not post:
        messages.error(request, "Post not found.")
        return redirect('/')
    post.liked = post.liked_by_user(request.user)
    post.comment_count = post.comments_count()
    post.reposted_by_user = Repost.objects.filter(user=request.user, original_post=post).exists()
    active_images = post.images.filter(is_active=True)
    if post.images.exists():
        active_images = post.images.filter(is_active=True)
    elif post.image:
        class DummyImag:
            def __init__(self, image):
                self.image = image
        active_images = [DummyImag(post.image)]
    else:
        active_images = []
    if request.method == 'POST':
        comment_text = request.POST.get('comment')
        if comment_text:
            Comments.objects.create(
                post=post,
                user=request.user,
                comment_text=comment_text
            )
            if post.user.email and post.user != request.user:
                send_mail(
                    subject="New comment on your post 💬",
                    message=(
                        f"{request.user} commented on your post.\n\n"
                        f"View post: http://127.0.0.1:8000/post_details/{post.id}/\n"
                        f"Comment: \"{comment_text}\"\n"
                        "\n\nThank you for being part of our community!"
                    ),
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[post.user.email],
                    fail_silently=True,
                )

        return redirect(f'/post_details/{post.id}/')
    comments = Comments.objects.filter(post=post).select_related('user__profile').order_by('created_at')

    context = {
        'page': 'Post Detail',
        'post': post,
        'comments': comments,
        'active_images': active_images,
    }
    return render(request, 'post_detail.html', context)
@login_required(login_url='/login/')
def follow_user(request):
    if request.method == 'POST':
        follower = request.user
        user = request.POST.get('user')
        followed_user = get_object_or_404(User, username=user)
        if Followers.objects.filter(follower=follower, user=followed_user).first():
            delete_follower = Followers.objects.get(follower=follower, user=followed_user)
            delete_follower.delete()
            messages.success(request, f"You have unfollowed {user}.")
            return redirect(f'/profile/{user}')
        else:
            new_follower = Followers.objects.create(follower=follower, user=followed_user)
            new_follower.save()
            if followed_user.email:
                send_mail(
                    subject="You have a new follower 🎉",
                    message=(
                        f"{follower.username} started following you.\n\n"
                        f"View profile: http://127.0.0.1:8000/profile/{follower.username}/"
                        f"\n\nThank you for being part of our community!"
                    ),
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[followed_user.email],
                    fail_silently=True,
                )
            messages.success(request, f"You are now following {user}.")
            notify(
            user=followed_user,  # recipient (User object)
            message=f"{follower.username} started following you!",  # message
            sender=follower,  # sender (User object)
            link=f"/profile/{follower.username}/"
        )

            return redirect(f'/profile/{user}')
    else:
        return redirect('/')

@login_required(login_url='/login/')
def search(request):
    profile = Profile.objects.get(user=request.user)

    history = SearchHistory.objects.filter(
        user=request.user,
        hidden=False
    ).select_related('searched_user').order_by('-searched_at')

    context = {
        'page': 'Search',
        'profile': profile,
        'users': [h.searched_user for h in history],
    }
    return render(request, 'search.html', context)
@login_required(login_url='/login/')
def live_search(request):
    query = request.GET.get('q', '').strip()
    
    users_qs = User.objects.filter(
        username__icontains=query,
        is_active=True,
        is_superuser=False,
        is_staff=False
    ).exclude(id=request.user.id)[:10]

    history_qs = SearchHistory.objects.filter(
        user=request.user,
        hidden=False,
        searched_user__username__icontains=query
    ).select_related('searched_user')[:10]

    data = []
    for h in history_qs:
        data.append({
            'id': h.searched_user.id,
            'username': h.searched_user.username,
            'profileimg': h.searched_user.profile.profileimg.url if hasattr(h.searched_user, 'profile') else '/static/default.png',
            'from_history': True
        })
    for u in users_qs:
        if u.id not in [d['id'] for d in data]:
            data.append({
                'id': u.id,
                'username': u.username,
                'profileimg': u.profile.profileimg.url if hasattr(u, 'profile') else '/static/default.png',
                'from_history': False
            })

    return JsonResponse(data, safe=False)
@login_required(login_url='/login/')
def save_search(request, user_id):
    searched_user = get_object_or_404(
        User,
        id=user_id,
        is_superuser=False,
        is_active=True
    )

    SearchHistory.objects.update_or_create(
        user=request.user,
        searched_user=searched_user,
        defaults={'hidden': False}
    )

    return redirect(f'/profile/{searched_user.username}')
@login_required(login_url='/login/')
def get_history(request):

    history = SearchHistory.objects.filter(user=request.user, hidden=False).select_related('searched_user').order_by('-searched_at')
    
    data = []
    for h in history:
        data.append({
            'id': h.searched_user.id,
            'username': h.searched_user.username,
            'profileimg': h.searched_user.profile.profileimg.url if hasattr(h.searched_user, 'profile') else '/static/default.png'
        })
    
    return JsonResponse(data, safe=False)
@login_required(login_url='/login/')
def remove_from_search_history(request, user_id):
    SearchHistory.objects.filter(
        user=request.user,
        searched_user_id=user_id
    ).update(hidden=True)

    return redirect('/search/')

@login_required(login_url='/login/')
def clear_search_history(request):
    SearchHistory.objects.filter(user=request.user).update(hidden=True)
    return redirect('/search/')
@login_required(login_url='/login/')
def notifications_view(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    notifications.filter(read=False).update(read=True)

    context = {
        'page': 'Notifications',
        'notifications': notifications,
    }
    return render(request, 'notifications.html', context)
@login_required(login_url='/login/')
def get_unread_notifications(request):
    unread = Notification.objects.filter(user=request.user, read=False).order_by('-created_at')
    notifications_list = []

    for n in unread:
        notifications_list.append({
            'id': n.id,
            'message': n.message,
            'link': n.link if n.link else '#',
            'sender_username': n.sender.username if n.sender else '',
            'sender_img': n.sender.profile.profileimg.url if n.sender else '',
        })

    return JsonResponse({'count': unread.count(), 'notifications': notifications_list})

@login_required(login_url='/login/')
@csrf_exempt
def mark_notification_read(request, notif_id):
    notif = get_object_or_404(Notification, id=notif_id, user=request.user)
    notif.read = True
    notif.save()
    return JsonResponse({'status': 'success'})
@login_required(login_url='/login/')
def add_comment(request):
    if request.method != 'POST':
        return redirect('/')

    post_id = request.POST.get('post_id')
    comment_text = request.POST.get('comment')
    user = request.user 

    post = Post.objects.get(id=post_id)

    Comments.objects.create(
        post_id=post_id,
        user=user,
        comment_text=comment_text
    )
    commenter = request.user

    if post.user.email and post.user != commenter:
        send_mail(
            subject="New comment on your post 💬",
            message=(
                f"{commenter} commented on your post.\n\n"
                f"View post:\n"
                f"http://127.0.0.1:8000/post_details/{post.id}/\n\n"
                f"Comment: \"{comment_text}\""
            ),
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[post.user.email],
            fail_silently=True,
        )
        if post.user != user:
            notify(
                user=post.user,
                message=f"{commenter.username} commented on your post: \"{comment_text}\"",
                sender=user,
                link=f"/post_details/{post.id}/"
            )
    return redirect('/')

@login_required(login_url='/login/')
def update_password(request):
    user = request.user
    profile = Profile.objects.get(user=user)

    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not user.check_password(current_password):
            messages.error(request, "Current password is incorrect.")
            return redirect('update_password')

        if new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
            return redirect('update_password')

        try:
            validate_password(new_password, user=user)

            if new_password.lower() in [
                user.username.lower(),
                user.email.lower(),
                profile.location.lower()
            ]:
                messages.error(
                    request,
                    "Password cannot be same as username, email, or location."
                )
                return redirect('update_password')

        except ValidationError as e:
            messages.error(request, "; ".join(e.messages))
            return redirect('update_password')

        user.set_password(new_password)
        user.save()

        messages.success(
            request,
            "Password updated successfully. Please log in again."
        )
        return redirect('/login/')

    context = {'page': 'Update Password'}
    return render(request, 'update_password.html', context)

def forget_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')

        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            send_mail(
                subject="Link to reset your password 🔐",
                message=(
                    f"Hey user: {user.username} !! \n\n"
                    f"Click the link below to reset your password:\n"
                    f"http://127.0.0.1:8000/reset_password/{user.id}/"
                    f"\n\nThank you for being part of our community!"
                ),
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[user.email],
                fail_silently=True,
            )
            messages.success(request, "Reset password email sent.")
        else:
            messages.error(request, "Email not found. Please try again.")

        return render(request, 'forget_password.html')

    return render(request, 'forget_password.html')

def reset_password(request, pk):
    user = get_object_or_404(User, username=pk)
    profile = Profile.objects.get(user=user)
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
            return redirect(f'/reset_password/{user.username}/')

        try:
            validate_password(new_password, user=user)
            profile = Profile.objects.get(user=user)
            if new_password.lower() in [user.username.lower(), user.email.lower(), profile.location.lower()]:
                messages.error(request, "Password cannot be same as username, email, or location.")
                return redirect(f'/reset_password/{user.username}/')
        except ValidationError as e:
            messages.error(request, "; ".join(e.messages))
            return redirect(f'/reset_password/{user.username}/')

        user.set_password(new_password)
        user.save()
        messages.success(request, "Password reset successfully. Please log in.")
        return redirect('/login/')

    return render(request, 'reset_password.html',{'page':'Reset Password'})

def get_follow_status(viewer, profile_user):
    viewer_follows = Followers.objects.filter(
        follower=viewer,
        user=profile_user
    ).exists()

    profile_follows_viewer = Followers.objects.filter(
        follower=profile_user,
        user=viewer
    ).exists()

    if viewer_follows and profile_follows_viewer:
        return "mutual"
    elif viewer_follows:
        return "you_follow"
    elif profile_follows_viewer:
        return "follows_you"
    else:
        return "no_relation"
@login_required(login_url='/login/')
def user_interaction_report(request, username):
    # Get user object
    user_object = get_object_or_404(User, username=username)
    
    # Get posts of the user you are viewing
    user_posts = Post.objects.filter(user=user_object, is_active=True)

    # Interaction data
    liked_posts = LikePost.objects.filter(user=request.user, post__in=user_posts).select_related('post')
    commented_posts = Comments.objects.filter(user=request.user, post__in=user_posts).select_related('post')
    reposted_posts = Repost.objects.filter(user=request.user, original_post__in=user_posts).select_related('original_post')

    # Attach first image/video for display
    def attach_first_content(posts_list, is_repost=False):
        for obj in posts_list:
            post = obj.original_post if is_repost else obj.post
            if post.images.filter(is_active=True).exists():
                post.first_active_image = post.images.filter(is_active=True).first()
            elif post.image:
                post.first_active_image = type('Obj', (), {'image': post.image})
            elif post.video:
                post.first_active_image = type('Obj', (), {'video': post.video})
            else:
                post.first_active_image = None
            post.has_content = bool(post.first_active_image)

    attach_first_content(liked_posts)
    attach_first_content(commented_posts)
    attach_first_content(reposted_posts, is_repost=True)

    context = {
        'page': f'{user_object.username} Interaction Report',
        'viewed_user': user_object,
        'liked_posts': liked_posts,
        'commented_posts': commented_posts,
        'reposted_posts': reposted_posts,
    }
    return render(request, 'user_interaction_report.html', context)
