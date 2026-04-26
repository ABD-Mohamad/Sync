# apps/tasks/urls.py
from django.urls import path
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

urlpatterns = [
    path('subtasks/my-subtasks/', SubTaskViewSet.as_view({'get': 'my_subtasks'}), name='my-subtasks'),
    path('subtasks/employee-dashboard/', SubTaskViewSet.as_view({'get': 'employee_dashboard'}), name='employee-dashboard'),
] + router.urls + tasks_router.urls