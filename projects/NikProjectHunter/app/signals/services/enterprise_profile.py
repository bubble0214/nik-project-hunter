"""
Nik Project Hunter — 企业画像引擎（第五阶段）

职责：
1. 根据信号分析生成企业画像
2. 评估企业数字化/AI/数据资产化成熟度
3. 评估长期合作价值
4. 推荐销售策略
5. 更新公司画像到数据库
"""

import json
from datetime import datetime, timezone, timedelta
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, EnterpriseSignal
from app.core.ai_client import ai_client


class EnterpriseProfileEngine:
    """
    企业画像引擎（第五阶段画像引擎

    根据信号分析结果，生成企业画像：
    1. 数字化成熟度
    2. AI 成熟度
    3. 数据资产化成熟度
    4. 长期合作价值
    5. 预算能力
    6. 推荐切入方向
    7. 推荐销售策略
    8. 推荐接触部门
    """

    async def build_profile(
        self,
        company_name: str,
        signals: list[dict],
        session: AsyncSession,
    ) -> dict:
        """
        构建企业画像

        Args:
            company_name: 企业名称
            signals: 该企业的信号列表（已分析）
            session: 数据库会话

        Returns:
            企业画像字典
        """
        logger.info(f"[企业画像] 开始构建: {company_name}")

        # 调用 LLM 生成画像
        profile = await self._call_llm_profile(company_name, signals)

        if "error" not in profile:
            # 更新数据库
            await self._update_company_profile(
                company_name=company_name,
                profile=profile,
                signals=signals,
                session=session,
            )

            # 标记信号为已处理
            await self._mark_signals_profiled(signals, session)

            logger.info(
                f"[企业画像] 完成: {company_name} | "
                f"数字成熟度={profile.get('digital_maturity', 'N/A')} | "
                f"AI成熟度={profile.get('ai_maturity', 'N/A')} | "
                f"战略级别={profile.get('strategic_level', 'N/A')}"
            )
        else:
            logger.error(f"[企业画像] 构建失败: {company_name}: {profile.get('error')}")

        return profile

    async def _call_llm_profile(self, company_name: str, signals: list[dict]) -> dict:
        """
        调用 LLM 生成企业画像

        输出：
        - 企业数字化成熟度
        - AI 成熟度
        - 数据资产化成熟度
        - 长期合作价值
        - 预算能力
        - 推荐切入方向
        - 推荐销售策略
        - 推荐接触部门
        """
        # 整理信号摘要
        signals_summary = []
        for s in signals:
            analysis = s.get("analysis", {})
            signals_summary.append(
                f"[{s.get('signal_type', '未知')}] "
                f"{s.get('title', '')} "
                f"→ 分析: {analysis.get('summary', '')}"
            )

        signals_text = "\n".join(signals_summary[:10])  # 取前 10 个

        prompt = (
            "你是一个企业级销售战略顾问，专门评估企业的数字化/AI/数据资产化成熟度。\n\n"
            f"企业名称: {company_name}\n\n"
            f"近期信号摘要（来自招聘、新闻、高管变动、政策分析）:\n{signals_text or '暂无信号'}\n\n"
            "请从以下维度评估该企业，返回 JSON 格式：\n\n"
            "{\n"
            '  "digital_maturity": 0-100,\n'
            '  "ai_maturity": 0-100,\n'
            '  "data_maturity": 0-100,\n'
            '  "estimated_budget_level": "high/medium/low",\n'
            '  "opportunity_score": 0-100,\n'
            '  "strategic_level": "strategic/high_value/normal/low",\n'
            '  "budget_estimate": "预估预算范围描述",\n'
            '  "long_term_value": "长期合作价值分析（50字）",\n'
            '  "recommended_focus": "推荐切入方向（数据治理/AI平台/数据资产/安全/数字化）",\n'
            '  "recommended_strategy": "推荐销售策略描述（50字）",\n'
            '  "recommended_department": "推荐接触部门",\n'
            '  "entry_point": "建议切入点",\n'
            '  "risk_analysis": "风险分析（30字）",\n'
            '  "summary": "企业画像摘要（80字）",\n'
            '  "maturity_analysis": {\n'
            '    "digital_stage": "早期/建设中/成熟/领先",\n'
            '    "ai_readiness": "是否准备好AI采购",\n'
            '    "data_asset_potential": "数据资产化潜力"\n'
            '  }\n'
            "}\n\n"
            "评分标准：\n"
            "- digital_maturity: 企业的数字化转型阶段（招聘/AI新闻/数字化投入越多越高\n"
            "- ai_maturity: 有AI岗位/AI新闻/AI战略信号越高\n"
            "- data_maturity: 有数据治理岗位/数据资产新闻越高\n"
            "- opportunity_score: 综合评分，考虑行业、成熟度、预算能力\n"
            "- strategic_level: 国企/金融/能源/医疗+高预算+明确信号=strategic\n\n"
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
            logger.error(f"[企业画像] LLM 返回非法 JSON for {company_name}")
            return self._default_profile()

    def _default_profile(self) -> dict:
        return {
            "digital_maturity": 0,
            "ai_maturity": 0,
            "data_maturity": 0,
            "estimated_budget_level": "low",
            "opportunity_score": 0,
            "strategic_level": "normal",
            "budget_estimate": "无法评估",
            "long_term_value": "无法评估",
            "recommended_focus": "数据治理",
            "recommended_strategy": "观察",
            "recommended_department": "未知",
            "entry_point": "未知",
            "risk_analysis": "无法评估",
            "summary": "画像生成失败",
            "maturity_analysis": {
                "digital_stage": "未知",
                "ai_readiness": "未知",
                "data_asset_potential": "未知",
            },
        }

    async def _update_company_profile(
        self,
        company_name: str,
        profile: dict,
        signals: list[dict],
        session: AsyncSession,
    ):
        """更新或创建企业画像"""
        # 查找已有企业
        result = await session.execute(
            select(Company).where(Company.company_name == company_name)
        )
        company = result.scalar_one_or_none()


        now = datetime.now(timezone.utc)

        if company:
            # 更新已有记录
            company.industry = profile.get("industry", company.industry)
            company.digital_maturity = profile.get("digital_maturity")
            company.ai_maturity = profile.get("ai_maturity")
            company.data_maturity = profile.get("data_maturity")
            company.estimated_budget_level = profile.get("estimated_budget_level")
            company.opportunity_score = profile.get("opportunity_score")
            company.strategic_level = profile.get("strategic_level")
            company.recommended_strategy = {
                "focus": profile.get("recommended_focus"),
                "strategy": profile.get("recommended_strategy"),
                "entry_point": profile.get("entry_point"),
                "risk_analysis": profile.get("risk_analysis"),
            }
            company.recommended_department = profile.get("recommended_department")
            company.recommended_focus = profile.get("recommended_focus")
            company.profile_updated_at = now

            # 更新最新信号
            company.latest_signal_summary = profile.get("summary", "")
            company.latest_signals = [
                {"type": s.get("signal_type"), "title": s.get("title")[:100]}
                for s in signals[-10:]
            ]
            company.latest_signal_at = now
        else:
            # 创建新记录
            company = Company(
                company_name=company_name,
                industry=profile.get("industry", ""),
                digital_maturity=profile.get("digital_maturity"),
                ai_maturity=profile.get("ai_maturity"),
                data_maturity=profile.get("data_maturity"),
                estimated_budget_level=profile.get("estimated_budget_level"),
                opportunity_score=profile.get("opportunity_score"),
                strategic_level=profile.get("strategic_level"),
                recommended_strategy={
                    "focus": profile.get("recommended_focus"),
                    "strategy": profile.get("recommended_strategy"),
                    "entry_point": profile.get("entry_point"),
                    "risk_analysis": profile.get("risk_analysis"),
                },
                recommended_department=profile.get("recommended_department"),
                recommended_focus=profile.get("recommended_focus"),
                profile_updated_at=now,
                latest_signal_summary=profile.get("summary", ""),
                latest_signals=[
                    {"type": s.get("signal_type"), "title": s.get("title")[:100]}
                    for s in signals[-10:]
                ],
                latest_signal_at=now,
            )
            session.add(company)

        await session.flush()

    async def _mark_signals_profiled(self, signals: list[dict], session: AsyncSession):
        """标记信号为已处理"""
        for signal in signals:
            signal_id = signal.get("id")
            if signal_id:
                db_signal = await session.get(EnterpriseSignal, signal_id)
                if db_signal:
                    db_signal.status = "profiled"
        await session.flush()

    async def get_company_profile(
        self,
        company_name: str,
        session: AsyncSession,
    ) -> dict:
        """获取企业画像"""
        result = await session.execute(
            select(Company).where(Company.company_name == company_name)
        )
        company = result.scalar_one_or_none()
        if not company:
            return {}
        return company.profile_summary

    async def list_strategic_companies(
        self,
        session: AsyncSession,
        limit: int = 20,
    ) -> list[dict]:
        """获取战略客户列表"""
        result = await session.execute(
            select(Company)
            .where(
                Company.strategic_level.in_(["strategic", "high_value"])
            )
            .order_by(Company.opportunity_score.desc().nullslast())
            .limit(limit)
        )
        return [c.profile_summary for c in result.scalars()]


# 全局单例
enterprise_profile = EnterpriseProfileEngine()