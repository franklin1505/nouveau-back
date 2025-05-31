from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
from utilisateurs.Auth.views import LoginView, UserCreationView, PasswordResetRequestView, PasswordResetValidationView, PasswordChangeView

urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'), 
    path('register/', UserCreationView.as_view(), name='create-user'),
    path('login/', LoginView.as_view(), name='login'),
    path('password-reset-request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset-validate/', PasswordResetValidationView.as_view(), name='password_reset_validate'),
    path('password-change/', PasswordChangeView.as_view(), name='password_change'),

]
