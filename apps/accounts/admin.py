# apps/accounts/admin.py
from django.contrib import admin
from .models import User, Employee, Role, Department
from .audit  import AuditLog

admin.site.register(User)
admin.site.register(Employee)
admin.site.register(Role)
admin.site.register(Department)

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ['timestamp', 'actor', 'action', 'resource', 'resource_id', 'ip_address']
    list_filter   = ['action', 'resource']
    search_fields = ['actor__email', 'resource', 'resource_id']
    readonly_fields = ['timestamp', 'actor', 'action', 'resource',
                       'resource_id', 'detail', 'ip_address']