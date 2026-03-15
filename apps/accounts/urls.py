# apps/accounts/urls.py
from rest_framework.routers import DefaultRouter
from apps.accounts.views import (
    UserViewSet,
    EmployeeViewSet,
    AuthViewSet,
    DepartmentViewSet,
    ProfileViewSet,
)

router = DefaultRouter()

router.register(r'users',       UserViewSet,       basename='user')
router.register(r'employees',   EmployeeViewSet,   basename='employee')
router.register(r'auth',        AuthViewSet,       basename='auth')
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'profile',     ProfileViewSet,    basename='profile')

urlpatterns = router.urls