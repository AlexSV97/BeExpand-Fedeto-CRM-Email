from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

async def soc_error_handler(request: Request, exc: Exception) -> JSONResponse:
    '''Return safe error responses for SOC endpoints — no stack traces.'''
    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            'error': 'An internal error occurred',
            'message': 'An internal error occurred',
            'code': 'INTERNAL_ERROR',
            'trace_id': str(id(exc))[-8:],
        }
    )
