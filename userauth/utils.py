# utils.py
import random
from django.core.mail import send_mail
import datetime
from django.conf import settings
from .models import EmailOTP
from .models import Notification

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp(user, request):
    otp = generate_otp()
    obj, _ = EmailOTP.objects.get_or_create(user=user)
    obj.otp = otp
    obj.save()

    send_mail(
        subject="Email Verification OTP",
        message=f"Your OTP is {otp}",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[user.email],
        fail_silently=False,
    )

    request.session['otp_sent_time'] = datetime.datetime.now().timestamp()
   
def notify(user, message, sender=None, link=None):
    Notification.objects.create(user=user, sender=sender, message=message, link=link)
