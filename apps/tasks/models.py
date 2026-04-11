# apps/tasks/models.py
from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL


class MainTask(models.Model):

    class Priority(models.TextChoices):
        LOW    = 'low',    'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH   = 'high',   'High'
        URGENT = 'urgent', 'Urgent'

    class Status(models.TextChoices):
        UNASSIGNED  = 'unassigned',  'Unassigned'
        ASSIGNED    = 'assigned',    'Assigned'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED   = 'completed',   'Completed'

    title       = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    priority    = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.UNASSIGNED,
    )

    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='created_main_tasks',
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_main_tasks',
    )
    department = models.ForeignKey(
        'accounts.Department',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='main_tasks',
    )

    start_date = models.DateField(null=True, blank=True)
    due_date   = models.DateField(null=True, blank=True)
    # ← attachments field removed — replaced by TaskAttachment model

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name        = 'Main Task'
        verbose_name_plural = 'Main Tasks'
        ordering            = ['-created_at']


class TaskAttachment(models.Model):
    """
    Stores multiple file attachments for a MainTask.
    Each file is associated with the user who uploaded it.
    """
    task        = models.ForeignKey(
        MainTask,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='task_attachments',
    )
    file        = models.FileField(upload_to='task_attachments/%Y/%m/')
    filename    = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Store original filename for display purposes
        if self.file and not self.filename:
            self.filename = self.file.name.split('/')[-1]
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.filename} → {self.task.title}'

    class Meta:
        verbose_name        = 'Task Attachment'
        verbose_name_plural = 'Task Attachments'
        ordering            = ['-uploaded_at']


class SubTask(models.Model):

    class Status(models.TextChoices):
        NOT_STARTED     = 'not_started',     'Not Started'
        IN_PROGRESS     = 'in_progress',     'In Progress'
        AWAITING_REVIEW = 'awaiting_review',  'Awaiting Review'
        COMPLETED       = 'completed',       'Completed'

    title       = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    notes       = models.TextField(blank=True)
    status      = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_STARTED,
    )

    main_task  = models.ForeignKey(
        MainTask, on_delete=models.CASCADE,
        related_name='subtasks',
    )
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='created_subtasks',
    )
    assigned_to = models.ForeignKey(
        'accounts.Employee',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_subtasks',
    )

    estimated_hours = models.PositiveIntegerField(null=True, blank=True)
    actual_hours    = models.PositiveIntegerField(null=True, blank=True)
    due_date        = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.title} → {self.main_task.title}'

    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.due_date and self.status != self.Status.COMPLETED:
            return self.due_date < timezone.now().date()
        return False

    class Meta:
        verbose_name        = 'Sub Task'
        verbose_name_plural = 'Sub Tasks'
        ordering            = ['due_date', '-created_at']


class Request(models.Model):

    class RequestType(models.TextChoices):
        EXTENSION = 'extension', 'Extension Request'
        EXEMPTION = 'exemption', 'Exemption Request'

    class Status(models.TextChoices):
        PENDING  = 'pending',  'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    request_type = models.CharField(max_length=10, choices=RequestType.choices)
    status       = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )

    subtask     = models.ForeignKey(
        SubTask, on_delete=models.CASCADE,
        related_name='requests',
    )
    employee = models.ForeignKey(
        'accounts.Employee', on_delete=models.CASCADE,
        related_name='requests',
    )
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_requests',
    )

    extension_days   = models.PositiveIntegerField(null=True, blank=True)
    reason           = models.TextField()
    rejection_reason = models.TextField(blank=True)
    submitted_at     = models.DateTimeField(auto_now_add=True)
    reviewed_at      = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.get_request_type_display()} by {self.employee} - {self.status}'

    class Meta:
        verbose_name        = 'Request'
        verbose_name_plural = 'Requests'
        ordering            = ['-submitted_at']