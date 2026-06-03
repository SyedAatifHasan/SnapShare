from django.db import models
from django.contrib.auth.models import User
import uuid
# Create your models here.

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True,default='')
    fb = models.CharField(max_length=100, blank=True,default='')
    insta = models.CharField(max_length=100, blank=True,default='')
    twitter = models.CharField(max_length=100, blank=True,default='')
    linkedin = models.CharField(max_length=100, blank=True,default='')
    profileimg = models.ImageField(upload_to='profile_images',default='blank-profile-picture.png')
    location = models.CharField(max_length=100, blank=True,default='')
    is_completed = models.BooleanField(default=False)
    def __str__(self):
        return self.user.username
class EmailOTP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.otp}"
    
class Post(models.Model):
    POST_TYPES = (
        ('text', 'Text'),
        ('image', 'Image'),
        ('video', 'Video'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    caption = models.TextField(blank=True)
    text_content = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='post_images/', blank=True, null=True)
    video = models.FileField(upload_to='post_videos/', blank=True, null=True)

    post_type = models.CharField(max_length=10, choices=POST_TYPES, default='text')

    allow_repost = models.BooleanField(default=True)

    no_of_likes = models.IntegerField(default=0)
    no_of_comments = models.IntegerField(default=0)
    no_of_reposts = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.post_type}"
    
    
    def liked_by_user(self, user):
        return LikePost.objects.filter(post=self, user=user).exists()


    def comments_count(self):
        return self.comments.count()

    
    def reposted_by_user(self, user):
        return self.reposts.filter(user=user).exists()

class PostImage(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='post_images/')
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"Image for post {self.post.id}"
    
class Repost(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    original_post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reposts')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.original_post.is_active:
            raise ValueError("Cannot repost an inactive post.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} reposted {self.original_post.id}"
class LikePost(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)


    class Meta:
        unique_together = ('post', 'user')

    def __str__(self):
        return f"{self.user.username} liked {self.post.id}"


class Followers(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')

    class Meta:
        unique_together = ('user', 'follower')

    def __str__(self):
        return f"{self.follower.username} follows {self.user.username}"
    
class Comments(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} on {self.post.id}"

class SearchHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    searched_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='searched_by')
    searched_at = models.DateTimeField(auto_now_add=True)
    hidden = models.BooleanField(default=False)  

    class Meta:
        unique_together = ('user', 'searched_user') 

    def __str__(self):
        return f"{self.user.username} searched {self.searched_user.username}"
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications')
    message = models.TextField()
    link = models.URLField(blank=True, null=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.message[:20]}"
