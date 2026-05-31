"""
Nik Project Hunter — 评分服务（第四阶段：商机 Intelligence 复合评分）

职责：
1. S/A/B/C 四级评分
2. 综合 Intelligence 维度评分
3. 战略级项目自动识别
4. 输出多维度评分理由

评分规则（第六版：聚焦数据安全/分类分级）：
- S 级 (85-100): 数据安全/分类分级直接相关 + deadline有效 + 意向采购/供应商征集/招标公示，立即布局
- A 级 (70-84): 数据安全/分类分级相关 + deadline有效，重点跟踪
- B 级 (50-69): 部分相关或deadline未知，保持观察
- C 级 (0-49): 不相关（非数据安全）或deadline已过期，暂不跟进

综合评分维度：
- 数据安全/分类分级相关度（50%）
- 项目阶段优先级（20%）
- 时效性（15%）
- 预算规模（10%）
- 客户行业价值（5%）
"""

import json
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project
from app.core.ai_client import ai_client


class ScoreGrade:
    """评分等级常量"""
    S = "S"       # 极高价值 (85-100)
    A = "A"       # 高价值 (70-84)
    B = "B"       # 中等价值 (50-69)
    C = "C"       # 低价值 (0-49)

    @staticmethod
    def from_score(score: int) -> str:
        if score >= 85:
            return ScoreGrade.S
        elif score >= 70:
            return ScoreGrade.A
        elif score >= 50:
            return ScoreGrade.B
        else:
            return ScoreGrade.C

    @staticmethod
    def should_notify(score: int) -> bool:
        """现阶段：所有项目都推送通知"""
        return True


class ScorerService:
    """项目商机评分服务（第四阶段）"""

    LOG_FILE = "logs/scorer.log"

    async def score_project(
        self,
        project: Project,
        session: AsyncSession,
        analysis: dict = None,
    ) -> dict:
        """
        对单个项目进行复合 Intelligence 评分

        Args:
            project: 项目 ORM 对象
            session: 数据库会话
            analysis: 已有的分析结果（可选）

        Returns:
            评分结果字典（含 Intelligence 维度评分）
        """
        logger.info(f"[Scorer] 开始评分项目: {project.title[:60]}...")

        if analysis is None:
            analysis = project.analysis or {}

        intelligence = analysis.get("opportunity_intelligence", {})

        # 准备评分数据（含 Intelligence 维度）
        project_data = {
            "title": project.title,
            "buyer": project.buyer or "未知",
            "budget": project.budget or "未知",
            "region": project.region or "未知",
            "source": project.source,
            "project_type": analysis.get("project_type", "未知"),
            "industry_type": analysis.get("industry_type", "未知"),
            "is_data_governance": analysis.get("is_data_governance", False),
            "is_data_asset": analysis.get("is_data_asset", False),
            "is_ai_project": analysis.get("is_ai_project", False),
            "is_long_track": analysis.get("is_long_track", False),
            "target_department": analysis.get("target_department", "未知"),
            "business_value": analysis.get("business_value", ""),
            "risk_analysis": analysis.get("risk_analysis", ""),
            # Intelligence 维度
            "customer_maturity_score": intelligence.get("customer_maturity_score", 50),
            "long_term_value_score": intelligence.get("long_term_value_score", 50),
            "industry_value_score": intelligence.get("industry_value_score", 50),
            "bidding_probability_score": intelligence.get("bidding_probability_score", 50),
            "business_difficulty_score": intelligence.get("business_difficulty_score", 50),
            "project_continuity_analysis": intelligence.get("project_continuity_analysis", ""),
            "opportunity_level": intelligence.get("opportunity_level", "normal"),
            # 第六阶段：项目阶段与时效性
            "notice_type": getattr(project, "notice_type", None) or "未知",
            "deadline": str(getattr(project, "deadline", "") or ""),
        }

        # 调用 LLM 复合评分
        score_result = await self._call_llm_composite_score(project_data)

        if "error" not in score_result:
            score = score_result.get("score", 0)
            grade = ScoreGrade.from_score(score)

            # 更新项目评分字段
            project.score = score
            project.score_grade = grade
            project.score_reason = json.dumps(
                {
                    "grade": grade,
                    "reason": score_result.get("reason", ""),
                    "worth_following": score_result.get("worth_following", ""),
                    "key_track": score_result.get("key_track", False),
                    "dimensions": score_result.get("dimensions", {}),
                    "intelligence_dimensions": score_result.get("intelligence_dimensions", {}),
                },
                ensure_ascii=False,
            )
            project.status = "scored"

            logger.info(
                f"[Scorer] 项目评分完成: {project.title[:50]} | "
                f"评分={score} | 等级={grade} | "
                f"重点跟踪={'是' if score_result.get('key_track', False) else '否'}"
            )
        else:
            logger.error(f"[Scorer] 项目评分失败: {score_result.get('error')}")

        return score_result

    async def _call_llm_composite_score(self, project_data: dict) -> dict:
        """
        调用 LLM 进行商机评分（第六版：聚焦数据安全/分类分级）

        权重体系：
        - 数据安全/分类分级相关度：50%（首要条件）
        - 项目阶段优先级：20%（意向采购 > 供应商征集 > 招标公示 > 废标公告 > 中标公告 > 招标公告）
        - 时效性：15%（deadline 必须在当前日期之后才有意义）
        - 预算规模：10%
        - 客户行业价值：5%
        """
        prompt = (
            "你是一个企业级销售评分专家，服务于一家专注于**数据安全、数据分类分级、数据治理**领域的科技公司。\n"
            "请对以下招投标项目进行**商机评分**。\n\n"
            "=== 项目信息 ===\n"
            f"- 标题: {project_data.get('title', '未知')}\n"
            f"- 采购单位: {project_data.get('buyer', '未知')}\n"
            f"- 预算: {project_data.get('budget', '未知')} 元\n"
            f"- 地区: {project_data.get('region', '未知')}\n"
            f"- 来源: {project_data.get('source', '未知')}\n"
            f"- 项目类型: {project_data.get('project_type', '未知')}\n"
            f"- 行业: {project_data.get('industry_type', '未知')}\n"
            f"- 数据治理: {'是' if project_data.get('is_data_governance') else '否'}\n"
            f"- 数据资产: {'是' if project_data.get('is_data_asset') else '否'}\n"
            f"- AI 相关: {'是' if project_data.get('is_ai_project') else '否'}\n"
            f"- 长期跟踪: {'是' if project_data.get('is_long_track') else '否'}\n"
            f"- 推荐部门: {project_data.get('target_department', '未知')}\n"
            f"- 商机价值: {project_data.get('business_value', '')}\n"
            f"- 风险分析: {project_data.get('risk_analysis', '')}\n\n"
            "=== 项目阶段与时效性 ===\n"
            f"- 公告类型: {project_data.get('notice_type', '未知')}\n"
            f"- 截标/截止日期: {project_data.get('deadline', '未知')}\n"
            f"- 当前日期: 2026-05-26\n\n"
            "=== 评分标准 ===\n"
            "\n"
            "**第一权重（50%）：数据安全/分类分级相关度**\n"
            "检查项目标题和内容是否与以下业务直接相关：\n"
            "- 数据分类分级系统/服务\n"
            "- 数据安全风险评估\n"
            "- 数据安全建设/防护/治理\n"
            "- 数据资产探查/盘点/分级\n"
            "- 数据安全运营/管控平台\n"
            "- 数据脱敏/水印/审计\n"
            "如果项目与此无关（如通用IT运维、网络安全而非数据安全等），直接评为C级。\n"
            "\n"
            "**第二权重（20%）：项目阶段优先级**\n"
            "按公告类型评分：\n"
            "- 意向采购：95-100（最优先，提前布局）\n"
            "- 供应商征集：85-95（次优先）\n"
            "- 招标公示：70-80（公示中可提前准备）\n"
            "- 废标公告：60-70（说明需求仍在，可能重新招标）\n"
            "- 中标公告：40-50（已定标，仅作市场了解）\n"
            "- 招标公告：30-40（竞争激烈，反应时间短）\n"
            "- 未知：50\n"
            "\n"
            "**第三权重（15%）：时效性**\n"
            "- deadline 有值且 >= 2026-05-26：有效（100分）\n"
            "- deadline 未知：50分（仍需跟进确认）\n"
            "- deadline 已过期：0分（项目已截止，直接降为C级）\n"
            "\n"
            "**第四权重（10%）：预算规模**\n"
            "- >= 500万：高\n"
            "- 100-500万：中\n"
            "- < 100万或未知：低\n"
            "\n"
            "**第五权重（5%）：客户行业价值**\n"
            "- 政府/国企/金融/医疗：高\n"
            "- 其他行业：中\n"
            "\n"
            "=== 等级标准 ===\n"
            "- S 级 (85-100): **数据安全/分类分级直接相关** + deadline有效 + 意向采购/供应商征集/招标公示\n"
            "- A 级 (70-84): 数据安全/分类分级相关 + deadline有效\n"
            "- B 级 (50-69): 部分相关 或 deadline未知\n"
            "- C 级 (0-49): 不相关（非数据安全）或 deadline已过期\n"
            "\n"
            "=== 返回 JSON ===\n"
            "{\n"
            '  "score": 0-100 的整数,\n'
            '  "grade": "S/A/B/C",\n'
            '  "reason": "评分理由（50字，说明与数据安全/分类分级的相关性和阶段优先级）",\n'
            '  "worth_following": "是否值得跟进（50字）",\n'
            '  "key_track": true/false,\n'
            '  "dimensions": {\n'
            '    "relevance_to_data_security": 0-100,\n'
            '    "notice_type_priority": 0-100,\n'
            '    "timeliness": 0-100,\n'
            '    "budget_score": 0-100,\n'
            '    "industry_value": 0-100\n'
            '  }\n'
            "}\n\n"
            "注意：如果项目与数据安全/分类分级无关，score 必须 <= 40（C级）。deadline已过期的项目 score 必须 <= 40（C级）。"
        )

        result = await ai_client.chat(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        try:
            parsed = json.loads(result)
            score = parsed.get("score", 0)
            parsed["grade"] = ScoreGrade.from_score(score)
            return parsed
        except json.JSONDecodeError:
            logger.error(f"[Scorer] LLM 返回非法 JSON: {result[:200]}")
            return {
                "score": 0,
                "grade": "C",
                "reason": "评分失败",
                "worth_following": "评分失败",
                "key_track": False,
                "dimensions": {},
                "intelligence_dimensions": {},
            }

    async def score_analyzed_projects(self, session: AsyncSession) -> list[dict]:
        """评分所有已分析但未评分的项目"""
        result = await session.execute(
            select(Project).where(Project.status == "analyzed")
        )
        projects = result.scalars().all()

        if not projects:
            logger.info("[Scorer] 没有待评分的项目")
            return []

        logger.info(f"[Scorer] 开始评分 {len(projects)} 个已分析项目")

        results = []
        for idx, project in enumerate(projects, 1):
            try:
                score = await self.score_project(project, session)
                results.append(score)
                logger.info(f"[Scorer] 进度 {idx}/{len(projects)}")
            except Exception as e:
                logger.error(f"[Scorer] 项目评分异常: {project.id}: {e}")
                results.append({"error": str(e)})

        logger.info(f"[Scorer] 全部分析完成: {len(results)} 个项目")
        return results


# 全局单例
scorer_service = ScorerService()