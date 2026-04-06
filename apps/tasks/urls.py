# apps/tasks/urls.py
from rest_framework.routers     import DefaultRouter
from rest_framework_nested      import routers as nested_routers
from apps.tasks.views           import MainTaskViewSet, SubTaskViewSet, RequestViewSet

# Main router
router = DefaultRouter()
router.register(r'main-tasks', MainTaskViewSet, basename='main-task')
router.register(r'requests',   RequestViewSet,  basename='request')

# Nested router — /main-tasks/{main_task_pk}/subtasks/
tasks_router = nested_routers.NestedDefaultRouter(
    router, r'main-tasks', lookup='main_task'
)
tasks_router.register(r'subtasks', SubTaskViewSet, basename='main-task-subtasks')

urlpatterns = router.urls + tasks_router.urls