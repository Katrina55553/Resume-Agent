"""Agent 节点测试

覆盖 collect_answer / evaluate_answer / generate_report 三个节点。
LLM 调用全部 mock，验证规则降级路径和决策逻辑。
"""

from unittest.mock import patch

import pytest

from app.agent.nodes.collect import collect_answer
from app.agent.nodes.evaluate import (
    _parse_evaluation,
    _rule_score_answer,
    evaluate_answer,
)
from app.agent.nodes.report import (
    _compute_overall_score,
    _extract_point_feedback,
    _rule_generate_report,
    generate_report,
)

# ============================================================
# collect_answer
# ============================================================


class TestCollectAnswer:
    """回答收集节点"""

    @pytest.mark.asyncio
    async def test_appends_user_message(self):
        result = await collect_answer({
            "current_answer": "我用 FastAPI 实现了 RESTful 接口",
            "doubt_points": [{"id": "p1"}],
            "current_point_index": 0,
            "current_round": 1,
        })

        assert "messages" in result
        assert len(result["messages"]) == 1
        msg = result["messages"][0]
        assert msg["role"] == "user"
        assert msg["content"] == "我用 FastAPI 实现了 RESTful 接口"
        assert msg["point_id"] == "p1"

    @pytest.mark.asyncio
    async def test_marks_short_answer(self):
        """回答过短应标记 answer_too_short"""
        result = await collect_answer({
            "current_answer": "是的",  # 远小于 MIN_ANSWER_LENGTH=50
            "doubt_points": [{"id": "p1"}],
            "current_point_index": 0,
            "current_round": 1,
        })

        assert result.get("answer_too_short") is True

    @pytest.mark.asyncio
    async def test_does_not_mark_long_answer(self):
        """足够长的回答不应被标记"""
        long_answer = "我使用 FastAPI 搭建了后端服务，包含用户认证、文件上传、WebSocket 面试等模块。" * 2
        result = await collect_answer({
            "current_answer": long_answer,
            "doubt_points": [{"id": "p1"}],
            "current_point_index": 0,
            "current_round": 1,
        })

        assert "answer_too_short" not in result

    @pytest.mark.asyncio
    async def test_handles_empty_doubt_points(self):
        """doubt_points 为空时 point_id 应为空字符串"""
        result = await collect_answer({
            "current_answer": "回答内容",
            "doubt_points": [],
            "current_point_index": 0,
            "current_round": 1,
        })
        assert result["messages"][0]["point_id"] == ""

    @pytest.mark.asyncio
    async def test_handles_out_of_range_index(self):
        """point_index 越界时 point_id 应为空字符串"""
        result = await collect_answer({
            "current_answer": "回答",
            "doubt_points": [{"id": "p1"}],
            "current_point_index": 99,
            "current_round": 1,
        })
        assert result["messages"][0]["point_id"] == ""

    @pytest.mark.asyncio
    async def test_handles_missing_answer(self):
        """current_answer 缺失时按空字符串处理"""
        result = await collect_answer({
            "doubt_points": [{"id": "p1"}],
            "current_point_index": 0,
            "current_round": 1,
        })
        assert result["messages"][0]["content"] == ""
        # 空回答应被标记为过短
        assert result.get("answer_too_short") is True


# ============================================================
# _rule_score_answer
# ============================================================


class TestRuleScoreAnswer:
    """规则评分（降级方案）"""

    def test_short_answer_low_score(self):
        """过短回答（< 50 字符）得分较低"""
        score, feedback = _rule_score_answer("是的", current_round=1)
        assert score <= 50
        assert "简略" in feedback

    def test_medium_answer_medium_score(self):
        """中等长度回答（50-200 字符）"""
        answer = "我使用 FastAPI 搭建了后端服务，包含用户认证、文件上传等模块。"  # ~30 chars
        # 拼接到 50-200 之间
        answer = answer * 3
        score, feedback = _rule_score_answer(answer, current_round=1)
        assert 50 < score <= 80
        assert "清楚" in feedback or "补充" in feedback

    def test_long_answer_high_score(self):
        """长回答（>= 200 字符）得分较高"""
        answer = "我使用 FastAPI 搭建了后端服务，包含用户认证、文件上传、WebSocket 面试等模块。" * 5
        score, feedback = _rule_score_answer(answer, current_round=1)
        assert score >= 70
        assert "详细" in feedback or "清晰" in feedback

    def test_round_bonus_increases_score(self):
        """轮次越多，奖励越高（但不超过 100）"""
        short_answer = "ok"
        score_r1, _ = _rule_score_answer(short_answer, current_round=1)
        score_r3, _ = _rule_score_answer(short_answer, current_round=3)
        assert score_r3 >= score_r1

    def test_score_capped_at_100(self):
        """得分不超过 100"""
        long_answer = "x" * 500
        score, _ = _rule_score_answer(long_answer, current_round=10)
        assert score <= 100


# ============================================================
# _parse_evaluation
# ============================================================


class TestParseEvaluation:
    """LLM 评估结果解析"""

    def test_parses_valid_json(self):
        text = '{"score": 85, "feedback": "回答良好", "credible": true}'
        result = _parse_evaluation(text)
        assert result["score"] == 85
        assert result["feedback"] == "回答良好"

    def test_extracts_json_from_text(self):
        """从包含其他文本的内容中提取 JSON"""
        text = '评估结果如下：\n{"score": 70, "feedback": "一般"}\n以上是评估。'
        result = _parse_evaluation(text)
        assert result["score"] == 70

    def test_returns_none_for_invalid_json(self):
        assert _parse_evaluation("not a json at all") is None

    def test_returns_none_for_empty_text(self):
        assert _parse_evaluation("") is None


# ============================================================
# evaluate_answer
# ============================================================


class TestEvaluateAnswer:
    """评估决策节点"""

    @pytest.mark.asyncio
    async def test_follow_up_when_score_low(self):
        """低分应触发 follow_up 决策"""
        with patch("app.agent.nodes.evaluate.is_llm_available", return_value=False):
            result = await evaluate_answer({
                "current_answer": "是的",  # 过短
                "current_round": 1,
                "current_point_index": 0,
                "doubt_points": [{"id": "p1"}],
                "point_states": {},
                "answer_too_short": True,
                "messages": [{"role": "assistant", "content": "Q1"}],
            })

        assert result["decision"] == "follow_up"
        assert result["current_round"] == 2
        assert result["current_evaluation"]["score"] <= 40  # 过短被压低

    @pytest.mark.asyncio
    async def test_next_point_when_score_high(self):
        """高分应切换到下一个存疑点"""
        long_answer = "我使用 FastAPI 搭建了后端服务，包含用户认证、文件上传、WebSocket 面试等模块。" * 5
        with patch("app.agent.nodes.evaluate.is_llm_available", return_value=False):
            result = await evaluate_answer({
                "current_answer": long_answer,
                "current_round": 1,
                "current_point_index": 0,
                "doubt_points": [
                    {"id": "p1"},
                    {"id": "p2"},
                ],
                "point_states": {},
                "messages": [{"role": "assistant", "content": "Q1"}],
            })

        assert result["decision"] == "next_point"
        assert result["current_point_index"] == 1
        assert result["current_round"] == 1
        # 当前点应标记为 resolved
        assert result["point_states"]["p1"] == "resolved"
        # 下一个点应标记为 active
        assert result["point_states"]["p2"] == "active"

    @pytest.mark.asyncio
    async def test_report_when_last_point_resolved(self):
        """最后一个存疑点解决后应生成报告"""
        long_answer = "我使用 FastAPI 搭建了后端服务，包含用户认证、文件上传、WebSocket 面试等模块。" * 5
        with patch("app.agent.nodes.evaluate.is_llm_available", return_value=False):
            result = await evaluate_answer({
                "current_answer": long_answer,
                "current_round": 1,
                "current_point_index": 0,
                "doubt_points": [{"id": "p1"}],  # 只有一个存疑点
                "point_states": {},
                "messages": [{"role": "assistant", "content": "Q1"}],
            })

        assert result["decision"] == "report"
        assert result["is_completed"] is True
        assert result["point_states"]["p1"] == "resolved"

    @pytest.mark.asyncio
    async def test_force_report_when_round_exceeds_max(self):
        """追问轮次达到上限应切换存疑点"""
        with patch("app.agent.nodes.evaluate.is_llm_available", return_value=False):
            result = await evaluate_answer({
                "current_answer": "是的",
                "current_round": 3,  # MAX_FOLLOW_UP=3
                "current_point_index": 0,
                "doubt_points": [{"id": "p1"}, {"id": "p2"}],
                "point_states": {},
                "answer_too_short": True,
                "messages": [{"role": "assistant", "content": "Q1"}],
            })

        # 轮次达到上限 → 切换存疑点
        assert result["decision"] == "next_point"
        assert result["point_states"]["p1"] == "resolved"

    @pytest.mark.asyncio
    async def test_llm_uncredible_caps_score(self):
        """LLM 判定不可信时分数被压低"""
        with (
            patch("app.agent.nodes.evaluate.is_llm_available", return_value=True),
            patch("app.agent.nodes.evaluate._llm_evaluate_answer", return_value={
                "score": 80,
                "feedback": "回答不可信",
                "credible": False,
            }),
        ):
            long_answer = "我使用 FastAPI 搭建了后端服务，包含用户认证、文件上传、WebSocket 面试等模块。" * 5
            result = await evaluate_answer({
                "current_answer": long_answer,
                "current_round": 1,
                "current_point_index": 0,
                "doubt_points": [{"id": "p1"}, {"id": "p2"}],
                "point_states": {},
                "messages": [{"role": "assistant", "content": "Q1"}],
            })

        # 不可信 → 分数被压到 <= 45 → follow_up
        assert result["current_evaluation"]["score"] <= 45
        assert result["decision"] == "follow_up"


# ============================================================
# _compute_overall_score
# ============================================================


class TestComputeOverallScore:
    """综合得分计算"""

    def test_returns_zero_for_empty_list(self):
        assert _compute_overall_score([]) == 0

    def test_returns_single_score(self):
        assert _compute_overall_score([{"score": 75}]) == 75

    def test_returns_average(self):
        result = _compute_overall_score([{"score": 60}, {"score": 80}])
        assert result == 70

    def test_handles_missing_score_field(self):
        """缺失 score 字段按 0 处理"""
        result = _compute_overall_score([{}, {"score": 100}])
        assert result == 50


# ============================================================
# _extract_point_feedback
# ============================================================


class TestExtractPointFeedback:
    """逐点反馈生成"""

    def test_skipped_point_feedback(self):
        doubt_points = [{"id": "p1", "source_text": "项目经历"}]
        result = _extract_point_feedback(doubt_points, {"p1": "skipped"}, [])
        assert len(result) == 1
        assert result[0]["state"] == "skipped"
        assert "跳过" in result[0]["feedback"]

    def test_high_score_feedback(self):
        doubt_points = [{"id": "p1", "source_text": "x"}]
        evaluations = [{"point_index": 0, "score": 85}]
        result = _extract_point_feedback(doubt_points, {"p1": "resolved"}, evaluations)
        assert "已消除" in result[0]["feedback"]

    def test_medium_score_feedback(self):
        doubt_points = [{"id": "p1", "source_text": "x"}]
        evaluations = [{"point_index": 0, "score": 60}]
        result = _extract_point_feedback(doubt_points, {"p1": "resolved"}, evaluations)
        assert "补充" in result[0]["feedback"]

    def test_low_score_feedback(self):
        doubt_points = [{"id": "p1", "source_text": "x"}]
        evaluations = [{"point_index": 0, "score": 30}]
        result = _extract_point_feedback(doubt_points, {"p1": "resolved"}, evaluations)
        assert "未能" in result[0]["feedback"] or "修改" in result[0]["feedback"]

    def test_uses_default_id_when_missing(self):
        """存疑点没有 id 字段时使用 point_{index}"""
        doubt_points = [{"source_text": "x"}]
        result = _extract_point_feedback(doubt_points, {}, [])
        assert result[0]["point_id"] == "point_0"


# ============================================================
# _rule_generate_report
# ============================================================


class TestRuleGenerateReport:
    """规则报告生成（降级方案）"""

    def test_generates_complete_report(self):
        state = {
            "doubt_points": [
                {"id": "p1", "source_text": "项目1"},
                {"id": "p2", "source_text": "项目2"},
            ],
            "point_states": {"p1": "resolved", "p2": "skipped"},
            "evaluations": [
                {"point_index": 0, "score": 80},
                {"point_index": 1, "score": 30},
            ],
        }
        report = _rule_generate_report(state)

        assert report["total_points"] == 2
        assert report["resolved_points"] == 1
        assert report["skipped_points"] == 1
        assert report["overall_score"] == 55  # (80 + 30) / 2
        assert len(report["point_feedbacks"]) == 2
        assert len(report["suggestions"]) >= 1
        assert "综合得分" in report["summary"]

    def test_handles_empty_state(self):
        """空状态应返回零值报告"""
        report = _rule_generate_report({})
        assert report["total_points"] == 0
        assert report["overall_score"] == 0
        assert report["resolved_points"] == 0

    def test_suggestions_include_weak_points(self):
        """弱项应触发改进建议"""
        state = {
            "doubt_points": [{"id": "p1", "source_text": "x"}],
            "point_states": {"p1": "resolved"},
            "evaluations": [{"point_index": 0, "score": 40}],
        }
        report = _rule_generate_report(state)
        joined = " ".join(report["suggestions"])
        assert "完善" in joined or "薄弱" in joined

    def test_high_overall_score_adds_positive_suggestion(self):
        state = {
            "doubt_points": [{"id": "p1", "source_text": "x"}],
            "point_states": {"p1": "resolved"},
            "evaluations": [{"point_index": 0, "score": 90}],
        }
        report = _rule_generate_report(state)
        joined = " ".join(report["suggestions"])
        assert "优秀" in joined


# ============================================================
# generate_report (节点函数)
# ============================================================


class TestGenerateReportNode:
    """报告生成节点"""

    @pytest.mark.asyncio
    async def test_falls_back_to_rule_when_llm_unavailable(self):
        """LLM 不可用时应降级到规则报告"""
        with patch("app.agent.nodes.report.is_llm_available", return_value=False):
            result = await generate_report({
                "doubt_points": [{"id": "p1", "source_text": "x"}],
                "point_states": {"p1": "resolved"},
                "evaluations": [{"point_index": 0, "score": 80}],
            })

        assert "report" in result
        assert result["is_completed"] is True
        assert result["report"]["total_points"] == 1

    @pytest.mark.asyncio
    async def test_uses_llm_report_when_available(self):
        """LLM 可用时应使用 LLM 生成的报告"""
        llm_report = {
            "overall_score": 88,
            "total_points": 1,
            "resolved_points": 1,
            "skipped_points": 0,
            "point_feedbacks": [],
            "suggestions": ["LLM 建议"],
            "summary": "LLM 摘要",
        }
        with (
            patch("app.agent.nodes.report.is_llm_available", return_value=True),
            patch("app.agent.nodes.report._llm_generate_report", return_value=llm_report),
        ):
            result = await generate_report({
                "doubt_points": [{"id": "p1"}],
                "point_states": {},
                "evaluations": [],
            })

        assert result["report"]["overall_score"] == 88
        assert result["report"]["suggestions"] == ["LLM 建议"]

    @pytest.mark.asyncio
    async def test_falls_back_on_llm_timeout(self):
        """LLM 超时应降级到规则报告"""
        with (
            patch("app.agent.nodes.report.is_llm_available", return_value=True),
            patch("app.agent.nodes.report._llm_generate_report", side_effect=TimeoutError()),
        ):
            result = await generate_report({
                "doubt_points": [{"id": "p1", "source_text": "x"}],
                "point_states": {},
                "evaluations": [],
            })

        # 降级到规则报告
        assert "report" in result
        assert result["is_completed"] is True

    @pytest.mark.asyncio
    async def test_falls_back_on_llm_exception(self):
        """LLM 异常应降级到规则报告"""
        with (
            patch("app.agent.nodes.report.is_llm_available", return_value=True),
            patch("app.agent.nodes.report._llm_generate_report", side_effect=RuntimeError("boom")),
        ):
            result = await generate_report({
                "doubt_points": [{"id": "p1", "source_text": "x"}],
                "point_states": {},
                "evaluations": [],
            })

        assert "report" in result
        assert result["is_completed"] is True
