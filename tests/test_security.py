"""
安全性测试: 确保敏感信息不会泄露到日志
"""
import importlib
import os
import sys
from io import StringIO

# 确保 SWU_DEBUG_CREDENTIALS / SWUDK_DEBUG_CREDENTIALS 未设置 (模拟生产环境)
os.environ.pop("SWU_DEBUG_CREDENTIALS", None)
os.environ.pop("SWUDK_DEBUG_CREDENTIALS", None)


def test_no_token_in_normal_output():
    """测试: 正常模式下不输出 token"""
    from swu_checkin.get_info import safe_print

    captured_output = StringIO()
    sys.stdout = captured_output

    safe_print("获取到 token: abc123xyz", ["token"])
    safe_print("这是普通日志")

    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()

    assert "token" not in output.lower()
    assert "abc123xyz" not in output
    assert "普通日志" in output
    print("[PASS] 测试通过: 正常模式下不输出包含 token 的日志")


def test_mask_sensitive_data():
    """测试: 敏感数据脱敏功能"""
    from swu_checkin.get_info import mask_sensitive_data

    token = "abcdefghijklmnopqrstuvwxyz123456"
    masked = mask_sensitive_data(token, show_chars=4)
    assert masked.startswith("ab")
    assert masked.endswith("56")
    assert "*" in masked
    assert "cdefghijklmnopqrstuvwxyz1234" not in masked
    print(f"[PASS] 长字符串脱敏: {token} -> {masked}")

    short_token = "abc"
    masked_short = mask_sensitive_data(short_token, show_chars=4)
    assert masked_short == "****"
    print(f"[PASS] 短字符串脱敏: {short_token} -> {masked_short}")

    empty = ""
    masked_empty = mask_sensitive_data(empty)
    assert masked_empty == "****"
    print(f"[PASS] 空字符串脱敏: (空) -> {masked_empty}")

    jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
    masked_jwt = mask_sensitive_data(jwt_token, show_chars=8)
    assert masked_jwt.startswith("eyJh")
    assert masked_jwt.endswith("IyfQ")
    assert "*" in masked_jwt
    assert "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4" not in masked_jwt
    print(f"[PASS] JWT token 脱敏: {jwt_token[:20]}... -> {masked_jwt[:20]}...")


def test_debug_mode_behavior():
    """测试: 非调试模式下 debug_print 不输出"""
    from swu_checkin.get_info import debug_print

    captured_output = StringIO()
    sys.stdout = captured_output

    debug_print("这是调试信息")

    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()

    assert output == ""
    print("[PASS] 测试通过: 非调试模式下 debug_print 不输出")


def test_debug_mode_enabled_swu():
    """测试: 启用 SWU_DEBUG_CREDENTIALS 调试模式后的行为"""
    os.environ["SWU_DEBUG_CREDENTIALS"] = "1"
    import swu_checkin.get_info
    importlib.reload(swu_checkin.get_info)
    from swu_checkin.get_info import debug_print

    captured_output = StringIO()
    sys.stdout = captured_output

    debug_print("调试信息: token=abc123")

    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()

    assert "[DEBUG]" in output
    assert "token=abc123" in output
    print("[PASS] 测试通过: SWU_DEBUG_CREDENTIALS 模式下 debug_print 正常输出")

    os.environ.pop("SWU_DEBUG_CREDENTIALS", None)
    importlib.reload(swu_checkin.get_info)


def test_debug_mode_enabled_swudk():
    """测试: 兼容旧环境变量 SWUDK_DEBUG_CREDENTIALS 行为"""
    os.environ["SWUDK_DEBUG_CREDENTIALS"] = "1"
    import swu_checkin.get_info
    importlib.reload(swu_checkin.get_info)
    from swu_checkin.get_info import debug_print

    captured_output = StringIO()
    sys.stdout = captured_output

    debug_print("调试信息: token=abc123")

    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()

    assert "[DEBUG]" in output
    assert "token=abc123" in output
    print("[PASS] 测试通过: SWUDK_DEBUG_CREDENTIALS 兼容模式下 debug_print 正常输出")

    os.environ.pop("SWUDK_DEBUG_CREDENTIALS", None)
    importlib.reload(swu_checkin.get_info)


def test_github_actions_safety():
    """测试: 模拟 GitHub Actions 环境, 确保不泄露敏感信息"""
    os.environ.pop("SWU_DEBUG_CREDENTIALS", None)
    os.environ.pop("SWUDK_DEBUG_CREDENTIALS", None)

    from swu_checkin.get_info import mask_sensitive_data, safe_print

    captured_output = StringIO()
    sys.stdout = captured_output

    fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
    fake_username = "20211234567"

    safe_print(f"用户: {mask_sensitive_data(fake_username, 4)}", [])
    safe_print(f"获取 token: {fake_token}", ["token"])
    safe_print("签到任务获取成功", [])

    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()

    assert "20**567" in output or "****" in output
    assert fake_token not in output
    assert "签到任务获取成功" in output

    print("[PASS] 测试通过: GitHub Actions 环境下不泄露敏感信息")


if __name__ == "__main__":
    print("=" * 60)
    print("开始安全性测试")
    print("=" * 60)
    print()

    test_mask_sensitive_data()
    print()

    test_no_token_in_normal_output()
    print()

    test_debug_mode_behavior()
    print()

    test_debug_mode_enabled_swu()
    print()

    test_debug_mode_enabled_swudk()
    print()

    test_github_actions_safety()
    print()

    print("=" * 60)
    print("[SUCCESS] 所有安全性测试通过")
    print("=" * 60)
