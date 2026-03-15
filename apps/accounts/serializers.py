# apps/accounts/serializers.py
from django.utils   import timezone
from rest_framework import serializers
from .models        import User, Employee, Role, Department, Profile


# ─── Mixins ───────────────────────────────────────────────────

class UniqueEmailMixin:
    """
    Reusable email validation for any serializer.
    - Skips check on update (instance already exists)
    - Checks DB uniqueness on create
    - Detects duplicates across bulk requests via ListSerializer
    """
    email_model = None  # set in each serializer

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
    email_model = User

    class Meta:
        model            = User
        fields           = ['id', 'full_name', 'email', 'role', 'department']
        read_only_fields = ['id']

    def validate_role(self, role):
        if role and role.name not in [Role.IT, Role.DEPARTMENT_HEAD]:
            raise serializers.ValidationError('Invalid role.')
        return role


class UserResponseSerializer(serializers.ModelSerializer):
    role       = serializers.StringRelatedField()
    department = serializers.StringRelatedField()

    class Meta:
        model  = User
        fields = ['id', 'full_name', 'email', 'role',
                  'department', 'must_change_password']


class UserProfileSerializer(serializers.ModelSerializer):
    role        = serializers.StringRelatedField()
    department  = serializers.StringRelatedField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ['id', 'full_name', 'email', 'role',
                  'department', 'must_change_password', 'permissions']

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
    head_name = serializers.SerializerMethodField()

    class Meta:
        model            = Department
        fields           = ['id', 'name', 'head', 'head_name']
        read_only_fields = ['id']

    def get_head_name(self, obj):
        return obj.head.full_name if obj.head else None

    def validate_head(self, user):
        if user and user.role and user.role.name != Role.DEPARTMENT_HEAD:
            raise serializers.ValidationError(
                'Assigned head must have the Department Head role.'
            )
        return user


# ─── Auth Serializers ─────────────────────────────────────────

class UnifiedLoginSerializer(serializers.Serializer):
    email    = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UnifiedChangePasswordSerializer(serializers.Serializer):
    old_password     = serializers.CharField(write_only=True)
    new_password     = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

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