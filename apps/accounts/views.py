# apps/accounts/views.py
from django.contrib.auth         import authenticate
from django.contrib.auth.hashers import make_password
from django.utils                import timezone
from rest_framework              import status, mixins, viewsets
from rest_framework.decorators   import action
from rest_framework.permissions  import IsAuthenticated, AllowAny
from rest_framework.response     import Response
from rest_framework_simplejwt.tokens     import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_spectacular.utils       import extend_schema, OpenApiResponse

from apps.accounts.models      import User, Employee, Department
from apps.accounts.serializers import (
    UserCreateSerializer, UserResponseSerializer,
    EmployeeCreateSerializer, EmployeeResponseSerializer,
    UserProfileSerializer, DepartmentSerializer,
    UnifiedLoginSerializer, UnifiedChangePasswordSerializer,
)
from apps.accounts.permissions import IsITOrAdmin
from apps.accounts.throttles   import LoginRateThrottle, SensitiveEndpointThrottle
from apps.accounts.tokens      import (
    get_tokens_for_user, get_tokens_for_employee, refresh_employee_token
)
from apps.accounts.utils import (
    generate_temp_password,
    send_user_welcome_email,
    send_employee_welcome_email,
)
from apps.accounts.audit import audit_action, AuditLog, get_client_ip


class UserViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset           = User.objects.select_related('role', 'department').all()
    permission_classes = [IsITOrAdmin]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return UserCreateSerializer
        return UserResponseSerializer

    @extend_schema(
        request=UserCreateSerializer,
        responses={201: UserResponseSerializer},
        summary='Create a system user',
        tags=['User Management'],
    )
    @audit_action(action='create', resource='User')
    def create(self, request, *args, **kwargs):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        temp_password = generate_temp_password()
        user = serializer.save(must_change_password=True)
        user.set_password(temp_password)
        user.save()

        send_user_welcome_email(user, temp_password)

        return Response(
            UserResponseSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        responses={200: UserResponseSerializer(many=True)},
        summary='List all system users',
        tags=['User Management'],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        responses={200: UserResponseSerializer},
        summary='Get a system user',
        tags=['User Management'],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        request=UserCreateSerializer,
        responses={200: UserResponseSerializer},
        summary='Update a system user',
        tags=['User Management'],
    )
    @audit_action(action='update', resource='User')
    def update(self, request, *args, **kwargs):
        instance   = self.get_object()
        serializer = UserCreateSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserResponseSerializer(user).data)

    @extend_schema(exclude=True)
    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @extend_schema(
        summary='Deactivate a system user',
        tags=['User Management'],
    )
    @audit_action(action='delete', resource='User')
    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response(
            {'detail': 'User deactivated successfully.'},
            status=status.HTTP_200_OK,
        )
    @extend_schema(
        request=UserCreateSerializer(many=True),
        responses={201: UserResponseSerializer(many=True)},
        summary='Bulk create system users',
        tags=['User Management'],
    )
    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        if not isinstance(request.data, list):
            return Response(
                {'detail': 'Expected a list of users.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not (2 <= len(request.data) <= 50):
            return Response(
                {'detail': 'Bulk create requires between 2 and 50 users.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = UserCreateSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        created = []
        failed  = []

        for user_data in serializer.validated_data:
            try:
                temp_password = generate_temp_password()
                user = User(
                    full_name            = user_data['full_name'],
                    email                = user_data['email'],
                    role                 = user_data.get('role'),
                    department           = user_data.get('department'),
                    must_change_password = True,
                )
                user.set_password(temp_password)
                user.save()
                send_user_welcome_email(user, temp_password)
                created.append(user)
            except Exception as e:
                failed.append({'email': user_data.get('email'), 'reason': str(e)})

        response_data = {
            'created': UserResponseSerializer(created, many=True).data,
            'count'  : len(created),
        }
        if failed:
            response_data['failed'] = failed

        return Response(response_data, status=status.HTTP_201_CREATED)



class EmployeeViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset           = Employee.objects.select_related('department').all()
    permission_classes = [IsITOrAdmin]
    filterset_fields   = ['department', 'status']
    search_fields      = ['full_name', 'email', 'phone']
    ordering_fields    = ['full_name', 'hired_at', 'created_at']
    ordering           = ['full_name']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return EmployeeCreateSerializer
        return EmployeeResponseSerializer

    @extend_schema(
        request=EmployeeCreateSerializer,
        responses={201: EmployeeResponseSerializer},
        summary='Create an employee',
        tags=['Employee Management'],
    )
    @audit_action(action='create', resource='Employee')
    def create(self, request, *args, **kwargs):
        serializer = EmployeeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        temp_password = generate_temp_password()
        employee = serializer.save(
            password=make_password(temp_password),
            must_change_password=True,
        )

        send_employee_welcome_email(employee, temp_password)

        return Response(
            EmployeeResponseSerializer(employee).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        responses={200: EmployeeResponseSerializer(many=True)},
        summary='List all employees',
        tags=['Employee Management'],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        responses={200: EmployeeResponseSerializer},
        summary='Get an employee',
        tags=['Employee Management'],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        request=EmployeeCreateSerializer,
        responses={200: EmployeeResponseSerializer},
        summary='Update an employee',
        tags=['Employee Management'],
    )
    @audit_action(action='update', resource='Employee')
    def update(self, request, *args, **kwargs):
        instance   = self.get_object()
        serializer = EmployeeCreateSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()
        return Response(EmployeeResponseSerializer(employee).data)

    @extend_schema(exclude=True)
    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @extend_schema(
        summary='Deactivate an employee',
        tags=['Employee Management'],
    )
    @audit_action(action='delete', resource='Employee')
    def destroy(self, request, *args, **kwargs):
        employee = self.get_object()
        employee.status = Employee.Status.INACTIVE
        employee.save()
        return Response(
            {'detail': 'Employee deactivated successfully.'},
            status=status.HTTP_200_OK,
        )
    @extend_schema(
    request=EmployeeCreateSerializer(many=True),
    responses={201: EmployeeResponseSerializer(many=True)},
    summary='Bulk create employees',
    tags=['Employee Management'],
)
    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        if not isinstance(request.data, list):
            return Response(
                {'detail': 'Expected a list of employees.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not (2 <= len(request.data) <= 50):
            return Response(
                {'detail': 'Bulk create requires between 2 and 50 employees.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = EmployeeCreateSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        created = []
        failed  = []

        for employee_data in serializer.validated_data:
            try:
                temp_password = generate_temp_password()
                employee = Employee(
                    full_name            = employee_data['full_name'],
                    email                = employee_data['email'],
                    phone                = employee_data.get('phone', ''),
                    department           = employee_data.get('department'),
                    hired_at             = employee_data.get('hired_at'),
                    must_change_password = True,
                )
                employee.set_password(temp_password)
                employee.save()
                send_employee_welcome_email(employee, temp_password)
                created.append(employee)
            except Exception as e:
                failed.append({'email': employee_data.get('email'), 'reason': str(e)})

        response_data = {
            'created': EmployeeResponseSerializer(created, many=True).data,
            'count'  : len(created),
        }
        if failed:
            response_data['failed'] = failed

        return Response(response_data, status=status.HTTP_201_CREATED)
class AuthViewSet(viewsets.GenericViewSet):
    permission_classes = [AllowAny]

    @extend_schema(
        request=UnifiedLoginSerializer,
        responses={200: OpenApiResponse(description='JWT tokens + profile')},
        summary='Login — works for all account types',
        tags=['Auth'],
    )
    @action(
        detail=False, methods=['post'], url_path='login',
        throttle_classes=[LoginRateThrottle],
    )
    def login(self, request):
        serializer = UnifiedLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email    = serializer.validated_data['email']
        password = serializer.validated_data['password']

        # ── Try User first ────────────────────────────────────
        user = authenticate(request, email=email, password=password)
        if user:
            if not user.is_active:
                return Response(
                    {'detail': 'Account is inactive.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Log login audit
            AuditLog.objects.create(
                actor=user,
                action=AuditLog.Action.LOGIN,
                resource='User',
                resource_id=str(user.id),
                ip_address=get_client_ip(request),
            )

            return Response({
                'account_type'        : 'user',
                'must_change_password': user.must_change_password,
                'profile'             : UserResponseSerializer(user).data,
                **get_tokens_for_user(user),
            })

        # ── Try Employee ──────────────────────────────────────
        try:
            employee = Employee.objects.get(email=email)
        except Employee.DoesNotExist:
            return Response(
                {'detail': 'Invalid email or password.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not employee.check_password(password):
            return Response(
                {'detail': 'Invalid email or password.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if employee.status != Employee.Status.ACTIVE:
            return Response(
                {'detail': 'Account is inactive.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        employee.last_login = timezone.now()
        employee.save(update_fields=['last_login'])

        return Response({
            'account_type'        : 'employee',
            'must_change_password': employee.must_change_password,
            'profile'             : EmployeeResponseSerializer(employee).data,
            **get_tokens_for_employee(employee),
        })

    @extend_schema(
        request=UnifiedChangePasswordSerializer,
        responses={200: OpenApiResponse(description='Password changed successfully.')},
        summary='Change password — works for all account types',
        tags=['Auth'],
    )
    @action(
        detail=False, methods=['post'], url_path='change-password',
        throttle_classes=[SensitiveEndpointThrottle],
    )
    def change_password(self, request):
        token = request.auth
        if token is None:
            return Response(
                {'detail': 'Authentication token required.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = UnifiedChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']

        # ── Employee ──────────────────────────────────────────
        if token.get('type') == 'employee':
            try:
                employee = Employee.objects.get(id=token['employee_id'])
            except Employee.DoesNotExist:
                return Response(
                    {'detail': 'Employee not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if not employee.check_password(old_password):
                return Response(
                    {'detail': 'Old password is incorrect.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            employee.set_password(new_password)
            employee.must_change_password = False
            employee.save()

        # ── User ──────────────────────────────────────────────
        else:
            user = request.user
            if not user or not user.is_authenticated:
                return Response(
                    {'detail': 'Authentication required.'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            if not user.check_password(old_password):
                return Response(
                    {'detail': 'Old password is incorrect.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user.set_password(new_password)
            user.must_change_password = False
            user.save()

        return Response({'detail': 'Password changed successfully.'})

    @extend_schema(
        summary='Refresh token — works for all account types',
        tags=['Auth'],
        request=OpenApiResponse(description='{"refresh": "<token>"}'),
        responses={200: OpenApiResponse(description='New access (+ refresh for employees)')},
    )
    @action(detail=False, methods=['post'], url_path='refresh')
    def refresh(self, request):
        raw_refresh = request.data.get('refresh')
        if not raw_refresh:
            return Response(
                {'detail': 'Refresh token required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Peek at the token to decide which flow ────────────
        try:
            peeked = RefreshToken(raw_refresh)
        except TokenError:
            return Response(
                {'detail': 'Invalid or expired refresh token.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # ── Employee refresh ──────────────────────────────────
        if peeked.get('type') == 'employee':
            try:
                tokens = refresh_employee_token(raw_refresh)
            except TokenError as e:
                return Response(
                    {'detail': str(e)},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            return Response(tokens)

        # ── User refresh (standard simplejwt flow) ────────────
        try:
            peeked.blacklist()
            from apps.accounts.models import User as UserModel
            user = UserModel.objects.select_related('role').get(
                id=peeked['user_id']
            )
            return Response(get_tokens_for_user(user))
        except Exception:
            return Response(
                {'detail': 'Invalid or expired refresh token.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

    @extend_schema(
        responses={200: UserProfileSerializer},
        summary='Get profile — system users only',
        tags=['Auth'],
    )
    @action(detail=False, methods=['get'], url_path='profile',
            permission_classes=[IsAuthenticated])
    def profile(self, request):
        return Response(UserProfileSerializer(request.user).data)

    @extend_schema(
        summary='Logout — blacklist refresh token',
        tags=['Auth'],
    )
    @action(detail=False, methods=['post'], url_path='logout',
            permission_classes=[IsAuthenticated])
    def logout(self, request):
        try:
            token = RefreshToken(request.data.get('refresh'))
            token.blacklist()

            # Log logout audit (only for Users, not employees)
            if request.user and request.user.is_authenticated:
                AuditLog.objects.create(
                    actor=request.user,
                    action=AuditLog.Action.LOGOUT,
                    resource='User',
                    resource_id=str(request.user.id),
                    ip_address=get_client_ip(request),
                )

            return Response({'detail': 'Logged out successfully.'})
        except Exception:
            return Response(
                {'detail': 'Invalid or expired token.'},
                status=status.HTTP_400_BAD_REQUEST,
            )


class DepartmentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset         = Department.objects.select_related('head').all()
    serializer_class = DepartmentSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsITOrAdmin()]

    @extend_schema(summary='Create a department', tags=['Departments'])
    @audit_action(action='create', resource='Department')
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary='List all departments', tags=['Departments'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary='Get department detail', tags=['Departments'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(summary='Update a department', tags=['Departments'])
    @audit_action(action='update', resource='Department')
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(summary='Delete a department', tags=['Departments'])
    @audit_action(action='delete', resource='Department')
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)