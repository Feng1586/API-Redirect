"""
验证器（邮箱格式、密码强度）
"""

import re


def validate_email(email: str) -> bool:
    """
    验证邮箱格式
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    验证密码强度
    要求: 数字、大写字母、小写字母、特殊字符至少包含3种
    要求: 长度 >= 8
    返回: (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "密码长度至少8位"

    categories = 0
    if re.search(r"\d", password):
        categories += 1
    if re.search(r"[A-Z]", password):
        categories += 1
    if re.search(r"[a-z]", password):
        categories += 1
    if re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password):
        categories += 1

    if categories < 3:
        return False, "密码需包含至少3种字符类型（数字、大写字母、小写字母、特殊字符）"

    return True, ""


def validate_username(username: str) -> tuple[bool, str]:
    """
    验证用户名 (字母开头, 字母数字下划线, 4-20位)
    """
    if len(username) < 4 or len(username) > 20:
        return False, "用户名长度需在4-20位之间"

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", username):
        return False, "用户名需以字母开头，只能包含字母、数字、下划线"

    return True, ""
