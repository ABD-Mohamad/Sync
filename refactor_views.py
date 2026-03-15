import re

with open(r'c:\Users\Abdullah\Projects\django\Sync\apps\accounts\views.py', 'r', encoding='utf-8') as f:
    text = f.read()

replacement = """class BaseAccountViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    create_serializer_class   = None
    response_serializer_class = None
    welcome_email_func        = None

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update', 'bulk_create']:
            return self.create_serializer_class
        return self.response_serializer_class

    def update(self, request, *args, **kwargs):
        instance   = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(self.response_serializer_class(obj).data)

    @extend_schema(exclude=True)
    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        temp_password = generate_temp_password()
        
        obj = serializer.save(must_change_password=True)
        obj.set_password(temp_password)
        obj.save()

        if self.welcome_email_func:
            self.welcome_email_func(obj, temp_password)

        return Response(
            self.response_serializer_class(obj).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        if not isinstance(request.data, list):
            return Response(
                {'detail': 'Expected a list of accounts.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not (2 <= len(request.data) <= 50):
            return Response(
                {'detail': 'Bulk create requires between 2 and 50 accounts.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        created = []
        failed  = []

        model_class = self.queryset.model

        for item_data in serializer.validated_data:
            try:
                temp_password = generate_temp_password()
                obj = model_class(**item_data)
                obj.must_change_password = True
                obj.set_password(temp_password)
                obj.save()
                
                if self.welcome_email_func:
                    self.welcome_email_func(obj, temp_password)
                created.append(obj)
            except Exception as e:
                failed.append({'email': item_data.get('email'), 'reason': str(e)})

        response_data = {
            'created': self.response_serializer_class(created, many=True).data,
            'count'  : len(created),
        }
        if failed:
            response_data['failed'] = failed

        return Response(response_data, status=status.HTTP_201_CREATED)


class UserViewSet(BaseAccountViewSet):
    queryset                  = User.objects.select_related('role', 'department').all()
    permission_classes        = [IsITOrAdmin]
    create_serializer_class   = UserCreateSerializer
    response_serializer_class = UserResponseSerializer
    
    @staticmethod
    def welcome_email_func(user, password):
        send_user_welcome_email(user, password)

    @extend_schema(
        request=UserCreateSerializer,
        responses={201: UserResponseSerializer},
        summary='Create a system user',
        tags=['User Management'],
    )
    @audit_action(action='create', resource='User')
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

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
        return super().update(request, *args, **kwargs)

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
    def bulk_create(self, request):
        return super().bulk_create(request)


class EmployeeViewSet(BaseAccountViewSet):
    queryset                  = Employee.objects.select_related('department').all()
    permission_classes        = [IsITOrAdmin]
    filterset_fields          = ['department', 'status']
    search_fields             = ['full_name', 'email', 'phone']
    ordering_fields           = ['full_name', 'hired_at', 'created_at']
    ordering                  = ['full_name']
    
    create_serializer_class   = EmployeeCreateSerializer
    response_serializer_class = EmployeeResponseSerializer
    
    @staticmethod
    def welcome_email_func(employee, password):
        send_employee_welcome_email(employee, password)

    @extend_schema(
        request=EmployeeCreateSerializer,
        responses={201: EmployeeResponseSerializer},
        summary='Create an employee',
        tags=['Employee Management'],
    )
    @audit_action(action='create', resource='Employee')
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

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
        return super().update(request, *args, **kwargs)

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
    def bulk_create(self, request):
        return super().bulk_create(request)

"""

pattern = re.compile(r'class UserViewSet\(.*?class AuthViewSet\(', re.DOTALL)
text = pattern.sub(replacement + 'class AuthViewSet(', text)

with open(r'c:\Users\Abdullah\Projects\django\Sync\apps\accounts\views.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("done")
