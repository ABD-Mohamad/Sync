# apps/tasks/admin.py
from django.contrib    import admin
from apps.tasks.models import MainTask, TaskAttachment


class TaskAttachmentInline(admin.TabularInline):
    model   = TaskAttachment
    extra   = 0
    readonly_fields = ['filename', 'uploaded_by', 'uploaded_at']


@admin.register(MainTask)
class MainTaskAdmin(admin.ModelAdmin):
    list_display    = [
        'title', 'priority', 'status',
        'department', 'assigned_to', 'due_date',
    ]
    list_filter     = ['status', 'priority', 'department']
    search_fields   = ['title', 'description']
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    inlines         = [TaskAttachmentInline]


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    list_display  = ['filename', 'task', 'uploaded_by', 'uploaded_at']
    search_fields = ['filename', 'task__title']
    readonly_fields = ['filename', 'uploaded_by', 'uploaded_at']