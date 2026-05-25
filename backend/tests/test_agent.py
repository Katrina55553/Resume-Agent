"""Agent 模块测试

测试面试规则引擎。
"""

import pytest
from app.agent.rules import InterviewRules, should_force_switch, DEFAULT_RULES


class TestInterviewRules:
    """面试规则测试"""

    def test_default_rules(self):
        """测试默认规则值"""
        assert DEFAULT_RULES.MAX_FOLLOW_UP == 3
        assert DEFAULT_RULES.MAX_ERROR_COUNT == 3
        assert DEFAULT_RULES.LLM_TIMEOUT == 15
        assert DEFAULT_RULES.MAX_TOKENS_PER_SESSION == 50000

    def test_custom_rules(self):
        """测试自定义规则"""
        rules = InterviewRules(MAX_FOLLOW_UP=5)
        assert rules.MAX_FOLLOW_UP == 5
        assert rules.MAX_ERROR_COUNT == 3  # 保持默认值

    def test_rules_immutable(self):
        """测试规则不可变"""
        with pytest.raises(AttributeError):
            DEFAULT_RULES.MAX_FOLLOW_UP = 10


class TestShouldForceSwitch:
    """强制切换测试"""

    def test_follow_up_limit(self):
        """追问次数超限"""
        should_switch, reason = should_force_switch(
            follow_up_count=3,
            error_count=0,
            total_tokens=0,
            question_count=0,
        )
        assert should_switch is True
        assert "追问次数" in reason

    def test_error_limit(self):
        """错误次数超限"""
        should_switch, reason = should_force_switch(
            follow_up_count=0,
            error_count=3,
            total_tokens=0,
            question_count=0,
        )
        assert should_switch is True
        assert "错误次数" in reason

    def test_token_limit(self):
        """Token 数超限"""
        should_switch, reason = should_force_switch(
            follow_up_count=0,
            error_count=0,
            total_tokens=50000,
            question_count=0,
        )
        assert should_switch is True
        assert "Token" in reason

    def test_question_limit(self):
        """问题数超限"""
        should_switch, reason = should_force_switch(
            follow_up_count=0,
            error_count=0,
            total_tokens=0,
            question_count=20,
        )
        assert should_switch is True
        assert "问题数" in reason

    def test_no_limit_exceeded(self):
        """未超限"""
        should_switch, reason = should_force_switch(
            follow_up_count=1,
            error_count=0,
            total_tokens=1000,
            question_count=5,
        )
        assert should_switch is False
        assert reason is None
