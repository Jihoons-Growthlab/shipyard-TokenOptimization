"""공통 오류 본문 {code, message, details}."""
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def validation(field: str, message: str) -> AppError:
    return AppError(400, "VALIDATION_ERROR", message, {"field": field})


def not_found(code: str, message: str) -> AppError:
    return AppError(404, code, message)


def duplicate(message: str, **details) -> AppError:
    return AppError(409, "DUPLICATE", message, details)


def unauthorized() -> AppError:
    return AppError(401, "UNAUTHORIZED", "세션이 만료되었거나 유효하지 않습니다.")


def _body(code: str, message: str, details: dict | None = None) -> dict:
    return {"code": code, "message": message, "details": jsonable_encoder(details or {})}


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(_body(exc.code, exc.message, exc.details), exc.status)

    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, exc: RequestValidationError):
        fields = [".".join(str(p) for p in e["loc"][1:]) for e in exc.errors()]
        return JSONResponse(_body("INVALID_FORMAT", "요청 형식이 올바르지 않습니다.", {"fields": fields}), 422)

    @app.exception_handler(HTTPException)
    async def _http(_: Request, exc: HTTPException):
        if exc.status_code == 404:
            return JSONResponse(_body("NOT_FOUND", "요청한 경로를 찾을 수 없습니다."), 404)
        return JSONResponse(_body("HTTP_ERROR", str(exc.detail)), exc.status_code)
