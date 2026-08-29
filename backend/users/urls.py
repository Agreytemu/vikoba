from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)
from .views import (
    ChangePasswordView,
    CurrentUserView,
    EmailVerificationRequestView,
    EmailVerificationVerifyView,
    LoginView,
    LogoutView,
    NotificationViewSet,
    PasswordResetRequestView,
    PasswordResetView,
    PinLoginView,
    PinSetupConfirmView,
    PinSetupRequestView,
    RegisterView,
    UserViewList,
)

router = DefaultRouter()
router.register(r'users', UserViewList, basename='users')
router.register(r'notifications', NotificationViewSet, basename='notifications')

app_name = "users"

urlpatterns = [
    path('login', LoginView.as_view(), name='token_obtain_pair'),
    path('refresh-token', TokenRefreshView.as_view(), name='token_refresh'),
    path('register', RegisterView.as_view(), name='register'),
    path('email-verify-request', EmailVerificationRequestView.as_view(),
         name='email_verify_request'),
    path('email-verify', EmailVerificationVerifyView.as_view(),
         name='email_verify'),
    path('logout', LogoutView.as_view(), name='logout'),
    path('pin/setup-request', PinSetupRequestView.as_view(), name='pin_setup_request'),
    path('pin/setup-confirm', PinSetupConfirmView.as_view(), name='pin_setup_confirm'),
    path('pin/login', PinLoginView.as_view(), name='pin_login'),
    path('request-password-reset', PasswordResetRequestView.as_view(),
         name='request_password_reset'),
    path('password-reset',
         PasswordResetView.as_view(), name='password_reset'),
    path('change-password', ChangePasswordView.as_view(), name='change_password'),
    path('me', CurrentUserView.as_view(), name='current_user'),
    # path('api/profile/', UserProfileView.as_view(), name='profile'),
]

urlpatterns += router.urls
