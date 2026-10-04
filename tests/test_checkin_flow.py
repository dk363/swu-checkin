"""签到时间、重试分类、验证码判断和 ticket 解析测试."""

import importlib
import json
import sys
from datetime import datetime
from io import StringIO
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import requests

from swu_checkin.cache import CheckinContext
from swu_checkin.check_in import (
    RETRYABLE_STATUS,
    _beijing_date_str,
    _check_vacation_enabled,
    _is_on_leave,
    _submit_checkin,
    check_in,
    check_in_with_retry,
)
from swu_checkin.get_info import (
    _get_ocr,
    _get_token,
    extract_ticket_from_url,
    is_captcha_error_response,
    recognize_captcha,
)

check_in_mod = importlib.import_module("swu_checkin.check_in")
get_info_mod = importlib.import_module("swu_checkin.get_info")

UTC = ZoneInfo("UTC")


class _Cookies:
    def clear(self) -> None:
        return None


class _Response:
    def __init__(self, url: str, text: str = "", content: bytes = b"", payload: dict | None = None):
        self.url = url
        self.text = text
        self.content = content
        self._payload = payload if payload is not None else {}

    def json(self) -> dict:
        return self._payload


def test_ocr_singleton_and_bytes() -> None:
    """OCR 模型只创建一次, 验证码图片以 bytes 传入."""
    created: list[int] = []
    seen: list[bytes] = []

    class FakeOcr:
        def __init__(self, *args, **kwargs):
            created.append(1)

        def classification(self, img):
            seen.append(img)
            return "ab12"

    class Session:
        def get(self, *args, **kwargs):
            return _Response("https://idm.swu.edu.cn/am/validate.code", content=b"img-bytes")

    original_cls = get_info_mod.ddddocr.DdddOcr
    original_instance = get_info_mod._ocr_instance
    original_sleep = get_info_mod.time.sleep
    get_info_mod.ddddocr.DdddOcr = FakeOcr
    get_info_mod._ocr_instance = None
    get_info_mod.time.sleep = lambda seconds: None
    try:
        first = _get_ocr()
        second = _get_ocr()
        assert first is second
        assert recognize_captcha(Session(), timeout=1, max_attempts=1) == "ab12"
        assert recognize_captcha(Session(), timeout=1, max_attempts=1) == "ab12"
    finally:
        get_info_mod.ddddocr.DdddOcr = original_cls
        get_info_mod._ocr_instance = original_instance
        get_info_mod.time.sleep = original_sleep

    assert created == [1]
    assert seen == [b"img-bytes", b"img-bytes"]
    print("[PASS] OCR 单例, 且直接识别图片 bytes")


def test_beijing_time_across_utc_midnight() -> None:
    """UTC 晚上对应北京时间次日, 签到日期和请假窗口按北京时间."""
    utc_evening = datetime(2026, 10, 4, 18, 0, tzinfo=UTC)
    utc_checkin = datetime(2026, 10, 4, 13, 15, tzinfo=UTC)

    assert _beijing_date_str(utc_evening) == "2026-10-05"
    assert _beijing_date_str(utc_checkin) == "2026-10-04"
    assert _is_on_leave("2026-10-04 18:00", "2026-10-04 23:30", utc_checkin)
    assert not _is_on_leave("2026-10-04 08:00", "2026-10-04 14:00", utc_checkin)
    print("[PASS] 日期和请假窗口使用北京时间")


def test_vacation_and_submit_use_beijing_clock() -> None:
    """请假判断和 tsrq 走同一套北京时间, 响应日志不带整包数据."""
    utc_checkin = datetime(2026, 10, 4, 13, 15, tzinfo=UTC)
    utc_after_midnight = datetime(2026, 10, 4, 18, 0, tzinfo=UTC)
    original_now = check_in_mod._now_beijing

    ctx = CheckinContext()
    ctx.token = "token"
    ctx.transition = {"formId": "form-1", "id": "record-1"}
    ctx.student_id = "20210001"
    ctx.building = "楠园"
    ctx.room = "101"
    ctx.latitude = 29.8
    ctx.longitude = 106.4

    def leave_payload(start: str, end: str) -> dict:
        return {"data": {"records": [{"lcztmc": "已同意", "kssj": start, "jssj": end}]}}

    class LeaveSession:
        def __init__(self, payload: dict):
            self.payload = payload

        def get(self, *args, **kwargs):
            return _Response("https://of.swu.edu.cn/leave", payload=self.payload)

    try:
        check_in_mod._now_beijing = lambda: utc_checkin
        ctx.session = LeaveSession(leave_payload("2026-10-04 18:00", "2026-10-04 23:30"))
        assert _check_vacation_enabled(ctx, 1) is True
        ctx.session = LeaveSession(leave_payload("2026-10-04 08:00", "2026-10-04 14:00"))
        assert _check_vacation_enabled(ctx, 1) is False

        check_in_mod._now_beijing = lambda: utc_after_midnight
        captured: dict = {}

        class SubmitResponse:
            text = '{"xh":"20210001","dorm":"secret-dorm"}'

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"success": True, "msg": "ok", "xh": "20210001", "dorm": "secret-dorm"}

        def post(*args, **kwargs):
            captured["body"] = json.loads(kwargs["data"])
            return SubmitResponse()

        ctx.session = SimpleNamespace(post=post)
        stdout = StringIO()
        original_stdout = sys.stdout
        sys.stdout = stdout
        try:
            assert _submit_checkin(ctx, 1) == 1
        finally:
            sys.stdout = original_stdout
    finally:
        check_in_mod._now_beijing = original_now

    output = stdout.getvalue()
    assert captured["body"]["tsrq"] == "2026-10-05"
    assert "success=True" in output
    assert "msg=ok" in output
    assert "20210001" not in output
    assert "secret-dorm" not in output
    print("[PASS] 请假和签到日期跟随北京时间, 日志只保留 success 与 msg")


def test_outer_retry_skips_login_failure() -> None:
    """外层重试状态 0 和 4, 登录失败不再乘上外层次数."""
    assert RETRYABLE_STATUS == {0, 4}

    original_check_in = check_in_mod.check_in
    original_sleep = check_in_mod.time.sleep
    calls = {"n": 0, "sleeps": []}

    def fake_check_in(username, password, timeout=10):
        calls["n"] += 1
        return calls["status"]

    def fake_sleep(seconds):
        calls["sleeps"].append(seconds)

    check_in_mod.check_in = fake_check_in
    check_in_mod.time.sleep = fake_sleep
    try:
        calls["status"] = 3
        assert check_in_with_retry("user", "pass", max_attempts=3, retry_delay=8) == 3
        assert calls["n"] == 1
        assert calls["sleeps"] == []

        calls["n"] = 0
        calls["sleeps"] = []
        calls["status"] = 0
        assert check_in_with_retry("user", "pass", max_attempts=3, retry_delay=8) == 0
        assert calls["n"] == 3
        assert calls["sleeps"] == [8, 16]

        calls["n"] = 0
        calls["sleeps"] = []
        calls["status"] = 4
        assert check_in_with_retry("user", "pass", max_attempts=3, retry_delay=8) == 4
        assert calls["n"] == 3
    finally:
        check_in_mod.check_in = original_check_in
        check_in_mod.time.sleep = original_sleep

    print("[PASS] 状态 3 不进外层重试, 状态 0 和 4 会重试")


def test_check_in_splits_auth_and_network() -> None:
    """空 token 是登录失败, 网络异常是状态 4."""
    original = check_in_mod.get_token
    try:
        check_in_mod.get_token = lambda *args, **kwargs: ""
        assert check_in("user", "pass") == 3

        def raise_network(*args, **kwargs):
            raise requests.exceptions.ConnectionError("down")

        check_in_mod.get_token = raise_network
        assert check_in("user", "pass") == 4
    finally:
        check_in_mod.get_token = original
    print("[PASS] check_in 把认证失败和网络失败分成状态 3 和 4")


def test_get_token_failure_classes() -> None:
    """纯网络耗尽向外抛, 出现认证失败则返回空 token."""

    class NetworkSession:
        def __init__(self):
            self.cookies = _Cookies()

        def get(self, *args, **kwargs):
            raise requests.exceptions.Timeout("down")

        def post(self, *args, **kwargs):
            raise requests.exceptions.Timeout("down")

    class AuthSession:
        def __init__(self):
            self.cookies = _Cookies()
            self.calls = 0

        def get(self, url, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise requests.exceptions.ConnectionError("down")
            return _Response(url, "<html></html>")

        def post(self, url, **kwargs):
            return _Response(url, "<html></html>")

    original_sleep = get_info_mod.time.sleep
    get_info_mod.time.sleep = lambda seconds: None
    try:
        try:
            _get_token("user", "pass", timeout=1, max_login_attempts=2, session=NetworkSession())
        except requests.exceptions.Timeout:
            pass
        else:
            raise AssertionError("纯网络失败应该抛出 Timeout")

        assert _get_token("user", "pass", timeout=1, max_login_attempts=2, session=AuthSession()) == ""
    finally:
        get_info_mod.time.sleep = original_sleep
    print("[PASS] 登录网络耗尽可重试, 认证耗尽返回空 token")


def test_captcha_error_detection() -> None:
    """验证码错误必须是登录页上的明确文案, 身份选择页不能被当成验证码失败."""
    login_error = SimpleNamespace(
        url="https://idm.swu.edu.cn/am/UI/Login",
        text="<div>验证码错误</div><input name='validateCode'>",
    )
    identity_page = SimpleNamespace(
        url="https://idm.swu.edu.cn/am/UI/Login",
        text="<input name='validateCode'><input name='identityDefault'>验证码",
    )
    login_form = SimpleNamespace(
        url="https://idm.swu.edu.cn/am/UI/Login",
        text="<label>验证码</label><input name='validateCode'>",
    )
    callback = SimpleNamespace(
        url="https://of.swu.edu.cn/cas/oauth/callback?ticket=ST-1",
        text="验证码错误",
    )

    assert is_captcha_error_response(login_error)
    assert not is_captcha_error_response(identity_page)
    assert not is_captcha_error_response(login_form)
    assert not is_captcha_error_response(callback)
    print("[PASS] 验证码失败判断不会误伤身份选择页")


def test_extract_ticket_stops_at_next_param() -> None:
    """ticket 只取到下一个 &, 不把后续查询参数粘进去."""
    assert extract_ticket_from_url("https://of.swu.edu.cn/cb?ticket=ST-ABC&foo=1") == "ST-ABC"
    assert extract_ticket_from_url("https://of.swu.edu.cn/cb?ticket=ST-ABC%2F1&foo=1") == "ST-ABC/1"
    assert extract_ticket_from_url("https://of.swu.edu.cn/cb?foo=1") is None
    assert extract_ticket_from_url("https://of.swu.edu.cn/cb?ticket=&foo=1") is None
    print("[PASS] ticket 在下一个参数处截断")


if __name__ == "__main__":
    test_ocr_singleton_and_bytes()
    test_beijing_time_across_utc_midnight()
    test_vacation_and_submit_use_beijing_clock()
    test_outer_retry_skips_login_failure()
    test_check_in_splits_auth_and_network()
    test_get_token_failure_classes()
    test_captcha_error_detection()
    test_extract_ticket_stops_at_next_param()
    print("[SUCCESS] 签到流程测试通过")
