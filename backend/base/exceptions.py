from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.db import IntegrityError
from django.core.exceptions import ValidationError


def custom_exception_handler(exc, context):
    """
    Custom exception handler for REST framework that handles common database errors.
    """
    response = exception_handler(exc, context)

    if isinstance(exc, IntegrityError):
        error_message = str(exc)
        error_code = 'integrity_error'
        
        # Handle specific integrity errors
        if 'unique constraint' in error_message.lower():
            if 'system_id' in error_message:
                error_code = 'duplicate_system_id'
                message = "A record with this system ID already exists."
            elif 'code' in error_message:
                error_code = 'duplicate_code'
                message = "A record with this code already exists."
            else:
                message = "This record already exists."
        else:
            message = "Database integrity error occurred."

        return Response(
            {
                "status": "error",
                "message": message,
                "detail": error_message,
                "code": error_code
            },
            status=status.HTTP_409_CONFLICT
        )

    elif isinstance(exc, ValidationError):
        return Response(
            {
                "status": "error",
                "message": "Validation failed",
                "errors": exc.message_dict if hasattr(exc, 'message_dict') else {'detail': str(exc)},
                "code": "validation_error"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # If response is already handled by DRF's exception handler
    elif response is not None:
        data = {
            "status": "error",
            "message": str(response.data.get('detail', "An error occurred")),
            "code": response.status_code
        }
        response.data = data
        return response

    # For unhandled exceptions
    return Response(
        {
            "status": "error",
            "message": "An unexpected error occurred",
            "detail": str(exc),
            "code": "server_error"
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )