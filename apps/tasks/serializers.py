# apps/tasks/serializers.py
from rest_framework import serializers
from apps.tasks.models    import MainTask, TaskAttachment
from apps.accounts.models import User, Role


class TaskAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = TaskAttachment
        fields = ['id', 'file', 'filename', 'uploaded_by', 'uploaded_at']
        read_only_fields = ['id', 'filename', 'uploaded_by', 'uploaded_at']


class AssignedToField(serializers.SlugRelatedField):
    """
    READ  : returns { id, full_name, department }
    WRITE : accepts a user ID, validates Department Head role
    """
    def to_representation(self, obj):
        return {
            'id'        : obj.id,
            'full_name' : obj.full_name,
            'department': obj.department.name if obj.department else None,
        }

    def to_internal_value(self, data):
        try:
            user = User.objects.select_related('role', 'department').get(pk=data)
        except (User.DoesNotExist, TypeError, ValueError):
            raise serializers.ValidationError('Invalid user ID.')

        if not user.role or user.role.name != Role.DEPARTMENT_HEAD:
            raise serializers.ValidationError(
                'Tasks can only be assigned to Department Heads.'
            )
        if not user.department:
            raise serializers.ValidationError(
                'This Department Head has no department assigned.'
            )
        return user


class MainTaskSerializer(serializers.ModelSerializer):
    created_by  = serializers.StringRelatedField(read_only=True)
    assigned_to = AssignedToField(
        slug_field='full_name',
        queryset=User.objects.select_related('role', 'department').filter(
            role__name=Role.DEPARTMENT_HEAD
        ),
        required=False,
        allow_null=True,
    )

    # Nested read — prefetch_related in ViewSet prevents N+1
    attachments = TaskAttachmentSerializer(many=True, read_only=True)

    # Write-only field for uploading multiple files in one request
    upload_files = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False,
    )

    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model  = MainTask
        fields = [
            'id', 'title', 'description', 'priority', 'status',
            'created_by', 'assigned_to', 'department',
            'start_date', 'due_date',
            'attachments', 'upload_files',
            'is_overdue', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'created_by', 'status',
            'created_at', 'updated_at',
        ]

    def get_is_overdue(self, obj):
        from django.utils import timezone
        if obj.due_date and obj.status != MainTask.Status.COMPLETED:
            return obj.due_date < timezone.now().date()
        return False

    def validate(self, data):
        start = data.get('start_date')
        due   = data.get('due_date')
        if start and due and due < start:
            raise serializers.ValidationError(
                'Due date cannot be before start date.'
            )
        return data

    def create(self, validated_data):
        files   = validated_data.pop('upload_files', [])
        task    = MainTask.objects.create(**validated_data)
        request = self.context.get('request')

        for f in files:
            TaskAttachment.objects.create(
                task=task,
                file=f,
                uploaded_by=request.user if request else None,
            )
        return task

    def update(self, instance, validated_data):
        files   = validated_data.pop('upload_files', [])
        request = self.context.get('request')

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        for f in files:
            TaskAttachment.objects.create(
                task=instance,
                file=f,
                uploaded_by=request.user if request else None,
            )
        return instance