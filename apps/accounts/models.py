# apps/accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, email, full_name, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, full_name, password, **extra_fields)


class Role(models.Model):
    """
    Defines the role of a system user.
    Values: IT, Department Head
    """
    IT              = 'it'
    DEPARTMENT_HEAD = 'department_head'

    ROLE_CHOICES = [
        (IT,              'IT'),
        (DEPARTMENT_HEAD, 'Department Head'),
    ]

    name = models.CharField(
        max_length=50,
        unique=True,
        choices=ROLE_CHOICES,
    )

    def __str__(self):
        return self.get_name_display()

    class Meta:
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'


class Department(models.Model):
    name = models.CharField(max_length=150, unique=True)

    head = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_departments',
    )

    def clean(self):
        """
        Model-level validation — enforced everywhere:
        admin panel, shell, serializer, management commands.
        """
        from django.core.exceptions import ValidationError
        if (self.head
                and self.head.role
                and self.head.role.name != Role.DEPARTMENT_HEAD):
            raise ValidationError(
                f'{self.head.full_name} does not have the Department Head role.'
            )

    def save(self, *args, **kwargs):
        self.full_clean()  # always run clean() before saving
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
class User(AbstractUser):
    """
    System user — Managers and Department Heads only.
    These are people who log into the web application.
    """
    username   = None
    email      = models.EmailField(unique=True)
    full_name  = models.CharField(max_length=200)

    objects = UserManager()

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='users',
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['full_name']
    must_change_password = models.BooleanField(default=False)
    def __str__(self):
        return f'{self.full_name} ({self.email})'

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'


class Employee(models.Model):
    """
    Represents a field employee who uses the mobile app.
    Completely independent from the User/auth system.
    Has its own credentials for mobile authentication.
    """
    class Status(models.TextChoices):
        ACTIVE   = 'active',   'Active'
        INACTIVE = 'inactive', 'Inactive'

    full_name  = models.CharField(max_length=200)
    email      = models.EmailField(unique=True)
    phone      = models.CharField(max_length=20, blank=True)
    status     = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
    )

    # Mobile app authentication
    password   = models.CharField(max_length=128)  # stores hashed password
    must_change_password = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)

    hired_at   = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True , null=True)
    updated_at = models.DateTimeField(auto_now=True,null=True)

    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password)

    def __str__(self):
        return f'{self.full_name} ({self.department})'

    class Meta:
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'
        ordering = ['full_name']