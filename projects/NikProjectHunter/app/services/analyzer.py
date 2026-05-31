"""
Nik Project Hunter — AI 分析服务（第四阶段：Opportunity Intelligence Engine）

职责：
1. 10 维基础分析（Phase 3）
2. Opportunity Intelligence Engine（Phase 4 新增）
   - 客户成熟度分析
   - 项目连续性分析
   - 行业价值分析
   - 预算真实性分析
   - 中标概率分析
   - 销售策略建议
3. 更新项目记录的 analysis JSON 和 Intelligence 字段
"""

import json
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project
from app.core.ai_client import ai_client


class AnalyzerService:
    """项目 AI 分析服务（第四阶段）"""

    LOG_FILE = "logs/analyzer.log"

    async def analyze_project(
        self,
        project: Project,
        session: AsyncSession,
    ) -> dict:
        """
        分析单个项目 — 10 维 + Opportunity Intelligence

        Args:
            project: 项目 ORM 对象
            session: 数据库会话

        Returns:
            完整分析结果字典
        """
        logger.info(f"[Analyzer] 开始分析项目: {project.title[:60]}...")

        project_data = {
            "title": project.title,
            "buyer": project.buyer or "未知",
            "budget": project.budget or "未知",
            "region": project.region or "未知",
            "description": project.summary or (
                project.raw_html[:3000] if project.raw_html else "无详细描述"
            ),
            "source": project.source,
        }

        # 调用 LLM 进行完整分析
        analysis = await self._call_llm_full_analysis(project_data)

        if "error" not in analysis:
            # 更新基础分析
            project.summary = analysis.get("summary", "")
            project.analysis = analysis
            project.status = "analyzed"

            # 更新 Opportunity Intelligence 字段
            intelligence = analysis.get("opportunity_intelligence", {})
            project.customer_maturity_score = intelligence.get("customer_maturity_score")
            project.long_term_value_score = intelligence.get("long_term_value_score")
            project.industry_value_score = intelligence.get("industry_value_score")
            project.bidding_probability_score = intelligence.get("bidding_probability_score")
            project.business_difficulty_score = intelligence.get("business_difficulty_score")
            project.opportunity_level = intelligence.get("opportunity_level")

            logger.info(
                f"[Analyzer] 项目分析完成: {project.title[:50]} | "
                f"类型={analysis.get('project_type', 'N/A')} | "
                f"数据治理={analysis.get('is_data_governance', False)} | "
                f"数据资产={analysis.get('is_data_asset', False)} | "
                f"AI项目={analysis.get('is_ai_project', False)} | "
                f"商机级别={intelligence.get('opportunity_level', 'N/A')}"
            )
        else:
            logger.error(f"[Analyzer] 项目分析失败: {analysis.get('error')}")

        return analysis

    async def _call_llm_full_analysis(self, project_data: dict) -> dict:
        """
        调用 LLM 进行完整分析

        输出：
        1. 基础 10 维分析
        2. Opportunity Intelligence（6 维度）
        """
        prompt = (
            "你是一个企业级数据智能和 AI 领域的商机分析师与销售策略顾问。\n"
            "请对以下招投标项目进行深度商业情报分析，返回严格的 JSON 格式。\n\n"
            "项目信息：\n"
            f"- 标题: {project_data.get('title', '未知')}\n"
            f"- 采购单位: {project_data.get('buyer', '未知')}\n"
            f"- 预算: {project_data.get('budget', '未知')} 元\n"
            f"- 地区: {project_data.get('region', '未知')}\n"
            f"- 来源平台: {project_data.get('source', '未知')}\n"
            f"- 描述: {project_data.get('description', '无详细描述')}\n\n"
            "=== 第一部分：基础分析（以下字段必须全部返回）===\n"
            "{\n"
            '  "project_type": "项目类型（如：数据治理平台、数据中台建设、AI知识库等）",\n'
            '  "is_data_governance": true/false,\n'
            '  "is_data_asset": true/false,\n'
            '  "is_ai_project": true/false,\n'
            '  "is_long_track": true/false,\n'
            '  "industry_type": "所属行业（国企/金融/政府/医疗/能源/制造/其他）",\n'
            '  "target_department": "推荐客户部门",\n'
            '  "sales_entry_point": "推荐销售切入点",\n'
            '  "risk_analysis": "风险分析（50字）",\n'
            '  "business_value": "商机价值（50字）",\n'
            '  "summary": "项目摘要（100字）"\n'
            "}\n\n"
            "=== 第二部分：Opportunity Intelligence（以下字段必须全部返回）===\n"
            "{\n"
            '  "opportunity_intelligence": {\n'
            '    "customer_maturity_score": 0-100,\n'
            '    "customer_maturity_analysis": "客户成熟度分析：是否有数字化基础、是否长期预算（50字）",\n'
            '    "long_term_value_score": 0-100,\n'
            '    "project_continuity_analysis": "项目连续性分析：一期/二期/长期、是否追加预算（50字）",\n'
            '    "industry_value_score": 0-100,\n'
            '    "industry_value_analysis": "行业价值分析（30字）",\n'
            '    "budget_authenticity_analysis": "预算真实性分析（30字）",\n'
            '    "bidding_probability_score": 0-100,\n'
            '    "bidding_probability_analysis": "中标概率分析：竞争程度、是否适合中小厂商（50字）",\n'
            '    "business_difficulty_score": 0-100,\n'
            '    "sales_strategy": {\n'
            '      "contact_department": "建议先接触的部门",\n'
            '      "entry_point": "建议切入点",\n'
            '      "main_focus": "主打方向（数据治理/AI/数据资产/安全）",\n'
            '      "approach_type": "销售方式（方案型/关系型/竞争型）"\n'
            '    },\n'
            '    "opportunity_level": "strategic/high_value/normal/low",\n'
            '    "opportunity_reason": "商机级别判断理由（30字）"\n'
            '  }\n'
            "}\n\n"
            "请确保所有字段都有值。布尔字段必须为 true/false。数值字段在 0-100 范围内。"
        )

        result = await ai_client.chat(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=3072,
        )

        try:
            parsed = json.loads(result)
            if "opportunity_intelligence" not in parsed:
                parsed["opportunity_intelligence"] = self._default_intelligence()
            return parsed
        except json.JSONDecodeError:
            logger.error(f"[Analyzer] LLM 返回非法 JSON: {result[:200]}")
            return self._fallback_analysis()

    def _default_intelligence(self) -> dict:
        return {
            "customer_maturity_score": 50,
            "customer_maturity_analysis": "无法分析",
            "long_term_value_score": 50,
            "project_continuity_analysis": "无法分析",
            "industry_value_score": 50,
            "industry_value_analysis": "无法分析",
            "budget_authenticity_analysis": "无法分析",
            "bidding_probability_score": 50,
            "bidding_probability_analysis": "无法分析",
            "business_difficulty_score": 50,
            "sales_strategy": {
                "contact_department": "未知",
                "entry_point": "未知",
                "main_focus": "数据治理",
                "approach_type": "方案型",
            },
            "opportunity_level": "normal",
            "opportunity_reason": "分析失败",
        }

    def _fallback_analysis(self) -> dict:
        return {
            "error": "LLM response parsing failed",
            "project_type": "未知",
            "is_data_governance": False,
            "is_data_asset": False,
            "is_ai_project": False,
            "is_long_track": False,
            "industry_type": "其他",
            "target_department": "未知",
            "sales_entry_point": "未知",
            "risk_analysis": "分析失败",
            "business_value": "分析失败",
            "summary": "分析失败",
            "opportunity_intelligence": self._default_intelligence(),
        }

    async def analyze_unanalyzed_projects(self, session: AsyncSession) -> list[dict]:
        """分析所有未分析的项目"""
        result = await session.execute(
            select(Project).where(Project.status == "new")
        )
        projects = result.scalars().all()

        if not projects:
            logger.info("[Analyzer] 没有待分析的项目")
            return []

        logger.info(f"[Analyzer] 开始分析 {len(projects)} 个未分析项目")

        results = []
        for idx, project in enumerate(projects, 1):
            try:
                analysis = await self.analyze_project(project, session)
                results.append(analysis)
                logger.info(f"[Analyzer] 进度 {idx}/{len(projects)}")
            except Exception as e:
                logger.error(f"[Analyzer] 项目分析异常: {project.id}: {e}")
                results.append({"error": str(e)})

        logger.info(f"[Analyzer] 全部分析完成: {len(results)} 个项目")
        return results


# 全局单例
analyzer_service = AnalyzerService()