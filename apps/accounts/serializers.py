# apps/accounts/serializers.py
from rest_framework import serializers
from .models        import User, Employee, Role, Department


class UserCreateSerializer(serializers.ModelSerializer):
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


class EmployeeCreateSerializer(serializers.ModelSerializer):
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