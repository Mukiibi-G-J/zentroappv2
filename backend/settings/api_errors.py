from rest_framework.response import Response


def error_response(code, message, details=None, status_code=400):
    return Response(
        {
            "code": code,
            "message": message,
            "details": details or {},
        },
        status=status_code,
    )
