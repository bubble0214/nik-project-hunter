"""
Nik Project Hunter — 信号分析服务（第五阶段）

职责：
1. 分析招聘信号 → 判断企业数字化/AI 建设阶段
2. 分析新闻信号 → 判断企业战略方向
3. 分析高管信号 → 判断新项目可能性
4. 分析政策信号 → 判断行业预算方向
"""

import json
from loguru import logger

from app.core.ai_client import ai_client


class SignalAnalyzer:
    """
    信号 AI 分析服务

    对四种信号进行深度分析：
    1. 招聘信号：企业是否准备启动项目
    2. 新闻信号：企业战略方向
    3. 高管信号：新项目可能性
    4. 政策信号：行业预算方向
    """

    async def analyze_signal(self, signal: dict) -> dict:
        """
        分析单个信号

        Args:
            signal: 信号字典（含 signal_type, company_name, title, content）

        Returns:
            分析结果字典
        """
        signal_type = signal.get("signal_type", "unknown")

        if signal_type == "recruitment":
            return await self._analyze_recruitment(signal)
        elif signal_type == "news":
            return await self._analyze_news(signal)
        elif signal_type == "executive":
            return await self._analyze_executive(signal)
        elif signal_type == "policy":
            return await self._analyze_policy(signal)
        else:
            return {
                "summary": "未知信号类型",
                "impact_level": "low",
                "is_project_starter": False,
                "recommended_action": "观察",
                "potential_budget": "",
            }

    async def _analyze_recruitment(self, signal: dict) -> dict:
        """
        分析招聘信号

        判断：
        - 企业是否准备启动项目
        - 企业当前数字化阶段
        - 是否有 AI 战略
        - 是否可能采购系统
        """
        prompt = (
            "你是一个企业级销售分析师。请分析以下招聘信号，判断企业数字化/AI 建设状态。\n\n"
            f"企业: {signal.get('company_name', '未知')}\n"
            f"岗位: {signal.get('title', '未知')}\n"
            f"描述: {signal.get('content', '')[:1500]}\n\n"
            "请分析：\n"
            "1. 该企业是否准备启动数据治理/AI/数字化项目？\n"
            "2. 企业当前处于什么数字化阶段？（早期/建设中/成熟/领先）\n"
            "3. 是否有明确的 AI 战略信号？（是/否？\n"
            "4. 是否可能采购外部系统？\n\n"
            "请以 JSON 格式返回：\n"
            "{\n"
            '  "summary": "分析摘要（50字）",\n'
            '  "digital_stage": "早期/建设中/成熟/领先/未知",\n'
            '  "has_ai_strategy": true/false,\n'
            '  "is_project_starter": true/false,\n'
            '  "project_type": "可能启动的项目类型（数据治理/AI平台/数据资产/数字化/其他）",\n'
            '  "likely_to_buy": true/false,\n'
            '  "impact_level": "high/medium/low/medium/high",\n'
            '  "potential_budget": "预估预算范围（如: 100-500万）",\n'
            '  "recommended_action": "建议行动（立即接触/关注/观察）",\n'
            '  "signal_score": 0-100\n'
            "}\n\n"
            "请确保输出合法 JSON。"
        )

        result = await ai_client.chat(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        try:
            return json.loads(result)
        except json.JSONDecodeError:
            logger.error(f"[信号分析] 招聘信号 LLM 返回非法 JSON")
            return self._default_recruitment_analysis()

    def _default_recruitment_analysis(self) -> dict:
        return {
            "summary": "分析失败",
            "digital_stage": "未知",
            "has_ai_strategy": False,
            "is_project_starter": False,
            "project_type": "未知",
            "likely_to_buy": False,
            "impact_level": "low",
            "potential_budget": "未知",
            "recommended_action": "观察",
            "signal_score": 0,
        }

    async def _analyze_news(self, signal: dict) -> dict:
        """
        分析新闻信号

        判断：
        - 企业战略方向
        - 是否进入 AI 建设期
        - 是否进入数据治理阶段
        """
        prompt = (
            "你是一个企业级销售分析师。请分析以下企业新闻，判断企业数字化/AI 战略方向。\n\n"
            f"企业: {signal.get('company_name', '未知')}\n"
            f"标题: {signal.get('title', '未知')}\n"
            f"内容: {signal.get('content', '')[:2000]}\n\n"
            "请分析：\n"
            "1. 企业当前的核心战略方向是什么？\n"
            "2. 是否进入 AI 建设期？\n"
            "3. 是否进入数据治理/数据资产化阶段？\n"
            "4. 是否涉及信息化升级或系统采购？\n\n"
            "请以 JSON 格式返回：\n"
            "{\n"
            '  "summary": "分析摘要（50字）",\n摘要（50字）",\n'
            '  "strategic_direction": "企业战略方向描述",\n'
            '  "entering_ai_phase": true/false,\n'
            '  "entering_data_governance": true/false,\n'
            '  "entering_digitalization": true/false,\n'
            '  "has_procurement_signal": true/false,\n'
            '  "procurement_type": "可能采购类型（数据平台/AI平台/安全/其他）",\n'
            '  "impact_level": "low/medium/high",\n'
            '  "potential_budget": "预估预算范围",\n'
            '  "recommended_action": "建议行动（立即接触/关注/观察）",\n'
            '  "signal_score": 0-100\n'
            "}\n\n"
            "请确保输出合法 JSON。"
        )

        result = await ai_client.chat(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        try:
            return json.loads(result)
        except json.JSONDecodeError:
            logger.error(f"[信号分析] 新闻信号 LLM 返回非法 JSON")
            return self._default_news_analysis()

    def _default_news_analysis(self) -> dict:
        return {
            "summary": "分析失败",
            "strategic_direction": "未知",
            "entering_ai_phase": False,
            "entering_data_governance": False,
            "entering_digitalization": False,
            "has_procurement_signal": False,
            "procurement_type": "未知",
            "impact_level": "low",
            "potential_budget": "未知",
            "recommended_action": "观察",
            "signal_score": 0,
        }

    async def _analyze_executive(self, signal: dict) -> dict:
        """
        分析高管变动信号

        判断：
        - 是否意味着新项目
        - 是否意味着组织调整
        - 是否意味着新预算
        """
        prompt = (
            "你是一个企业级销售分析师。请分析以下高管变动新闻。\n\n"
            f"企业: {signal.get('company_name', '未知')}\n"
            f"标题: {signal.get('title', '未知')}\n"
            f"内容: {signal.get('content', '')[:1500]}\n\n"
            "请分析：\n"
            "1. 该高管变动是否意味着新项目即将启动？\n"
            "2. 是否意味着组织架构调整？\n"
            "3. 是否意味着新预算或新业务方向？\n"
            "4. 如果是 CIO/CDO/数据负责人变动，是否意味着数据/AI 投入增加？\n\n"
            "请以 JSON 格式返回：\n"
            "{\n"
            '  "summary": "分析摘要（50字）",\n'
            '  "implies_new_project": true/false,\n'
            '  "project_type": "可能的新项目类型",\n'
            '  "implies_org_change": true/false,\n'
            '  "implies_new_budget": true/false,\n'
            '  "estimated_budget_range": "预估预算范围",\n'
            '  "urgency_level": "low/medium/high",\n'
            '  "impact_level": "low/medium/high",\n'
            '  "recommended_action": "建议行动（立即接触/关注/观察）",\n'
            '  "signal_score": 0-100\n'
            "}\n\n"
            "请确保输出合法 JSON。"
        )

        result = await ai_client.chat(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        try:
            return json.loads(result)
        except json.JSONDecodeError:
            logger.error(f"[信号分析] 高管信号 LLM 返回非法 JSON")
            return self._default_executive_analysis()

    def _default_executive_analysis(self) -> dict:
        return {
            "summary": "分析失败",
            "implies_new_project": False,
            "project_type": "未知",
            "implies_org_change": False,
            "implies_new_budget": False,
            "estimated_budget_range": "未知",
            "urgency_level": "low",
            "impact_level": "low",
            "recommended_action": "观察",
            "signal_score": 0,
        }

    async def _analyze_policy(self, signal: dict) -> dict:
        """
        分析政策信号

        判断：
        - 哪些行业会新增预算
        - 哪些方向即将爆发
        - 哪些政策影响最大
        """
        prompt = (
            "你是一个企业级政策分析师，专注于数据要素、AI、数字化领域。\n"
            "请分析以下政策信号对行业的影响。\n\n"
            f"发布机构: {signal.get('company_name', '未知')}\n"
            f"标题: {signal.get('title', '未知')}\n"
            f"内容: {signal.get('content', '')[:2000]}\n\n"
            "请分析：\n"
            "1. 哪些行业会因此新增预算？\n"
            "2. 哪些方向即将迎来爆发？（数据治理/AI/数据资产/安全/数字化）\n"
            "3. 该政策对企业的直接影响是什么？\n"
            "4. 建议我方如何应对？\n\n"
            "请以 JSON 格式返回：\n"
            "{\n"
            '  "summary": "政策分析摘要（50字）",\n'
            '  "affected_industries": ["行业1", "行业2"],\n'
            '  "exploding_direction": ["方向1", "方向2"],\n'
            '  "budget_impact": "预算影响分析",\n'
            '  "impact_level": "low/medium/high",\n'
            '  "recommended_strategy": "建议应对策略",\n'
            '  "urgency": "low/medium/high",\n'
            '  "signal_score": 0-100\n'
            "}\n\n"
            "请确保输出合法 JSON。"
        )

        result = await ai_client.chat(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        try:
            return json.loads(result)
        except json.JSONDecodeError:
            logger.error(f"[信号分析] 政策信号 LLM 返回非法 JSON")
            return self._default_policy_analysis()

    def _default_policy_analysis(self) -> dict:
        return {
            "summary": "分析失败",
            "affected_industries": [],
            "exploding_direction": [],
            "budget_impact": "未知",
            "impact_level": "low",
            "recommended_strategy": "观察",
            "urgency": "low",
            "signal_score": 0,
        }


# 全局单例
signal_analyzer = SignalAnalyzer()