"""
Nik Project Hunter — AI Sales Service（第六阶段）

AI 销售服务 — 统一编排三大引擎：

1. Sales Strategy Engine — 生成 6 维销售策略
2. Follow-up Engine — 生成 6 维跟进建议
3. Relationship Intelligence Engine — 分析客户关系

并提供以下能力：
- 全量销售分析（批量处理所有商机）
- 单商机分析（处理单个项目/企业）
- 高优先级商机推荐
- AI 销售摘要生成
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.ai_client import ai_client
from app.models import Project, Company, EnterpriseSignal
from app.sales.models import SalesOpportunity
from app.sales.services.strategy_engine import sales_strategy_engine
from app.sales.services.followup_engine import followup_engine
from app.sales.services.relationship_engine import relationship_intelligence_engine


class SalesService:
    """
    AI 销售服务

    统一编排销售策略引擎、跟进建议引擎、关系智能引擎。
    """

    async def analyze_opportunity(
        self,
        session: AsyncSession,
        company_name: str,
        project: Optional[Project] = None,
        company: Optional[Company] = None,
        signals: Optional[list[EnterpriseSignal]] = None,
    ) -> SalesOpportunity:
        """
        对单个商机执行完整销售分析

        Args:
            session: 数据库会话
            company_name: 企业名称
            project: 项目对象（可选）
            company: 企业对象（可选）
            signals: 企业信号列表（可选）

        Returns:
            SalesOpportunity 对象
        """
        logger.info(f"[SalesService] 开始销售分析: {company_name}")

        # Step 1: 运行销售策略引擎
        logger.info("[SalesService] Step 1/3: 销售策略引擎")
        strategy = await sales_strategy_engine.generate_strategy(
            project=project, company=company, session=session
        )

        # Step 2: 运行跟进建议引擎
        logger.info("[SalesService] Step 2/3: 跟进建议引擎")
        followup = await followup_engine.generate_followup_advice(
            project=project, company=company,
            sales_stage=None, existing_vendor=None
        )

        # Step 3: 运行关系智能引擎
        logger.info("[SalesService] Step 3/3: 关系智能引擎")
        relationship = await relationship_intelligence_engine.analyze_relationship(
            project=project, company=company, signals=signals
        )

        # 生成 AI 销售摘要
        ai_summary = await self._generate_sales_summary(
            company_name, strategy, followup, relationship
        )

        # 保存到数据库
        sales_opp = await self._save_opportunity(
            session=session,
            company_name=company_name,
            project=project,
            company=company,
            strategy=strategy,
            followup=followup,
            relationship=relationship,
            ai_summary=ai_summary,
        )

        logger.info(
            f"[SalesService] 销售分析完成: {company_name} | "
            f"优先级={strategy['project_priority']} | "
            f"阶段={relationship['sales_stage']}"
        )

        return sales_opp

    async def analyze_all_projects(
        self, session: AsyncSession, limit: int = 50
    ) -> list[SalesOpportunity]:
        """
        批量分析所有未分析的项目

        Args:
            session: 数据库会话
            limit: 最大分析数量

        Returns:
            SalesOpportunity 列表
        """
        logger.info(f"[SalesService] 开始批量销售分析 (limit={limit})")

        # 查询已有销售分析的企业，跳过
        existing = await session.execute(
            select(SalesOpportunity.company_name).distinct()
        )
        existing_names = {row[0] for row in existing}

        # 查询未分析的高价值项目
        result = await session.execute(
            select(Project)
            .where(
                Project.score.isnot(None),
                Project.score >= 50,
            )
            .order_by(Project.score.desc())
            .limit(limit)
        )
        projects = result.scalars().all()

        results = []
        for project in projects:
            try:
                if project.buyer and project.buyer in existing_names:
                    logger.debug(f"[SalesService] 跳过已分析: {project.buyer}")
                    continue

                company = await self._find_company(session, project.buyer)
                signals = await self._find_signals(session, project.buyer)

                sales_opp = await self.analyze_opportunity(
                    session=session,
                    company_name=project.buyer or project.title[:50],
                    project=project,
                    company=company,
                    signals=signals,
                )
                results.append(sales_opp)

            except Exception as e:
                logger.error(f"[SalesService] 项目分析异常: {project.title[:50]}: {e}")
                continue

        logger.info(f"[SalesService] 批量分析完成: {len(results)} 个")
        return results

    async def analyze_all_companies(
        self, session: AsyncSession, limit: int = 50
    ) -> list[SalesOpportunity]:
        """
        批量分析所有企业画像

        Args:
            session: 数据库会话
            limit: 最大分析数量

        Returns:
            SalesOpportunity 列表
        """
        logger.info(f"[SalesService] 开始企业批量分析 (limit={limit})")

        existing = await session.execute(
            select(SalesOpportunity.company_name).distinct()
        )
        existing_names = {row[0] for row in existing}

        result = await session.execute(
            select(Company)
            .where(
                Company.opportunity_score.isnot(None),
                Company.opportunity_score >= 50,
            )
            .order_by(Company.opportunity_score.desc())
            .limit(limit)
        )
        companies = result.scalars().all()

        results = []
        for company in companies:
            try:
                if company.company_name in existing_names:
                    logger.debug(f"[SalesService] 跳过已分析: {company.company_name}")
                    continue

                signals = await self._find_signals(session, company.company_name)

                sales_opp = await self.analyze_opportunity(
                    session=session,
                    company_name=company.company_name,
                    company=company,
                    signals=signals,
                )
                results.append(sales_opp)

            except Exception as e:
                logger.error(f"[SalesService] 企业分析异常: {company.company_name}: {e}")
                continue

        logger.info(f"[SalesService] 企业批量分析完成: {len(results)} 个")
        return results

    async def get_top_priorities(
        self, session: AsyncSession, limit: int = 20
    ) -> list[SalesOpportunity]:
        """
        获取高优先级商机
        """
        result = await session.execute(
            select(SalesOpportunity)
            .order_by(
                SalesOpportunity.project_priority.asc(),
                SalesOpportunity.updated_at.desc().nullslast()
            )
            .limit(limit)
        )
        opportunities = result.scalars().all()

        priority_order = {"immediate": 0, "this_week": 1, "long_term": 2, "hold": 3}
        opportunities.sort(
            key=lambda o: priority_order.get(o.project_priority or "hold", 99)
        )

        return opportunities

    async def get_high_risk_opportunities(
        self, session: AsyncSession, limit: int = 20
    ) -> list[SalesOpportunity]:
        """
        获取高风险商机
        """
        result = await session.execute(
            select(SalesOpportunity)
            .order_by(SalesOpportunity.updated_at.desc())
            .limit(limit * 3)
        )
        all_opps = result.scalars().all()

        high_risk = [
            o for o in all_opps
            if o.relationship_risk
            and isinstance(o.relationship_risk, dict)
            and o.relationship_risk.get("risk_level") == "high"
        ]

        return high_risk[:limit]

    # =========================================================================
    # 辅助方法
    # =========================================================================

    async def _find_company(
        self, session: AsyncSession, company_name: Optional[str]
    ) -> Optional[Company]:
        if not company_name:
            return None
        try:
            result = await session.execute(
                select(Company).where(Company.company_name == company_name)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.debug(f"[SalesService] 查找企业失败: {company_name}: {e}")
            return None

    async def _find_signals(
        self, session: AsyncSession, company_name: Optional[str], limit: int = 10
    ) -> list[EnterpriseSignal]:
        if not company_name:
            return []
        try:
            result = await session.execute(
                select(EnterpriseSignal)
                .where(EnterpriseSignal.company_name == company_name)
                .order_by(EnterpriseSignal.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
        except Exception as e:
            logger.debug(f"[SalesService] 查找信号失败: {company_name}: {e}")
            return []

    async def _generate_sales_summary(
        self,
        company_name: str,
        strategy: dict,
        followup: dict,
        relationship: dict,
    ) -> str:
        """生成 AI 销售摘要"""
        try:
            prompt = (
                f"请为以下商机生成一个简洁的 AI 销售摘要（50-150字）：\n\n"
                f"企业: {company_name}\n"
                f"最佳切入部门: {strategy.get('best_entry_department', '未知')}\n"
                f"推荐方案: {strategy.get('recommended_solution', '未知')}\n"
                f"销售策略: {strategy.get('recommended_strategy', '未知')}\n"
                f"优先级: {strategy.get('project_priority', '未知')}\n"
                f"客户阶段: {relationship.get('sales_stage', '未知')}\n"
                f"推荐动作: {relationship.get('recommended_action', '未知')}\n"
                f"风险等级: {relationship.get('relationship_risk', {}).get('risk_level', '未知')}\n\n"
                "摘要要包含：为什么值得跟进、最佳切入方式、风险提示。"
            )

            result = await ai_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "你是一位资深企业级销售顾问。生成简洁有力的销售摘要。",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            if isinstance(result, dict):
                return result.get("content", result.get("text", ""))[:500]
            return str(result)[:500]

        except Exception as e:
            logger.error(f"[SalesService] 销售摘要生成失败: {e}")
            return f"{company_name} — 待分析"

    async def _save_opportunity(
        self,
        session: AsyncSession,
        company_name: str,
        project: Optional[Project],
        company: Optional[Company],
        strategy: dict,
        followup: dict,
        relationship: dict,
        ai_summary: str,
    ) -> SalesOpportunity:
        """保存销售分析到数据库"""
        try:
            now = datetime.now(timezone.utc)

            result = await session.execute(
                select(SalesOpportunity).where(
                    SalesOpportunity.company_name == company_name
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                sales_opp = existing
            else:
                sales_opp = SalesOpportunity(
                    company_name=company_name,
                    project_id=project.id if project else None,
                    company_id=company.id if company else None,
                )

            sales_opp.best_entry_department = strategy.get("best_entry_department")
            sales_opp.recommended_sales_path = strategy.get("recommended_sales_path")
            sales_opp.recommended_pitch = strategy.get("recommended_pitch")
            sales_opp.recommended_solution = strategy.get("recommended_solution")
            sales_opp.recommended_strategy = strategy.get("recommended_strategy")
            sales_opp.project_priority = strategy.get("project_priority")
            sales_opp.strategy_generated_at = now

            sales_opp.first_contact_advice = followup.get("first_contact_advice")
            sales_opp.phone_call_advice = followup.get("phone_call_advice")
            sales_opp.wechat_advice = followup.get("wechat_advice")
            sales_opp.email_subject_suggestion = followup.get("email_subject_suggestion")
            sales_opp.email_body_suggestion = followup.get("email_body_suggestion")
            sales_opp.ppt_suggestion = followup.get("ppt_suggestion")
            sales_opp.followup_generated_at = now

            sales_opp.sales_stage = relationship.get("sales_stage")
            sales_opp.customer_stage_detail = relationship.get("customer_stage_detail")
            sales_opp.recommended_action = relationship.get("recommended_action")
            sales_opp.relationship_risk = relationship.get("relationship_risk")
            sales_opp.relationship_analyzed_at = now

            priority = strategy.get("project_priority", "long_term")
            if priority == "immediate":
                sales_opp.next_followup_at = now + timedelta(hours=24)
            elif priority == "this_week":
                sales_opp.next_followup_at = now + timedelta(days=3)
            elif priority == "long_term":
                sales_opp.next_followup_at = now + timedelta(days=14)
            else:
                sales_opp.next_followup_at = None

            sales_opp.ai_sales_summary = ai_summary

            session.add(sales_opp)
            await session.commit()

            return sales_opp

        except Exception as e:
            logger.error(f"[SalesService] 保存销售分析失败: {e}")
            await session.rollback()
            raise


# 全局单例
sales_service = SalesService()