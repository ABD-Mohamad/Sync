# apps/notifications/fcm_views.py
#
# REST endpoint for registering an FCM browser token.
#
# PRIMARY path:  WebSocket 'register_fcm_token' message (consumers.py)
#   - No extra HTTP round-trip
#   - Fires immediately when Angular receives the token from Firebase SDK
#
# FALLBACK path: PATCH /api/notifications/fcm-token/
#   - Used when the WebSocket isn't open yet (first load, page refresh)
#   - Also used by the Employee portal before WS connection is established
#
# URL: add to your project urls.py:
#   path('api/notifications/', include('apps.notifications.notification_urls')),
#
# Or directly in a urlconf:
#   path('api/notifications/fcm-token/', RegisterFCMTokenView.as_view(), name='fcm-token'),

from rest_framework.views       import APIView
from rest_framework.response    import Response
from rest_framework             import status
from rest_framework.permissions import IsAuthenticated

from apps.accounts.authentication import (
    UnifiedJWTAuthentication,
    EmployeeJWTAuthentication,
)


class RegisterFCMTokenView(APIView):
    """
    PATCH /api/notifications/fcm-token/

    Saves the FCM Web Push token for the authenticated User or Employee.

    Request body:
        { "token": "<firebase_fcm_token_string>" }

    Response:
        200  { "detail": "FCM token registered." }
        400  { "detail": "Token is required." }

    Authentication:
        - User    → UnifiedJWTAuthentication (DH / IT Manager)
        - Employee → EmployeeJWTAuthentication (Employee portal)
    """
    authentication_classes = [UnifiedJWTAuthentication, EmployeeJWTAuthentication]
    permission_classes     = [IsAuthenticated]

    def patch(self, request):
        token = request.data.get('token', '').strip()

        if not token:
            return Response(
                {'detail': 'Token is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Determine if this is a User or Employee session
        # EmployeeJWTAuthentication returns (None, token) — request.user is None
        if request.user is None or not hasattr(request.user, 'id'):
            # Employee session — get employee from the raw token
            raw_token     = request.auth
            employee_id   = raw_token.get('employee_id') if raw_token else None

            if not employee_id:
                return Response(
                    {'detail': 'Could not identify employee.'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            from apps.accounts.models import Employee
            Employee.objects.filter(id=employee_id).update(fcm_token=token)
            return Response({'detail': 'FCM token registered.', 'type': 'employee'})

        else:
            # User session (DH / IT Manager)
            request.user.__class__.objects.filter(id=request.user.id).update(
                fcm_token=token
            )
            return Response({'detail': 'FCM token registered.', 'type': 'user'})

    def delete(self, request):
        """
        DELETE /api/notifications/fcm-token/
        Clears the FCM token on logout or when notification permission is revoked.
        """
        if request.user is None or not hasattr(request.user, 'id'):
            raw_token   = request.auth
            employee_id = raw_token.get('employee_id') if raw_token else None
            if employee_id:
                from apps.accounts.models import Employee
                Employee.objects.filter(id=employee_id).update(fcm_token=None)
        else:
            request.user.__class__.objects.filter(id=request.user.id).update(
                fcm_token=None
            )

        return Response(status=status.HTTP_204_NO_CONTENT)