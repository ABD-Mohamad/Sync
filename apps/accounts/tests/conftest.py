# apps/accounts/tests/conftest.py
"""
Shared fixtures and factories for the accounts test suite.

Factory Boy is used for all model creation so that individual tests
can override only the fields they care about, keeping each test minimal
and readable.
"""
import pytest
import factory
from django.contrib.auth.hashers import make_password

from apps.accounts.models import Role, Department, User, Employee


# ─── Factories ────────────────────────────────────────────────────────────────

class RoleFactory(factory.django.DjangoModelFactory):
    """Creates a Role row.  Use `name=Role.IT` or `name=Role.DEPARTMENT_HEAD`."""

    class Meta:
        model = Role
        django_get_or_create = ('name',)

    name = Role.IT


class DepartmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Department

    name = factory.Sequence(lambda n: f'Department {n}')
    head = None  # populated explicitly when needed


class UserFactory(factory.django.DjangoModelFactory):
    """
    Creates a fully functional Django User.

    The raw password is stored in `_password` so tests can read it back
    without re-hashing (simulating what a real user would type).
    """

    class Meta:
        model = User
        exclude = ('_password',)

    _password            = 'StrongPass1!'
    email                = factory.Sequence(lambda n: f'user{n}@example.com')
    full_name            = factory.Sequence(lambda n: f'User {n}')
    role                 = factory.SubFactory(RoleFactory)
    is_active            = True
    must_change_password = False

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        raw = kwargs.pop('_password', 'StrongPass1!')
        manager = cls._get_manager(model_class)
        return manager.create_user(password=raw, **kwargs)


class EmployeeFactory(factory.django.DjangoModelFactory):
    """
    Creates an Employee with a hashed password.

    Raw password is stored on the instance as `._raw_password` so tests
    can authenticate without knowing the hash.
    """

    class Meta:
        model = Employee

    full_name            = factory.Sequence(lambda n: f'Employee {n}')
    email                = factory.Sequence(lambda n: f'employee{n}@example.com')
    phone                = '+966500000000'
    status               = Employee.Status.ACTIVE
    must_change_password = False

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        raw_password = kwargs.pop('_password', 'StrongPass1!')
        instance = model_class(**kwargs)
        instance.set_password(raw_password)
        instance.save()
        # Stash the raw password so fixtures can expose it to tests.
        instance._raw_password = raw_password
        return instance

    class Params:
        # Shortcut: EmployeeFactory(inactive=True)
        inactive = factory.Trait(status=Employee.Status.INACTIVE)


# ─── Pytest Fixtures ─────────────────────────────────────────────────────────

RAW_PASSWORD = 'StrongPass1!'


@pytest.fixture
def it_role(db):
    """A pre-existing IT Role row (get_or_create safe)."""
    return RoleFactory(name=Role.IT)


@pytest.fixture
def active_user(db, it_role):
    """A standard, active User with the IT role."""
    return UserFactory(role=it_role, _password=RAW_PASSWORD)


@pytest.fixture
def active_employee(db):
    """A standard, active Employee."""
    return EmployeeFactory(_password=RAW_PASSWORD)


@pytest.fixture
def user_password():
    """Returns the plain-text password used by `active_user` / `active_employee`."""
    return RAW_PASSWORD


@pytest.fixture
def login_url():
    return '/api/accounts/auth/login/'


@pytest.fixture
def logout_url():
    return '/api/accounts/auth/logout/'


@pytest.fixture
def refresh_url():
    return '/api/accounts/auth/refresh/'