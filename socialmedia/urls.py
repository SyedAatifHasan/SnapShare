"""
URL configuration for socialmedia project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from userauth.views import *
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('login/', login_user, name='login'),
    path('profile_details/', profile_details, name='profile_details'),
    path('skip_profile/', skip_profile, name='skip_profile'),
    path('forget_password/', forget_password, name='forget_password'),
    path('reset_password/<str:pk>/', reset_password, name='reset_password'),
    path('verify_otp/', verify_otp, name='verify_otp'),
    path('resend_otp/', resend_otp, name='resend_otp'),
    path('logout/', logout_page, name='logout'),
    path('register/', register_user, name='register'),
    path('create_post/', select_post_type, name='select_post_type'),
    path('create_post/text/', create_text_post, name='create_text_post'),
    path('create_post/image/', create_image_post, name='create_image_post'),
    path('create_post/video/', create_video_post, name='create_video_post'),
    path('repost/<uuid:post_id>/', repost, name='repost'), 
    path('like-post/', like_post, name='like-post'),
    path('add-comment/', add_comment, name='add-comment'),
    path('notifications/', notifications_view, name='notifications'),
    path('notifications/mark_read/<int:notif_id>/', mark_notification_read, name='mark_notification_read'), 
    path('get_unread_notifications/', get_unread_notifications, name='get_unread_notifications'),   
    path('explore/', explore, name='explore'),
    path('profile/<str:pk>/', profile_view, name='profile'),
    path('post_details/<str:pk>/', post_detail, name='post_details'),
    path('edit_profile/', edit_profile, name='edit_profile'),
    path('updatepassword/', update_password, name='update_password'),
    path('delete/<str:pk>/', delete_post, name='delete_post'),
    path('update/<str:pk>/', update_post, name='update_post'),
    path('follow/', follow_user, name='follow_user'),
    path('search/', search, name='search'),
    path('live-search/', live_search, name='live_search'),
    path('save-search/<int:user_id>/', save_search, name='save_search'),
    path('search/remove/<int:user_id>/', remove_from_search_history, name='remove_from_search_history'),
    path('search/clear/', clear_search_history, name='clear_search_history'),
    path('profile/<str:username>/report/', user_interaction_report, name='user_interaction_report'),

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
