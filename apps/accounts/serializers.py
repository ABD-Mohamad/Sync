# apps/accounts/serializers.py
from django.utils   import timezone
from rest_framework import serializers
from .models        import User, Employee, Role, Department, Profile


# ─── Mixins ───────────────────────────────────────────────────

class UniqueEmailMixin:
    email_model = None

    def validate_email(self, email):
        if self.instance:
            return email
        if self.email_model.objects.filter(email=email).exists():
            raise serializers.ValidationError(f'{email} is already registered.')
        return email

    def validate(self, data):
        root = self.parent
        if isinstance(root, serializers.ListSerializer):
            seen  = getattr(root, '_seen_emails', set())
            email = data.get('email', '').lower()
            if email in seen:
                raise serializers.ValidationError(
                    {'email': f'{email} appears more than once in this request.'}
                )
            seen.add(email)
            root._seen_emails = seen
        return data


# ─── User Serializers ─────────────────────────────────────────

class UserCreateSerializer(UniqueEmailMixin, serializers.ModelSerializer):
    """
    Used by the IT manager to create new web users.

    FIX: role is now a SlugRelatedField that accepts role names ('it',
    'department_head') instead of the FK primary key.  The Angular
    frontend always sends role as a string slug — the backend looked up
    the Role object by name via SlugRelatedField.

    Previously this was an implicit PrimaryKeyRelatedField which meant
    the frontend had to know the Role PK, requiring an extra /roles/
    fetch.  Slug-based lookup removes that round-trip.
    """
    email_model = User

    role = serializers.SlugRelatedField(
        slug_field='name',
        queryset=Role.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model            = User
        fields           = ['id', 'full_name', 'email', 'role', 'department']
        read_only_fields = ['id']

    def validate_role(self, role):
        if role and role.name not in [Role.IT, Role.DEPARTMENT_HEAD]:
            raise serializers.ValidationError('Invalid role.')
        return role


class UserResponseSerializer(serializers.ModelSerializer):
    role       = serializers.SlugRelatedField(slug_field='name', read_only=True)
    department = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            'id', 'email', 'full_name', 'role',
            'department', 'must_change_password',
            'is_superuser',
        ]

    def get_department(self, obj):
        # Primary: user.department FK
        if obj.department:
            return str(obj.department)
        # Fallback: check if this user is currently the head of any department
        # (handles the case where Department.head was set from the department side
        # but User.department FK was not yet synced)
        dept = obj.headed_departments.first()
        return str(dept) if dept else None


class UserProfileSerializer(serializers.ModelSerializer):
    role        = serializers.SlugRelatedField(slug_field='name', read_only=True)
    department  = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            'id', 'email', 'full_name', 'role',
            'department', 'must_change_password', 'is_superuser', 'permissions',
        ]

    def get_department(self, obj):
        # Primary: user.department FK
        if obj.department:
            return str(obj.department)
        # Fallback: reverse lookup via Department.head
        dept = obj.headed_departments.first()
        return str(dept) if dept else None

    def get_permissions(self, obj):
        if obj.is_superuser:
            return ['all']
        if not obj.role:
            return []
        return {
            Role.IT: [
                'create_user', 'create_employee',
                'manage_departments', 'view_all',
            ],
            Role.DEPARTMENT_HEAD: [
                'manage_subtasks', 'assign_employees',
                'review_requests', 'view_department',
            ],
        }.get(obj.role.name, [])


# ─── Employee Serializers ─────────────────────────────────────

class EmployeeCreateSerializer(UniqueEmailMixin, serializers.ModelSerializer):
    email_model = Employee

    class Meta:
        model            = Employee
        fields           = ['id', 'full_name', 'email', 'phone',
                            'department', 'hired_at']
        read_only_fields = ['id']


class EmployeeResponseSerializer(serializers.ModelSerializer):
    department = serializers.StringRelatedField()

    class Meta:
        model  = Employee
        fields = ['id', 'full_name', 'email', 'phone', 'department',
                  'status', 'hired_at', 'must_change_password']


# ─── Department Serializers ───────────────────────────────────

class DepartmentSerializer(serializers.ModelSerializer):
    head_name      = serializers.SerializerMethodField()
    employee_count = serializers.IntegerField(read_only=True, required=False)
    task_count     = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model            = Department
        fields           = ['id', 'name', 'head', 'head_name', 'employee_count', 'task_count']
        read_only_fields = ['id']

    def to_representation(self, instance):
        if not instance.head:
            head = User.objects.filter(
                department=instance,
                role__name=Role.DEPARTMENT_HEAD,
            ).first()
            if head:
                instance.head = head
        return super().to_representation(instance)

    def get_head_name(self, obj):
        return obj.head.full_name if obj.head else None

    def validate_head(self, user):
        if user and user.role and user.role.name != Role.DEPARTMENT_HEAD:
            raise serializers.ValidationError(
                'Assigned head must have the Department Head role.'
            )
        return user

    def update(self, instance, validated_data):
        new_head = validated_data.get('head', instance.head)
        old_head = instance.head

        instance = super().update(instance, validated_data)

        # ── Sync User.department when head changes ──────────────────
        # When we assign a new head, set their User.department so that
        # the login profile returns the correct department (not null).
        if new_head and new_head != old_head:
            new_head.department = instance
            new_head.save(update_fields=['department'])

        # If the old head was removed, clear their department FK
        if old_head and old_head != new_head:
            old_head.department = None
            old_head.save(update_fields=['department'])

        return instance

    def create(self, validated_data):
        head = validated_data.get('head')
        instance = super().create(validated_data)

        # Sync User.department on initial creation with a head
        if head:
            head.department = instance
            head.save(update_fields=['department'])

        return instance


# ─── Auth Serializers ─────────────────────────────────────────

class UnifiedLoginSerializer(serializers.Serializer):
    email    = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UnifiedChangePasswordSerializer(serializers.Serializer):
    old_password     = serializers.CharField(write_only=True)
    new_password     = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        from django.contrib.auth.password_validation import validate_password
        validate_password(value)
        return value

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError('Passwords do not match.')
        return data


# ─── Profile Serializers ──────────────────────────────────────

class ProfileSerializer(serializers.ModelSerializer):
    profile_picture     = serializers.ImageField(required=False, use_url=True)
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model            = Profile
        fields           = [
            'id', 'degree', 'profile_picture', 'profile_picture_url',
            'date_of_birth', 'phone_number', 'bio',
            'skills', 'linkedin_url', 'updated_at',
        ]
        read_only_fields = ['id', 'profile_picture_url', 'updated_at']

    def get_profile_picture_url(self, obj):
        if not obj.profile_picture:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(obj.profile_picture.url) if request else obj.profile_picture.url

    def validate_date_of_birth(self, value):
        if value >= timezone.now().date():
            raise serializers.ValidationError('Date of birth must be in the past.')
        return value

    def validate_profile_picture(self, image):
        if image.size > 2 * 1024 * 1024:
            raise serializers.ValidationError('Image size must not exceed 2MB.')
        if hasattr(image, 'content_type') and image.content_type not in [
            'image/jpeg', 'image/png', 'image/webp'
        ]:
            raise serializers.ValidationError('Only JPEG, PNG, and WebP images are allowed.')
        return image

    def validate_skills(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('Skills must be a list.')
        if not all(isinstance(s, str) for s in value):
            raise serializers.ValidationError('Each skill must be a string.')
        return value


# ─── Employee Performance Serializers ────────────────────────
#
# FIX: These serializers were previously in apps/tasks/serializers.py
# and imported from apps/accounts/views.py (EmployeeViewSet).
#
# That caused a circular import at startup because INSTALLED_APPS loads
# 'apps.accounts' BEFORE 'apps.tasks'. When accounts/urls.py triggered
# accounts/views.py at module level, importing from tasks/serializers.py
# tried to load tasks/models.py before the tasks app registry was ready
# → AppRegistryNotReady.
#
# Defining them here in accounts/serializers.py removes the cross-app
# import entirely.  tasks/serializers.py keeps its own WarningEntrySerializer
# (used only by ManagerDashboardSerializer inside tasks).
#
# ─── Action required in accounts/views.py ────────────────────────────────
# Change:
#   from apps.tasks.serializers import WarningListSerializer
# To:
#   from apps.accounts.serializers import WarningListSerializer

class EmployeePerformanceSummarySerializer(serializers.Serializer):
    total_staff      = serializers.IntegerField()
    avg_performance  = serializers.FloatField()
    avg_delay_rate   = serializers.FloatField()
    compliance_rate  = serializers.FloatField()
    critical_delays  = serializers.IntegerField()


class EmployeePerformanceRowSerializer(serializers.Serializer):
    id                = serializers.IntegerField()
    full_name         = serializers.CharField()
    email             = serializers.EmailField()
    dept_name         = serializers.CharField(allow_null=True)
    status            = serializers.CharField()
    total_sub         = serializers.IntegerField()
    completion_rate   = serializers.FloatField()
    delay_rate        = serializers.FloatField()
    performance_score = serializers.FloatField()
    performance_label = serializers.CharField()


class EmployeeDirectorySerializer(serializers.Serializer):
    """
    Used by GET /api/accounts/employees/performance/
    Wraps the output of tasks.selectors.get_employee_performance().
    """
    summary   = EmployeePerformanceSummarySerializer()
    employees = EmployeePerformanceRowSerializer(many=True)


class WarningListSerializer(serializers.Serializer):
    """
    Used by GET /api/accounts/employees/warnings/ (or similar action
    in EmployeeViewSet).  Includes extra fields (performance_score,
    performance_label) compared to ManagerDashboard's WarningEntrySerializer.
    """
    id                = serializers.IntegerField()
    full_name         = serializers.CharField()
    email             = serializers.EmailField()
    dept_name         = serializers.CharField(allow_null=True)
    delay_rate        = serializers.FloatField()
    completion_rate   = serializers.FloatField()
    performance_score = serializers.FloatField()
    performance_label = serializers.CharField()
    last_activity     = serializers.DateTimeField(allow_null=True, required=False)