# apps/tasks/urls.py
from rest_framework.routers import DefaultRouter
from apps.tasks.views       import MainTaskViewSet

router = DefaultRouter()
router.register(r'main-tasks', MainTaskViewSet, basename='main-task')

urlpatterns = router.urls