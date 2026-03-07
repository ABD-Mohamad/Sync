# apps/accounts/schema.py
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class BearerAuthScheme(OpenApiAuthenticationExtension):
    """
    Registers the BearerAuth security scheme for both
    EmployeeJWTAuthentication and UnifiedJWTAuthentication.
    """
    target_class = 'apps.accounts.authentication.EmployeeJWTAuthentication'
    name         = 'BearerAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type'        : 'http',
            'scheme'      : 'bearer',
            'bearerFormat': 'JWT',
            'description' : 'Paste your access token. Works for Users and Employees.',
        }