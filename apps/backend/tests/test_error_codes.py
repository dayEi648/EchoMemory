"""错误码与核心异常单元测试。"""

import warnings

import pytest

from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.core.exceptions.codes import ErrorCode, HttpStatus


class TestErrorCode:
    """验证 ErrorCode 枚举的数值、属性与分层。"""

    def test_success_code_is_zero(self):
        """SUCCESS 错误码为 0。"""
        assert ErrorCode.SUCCESS.value == 0
        assert ErrorCode.SUCCESS.http_status == HttpStatus.OK

    def test_error_code_has_http_status(self):
        """每个错误码都能返回推荐 HTTP 状态码。"""
        assert ErrorCode.AUTH_CREDENTIALS_INVALID.http_status == HttpStatus.UNAUTHORIZED
        assert ErrorCode.PERMISSION_DENIED.http_status == HttpStatus.FORBIDDEN
        assert ErrorCode.MUSIC_NOT_FOUND.http_status == HttpStatus.NOT_FOUND
        assert ErrorCode.USER_USERNAME_EXISTS.http_status == HttpStatus.CONFLICT
        assert ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS.http_status == HttpStatus.UNPROCESSABLE_ENTITY

    def test_error_code_has_description(self):
        """每个错误码都有中文说明。"""
        assert ErrorCode.AUTH_CREDENTIALS_INVALID.description == "用户名或密码错误"
        assert ErrorCode.SYSTEM_INTERNAL_ERROR.description == "系统内部错误"

    def test_from_status_mapping(self):
        """from_status 能根据 HTTP 状态码返回通用错误码。"""
        assert ErrorCode.from_status(HttpStatus.UNAUTHORIZED) == ErrorCode.AUTH_CREDENTIALS_INVALID
        assert ErrorCode.from_status(HttpStatus.FORBIDDEN) == ErrorCode.PERMISSION_DENIED
        assert ErrorCode.from_status(HttpStatus.NOT_FOUND) == ErrorCode.RESOURCE_NOT_FOUND
        assert ErrorCode.from_status(HttpStatus.INTERNAL_SERVER_ERROR) == ErrorCode.SYSTEM_INTERNAL_ERROR

    def test_from_status_unknown_fallback(self):
        """from_status 对未映射状态码返回 UNKNOWN_ERROR。"""
        assert ErrorCode.from_status(418) == ErrorCode.UNKNOWN_ERROR
        assert ErrorCode.from_status(999) == ErrorCode.UNKNOWN_ERROR

    def test_layer_boundaries(self):
        """错误码区间分层正确。"""
        assert 10000 <= ErrorCode.USER_USERNAME_EXISTS.value < 20000
        assert 20000 <= ErrorCode.AUTH_CREDENTIALS_INVALID.value < 30000
        assert 30000 <= ErrorCode.EXTERNAL_AI_RESPONSE_FAILED.value < 40000
        assert 40000 <= ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS.value < 50000
        assert 50000 <= ErrorCode.SYSTEM_INTERNAL_ERROR.value < 60000
        assert 90000 <= ErrorCode.UNKNOWN_ERROR.value < 100000


class TestBusinessError:
    """验证 BusinessError 与新错误码体系集成。"""

    def test_new_call_with_error_code(self):
        """新调用方式使用 ErrorCode 并推导 status_code。"""
        exc = BusinessError("用户名已存在", code=ErrorCode.USER_USERNAME_EXISTS)
        assert exc.detail == "用户名已存在"
        assert exc.code == ErrorCode.USER_USERNAME_EXISTS
        assert exc.status_code == HttpStatus.CONFLICT

    def test_new_call_with_overridden_status_code(self):
        """新调用方式允许显式覆盖 status_code。"""
        exc = BusinessError(
            "自定义",
            code=ErrorCode.USER_USERNAME_EXISTS,
            status_code=HttpStatus.BAD_REQUEST,
        )
        assert exc.status_code == HttpStatus.BAD_REQUEST
        assert exc.code == ErrorCode.USER_USERNAME_EXISTS

    def test_new_call_with_int_code(self):
        """允许传入整数错误码并自动转换为 ErrorCode。"""
        exc = BusinessError("测试", code=10001)
        assert exc.code == ErrorCode.USER_USERNAME_EXISTS

    def test_deprecated_positional_status_code(self):
        """旧调用 BusinessError(detail, status_code) 仍兼容并推导错误码。"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            exc = BusinessError("旧调用", 401)

        assert exc.status_code == 401
        assert exc.code == ErrorCode.AUTH_CREDENTIALS_INVALID
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)

    def test_deprecated_keyword_status_code(self):
        """旧调用 BusinessError(detail, status_code=...) 仍兼容。"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            exc = BusinessError("旧调用", status_code=404)

        assert exc.status_code == 404
        assert exc.code == ErrorCode.RESOURCE_NOT_FOUND
        assert len(w) == 1

    def test_no_code_no_status_defaults_to_400(self):
        """只传 detail 时默认 400。"""
        exc = BusinessError("缺少参数")
        assert exc.status_code == HttpStatus.BAD_REQUEST
        assert exc.code == ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS

    def test_success_code_is_rejected(self):
        """不允许使用 SUCCESS 作为业务错误码。"""
        with pytest.raises(ValueError):
            BusinessError("错误", code=ErrorCode.SUCCESS)
        with pytest.raises(ValueError):
            BusinessError("错误", code=0)


class TestHttpStatus:
    """验证 HttpStatus 常量。"""

    def test_common_status_codes(self):
        """常用状态码数值正确。"""
        assert HttpStatus.OK == 200
        assert HttpStatus.CREATED == 201
        assert HttpStatus.NO_CONTENT == 204
        assert HttpStatus.BAD_REQUEST == 400
        assert HttpStatus.UNAUTHORIZED == 401
        assert HttpStatus.FORBIDDEN == 403
        assert HttpStatus.NOT_FOUND == 404
        assert HttpStatus.CONFLICT == 409
        assert HttpStatus.UNPROCESSABLE_ENTITY == 422
        assert HttpStatus.TOO_MANY_REQUESTS == 429
        assert HttpStatus.INTERNAL_SERVER_ERROR == 500


class TestErrorCodeComparisons:
    """验证 ErrorCode 的数值比较行为。"""

    def test_intenum_equality(self):
        """ErrorCode 成员可与整数比较。"""
        assert ErrorCode.USER_USERNAME_EXISTS == 10001
        assert ErrorCode.USER_USERNAME_EXISTS != 10002

    def test_intenum_ordering(self):
        """ErrorCode 成员支持顺序比较。"""
        assert ErrorCode.USER_USERNAME_EXISTS < ErrorCode.AUTH_CREDENTIALS_INVALID
