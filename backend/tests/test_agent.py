"""Agent 模块测试

测试面试规则引擎。
"""

import pytest

from app.agent.nodes import question as question_node
from app.agent.nodes.question import generate_question, generate_question_stream
from app.agent.rules import DEFAULT_RULES, InterviewRules, should_force_switch


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


class TestGenerateQuestion:
    """追问生成测试"""

    @pytest.mark.asyncio
    async def test_generate_question_falls_back_when_llm_returns_process_text(self, monkeypatch):
        """LLM 只返回过程说明而不是问题时，降级到模板问题。"""
        doubt_point = {
            "id": "p1",
            "source_text": "简历智诊 Agent",
            "reason": "需要核实项目细节",
            "probe_questions": ["你在简历智诊 Agent 中具体负责哪个模块？"],
        }
        monkeypatch.setattr(question_node, "is_llm_available", lambda: True)
        monkeypatch.setattr(
            question_node,
            "_llm_generate_question",
            lambda *args, **kwargs: "我先查看一下简历中这个项目的具体细节，以及候选人的工作经历，以便提出有针对性的问题。",
        )

        result = await generate_question({
            "doubt_points": [doubt_point],
            "current_point_index": 0,
            "current_round": 1,
            "messages": [],
            "resume_data": {},
        })

        assert result["current_question"] == "你在简历智诊 Agent 中具体负责哪个模块？"

    def test_generate_question_stream_falls_back_when_llm_returns_process_text(self, monkeypatch):
        """流式生成只返回过程说明时，也降级到模板问题。"""
        doubt_point = {
            "id": "p1",
            "source_text": "简历智诊 Agent",
            "reason": "需要核实项目细节",
            "probe_questions": ["你在简历智诊 Agent 中具体负责哪个模块？"],
        }
        monkeypatch.setattr(question_node, "is_llm_available", lambda: True)
        monkeypatch.setattr(
            question_node,
            "call_llm_stream",
            lambda *args, **kwargs: iter(["我先查看一下简历中这个项目的具体细节，", "以及候选人的工作经历。"]),
        )

        assert "".join(generate_question_stream(doubt_point, [], 1)) == "你在简历智诊 Agent 中具体负责哪个模块？"
