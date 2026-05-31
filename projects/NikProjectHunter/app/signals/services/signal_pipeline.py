"""
Nik Project Hunter — 信号采集与分析管道（第五阶段）

职责：
1. 采集信号 → 2. 存储信号 → 3. AI 分析 → 4. 企业画像 → 5. 通知

流程：
1. 运行所有信号爬虫
2. 将原始信号写入 EnterpriseSignal 表
3. 对每条信号进行 AI 分析
4. 按企业分组，更新企业画像
5. 推送信号摘要通知
"""

from datetime import datetime
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EnterpriseSignal, Company
from app.database import async_session_factory
from app.signals.spiders.manager import signal_manager
from app.signals.services import signal_analyzer
from app.signals.services.enterprise_profile import enterprise_profile
from app.signals.services.signal_notifier import signal_notifier


class SignalPipeline:
    """
    信号采集与分析管道

    完整流程：
    1. 采集 → 2. 存储 → 3. AI 分析 → 4. 企业画像 → 5. 通知
    """

    async def run_pipeline(self) -> dict:
        """
        执行完整信号管道

        Returns:
            管道执行摘要
        """
        logger.info("=" * 60)
        logger.info("📡 开始执行信号采集与分析管道")
        logger.info("=" * 60)

        result = {
            "signals_collected": 0,
            "signals_stored": 0,
            "signals_analyzed": 0,
            "companies_profiled": 0,
            "notifications_sent": False,
            "errors": [],
        }

        async with async_session_factory() as session:
            try:
                # =========================================================================
                # Step 1: 采集信号
                # =========================================================================
                logger.info("[信号管道] Step 1/5: 开始信号采集")
                crawl_status, raw_signals = await signal_manager.crawl_all()
                result["signals_collected"] = len(raw_signals)
                logger.info(
                    f"[信号管道] Step 1/5: 采集完成 | {len(raw_signals)} 个信号"
                )

                if not raw_signals:
                    logger.info("[信号管道] 无新信号，跳过后续步骤")
                    return result

                # =========================================================================
                # Step 2: 存储原始信号
                # =========================================================================
                logger.info("[信号管道] Step 2/5: 存储原始信号")
                stored_signals = await self._store_signals(raw_signals, session)
                result["signals_stored"] = len(stored_signals)
                logger.info(
                    f"[信号管道] Step 2/5: 存储完成 | {len(stored_signals)} 条"
                )

                if not stored_signals:
                    logger.info("[信号管道] 无新信号需要存储")
                    return result

                # =========================================================================
                # Step 3: AI 分析信号
                # =========================================================================
                logger.info("[信号管道] Step 3/5: AI 分析信号")
                analyzed_signals = await self._analyze_signals(stored_signals)
                result["signals_analyzed"] = len(analyzed_signals)
                logger.info(
                    f"[信号管道] Step 3/5: 分析完成 | {len(analyzed_signals)} 条"
                )

                # =========================================================================
                # Step 4: 更新企业画像
                # =========================================================================
                logger.info("[信号管道] Step 4/5: 更新企业画像")
                companies_profiled = await self._update_enterprise_profiles(
                    analyzed_signals, session
                )
                result["companies_profiled"] = len(companies_profiled)
                logger.info(
                    f"[信号管道] Step 4/5: 画像完成 | {len(companies_profiled)} 个企业"
                )

                await session.commit()

                # =========================================================================
                # Step 5: 推送通知
                # =========================================================================
                logger.info("[信号管道] Step 5/5: 推送信号通知")
                # 收集企业画像摘要
                company_profiles = []
                for company_name in companies_profiled:
                    profile = await enterprise_profile.get_company_profile(
                        company_name, session
                    )
                    if profile:
                        company_profiles.append(profile)

                # 如果 profile 则 company_profiles.append(profile)
                        company_profiles.append(profile)

                notified = await signal_notifier.notify_signal_summary(
                    signals=analyzed_signals,
                    companies=company_profiles,
                )
                result["notifications_sent"] = notified
                logger.info(
                    f"[信号管道] Step 5/5: 通知完成 | 推送={'是' if notified else '否'}"
                )

                # 汇总日志
                logger.info("=" * 60)
                logger.info(
                    f"🏁 信号管道完成 | "
                    f"采集 {result['signals_collected']} 个 | "
                    f"存储 {result['signals_stored']} 条 | "
                    f"分析 {result['signals_analyzed']} 条 | "
                    f"画像 {result['companies_profiled']} 个"
                )
                logger.info("=" * 60)

            except Exception as e:
                logger.error(f"[信号管道] 管道执行异常: {e}")
                result["errors"].append(str(e))
                await session.rollback()

        return result

    async def _store_signals(
        self,
        raw_signals: list[dict],
        session: AsyncSession,
    ) -> list[EnterpriseSignal]:
        """
        存储原始信号到数据库

        去重逻辑：同一公司同一类型的信号，标题相同则跳过
        """
        stored = []

        for raw in raw_signals:
            try:
                company_name = raw.get("company_name", "未知企业")
                signal_type = raw.get("signal_type", "unknown")
                title = raw.get("title", "")

                # 去重检查
                result = await session.execute(
                    select(EnterpriseSignal).where(
                        EnterpriseSignal.company_name == company_name,
                        EnterpriseSignal.signal_type == signal_type,
                        EnterpriseSignal.title == title,
                    )
                )
                if result.scalar_one_or_none():
                    continue

                # 创建信号记录
                signal = EnterpriseSignal(
                    signal_type=signal_type,
                    company_name=company_name,
                    source_url=raw.get("source_url", ""),
                    source_platform=raw.get("source_platform", ""),
                    title=title,
                    content=raw.get("content", ""),
                    publish_date=None,  # 可通过日期解析
                    status="new",
                )

                # 解析发布日期
                pub_date = raw.get("publish_date")
                if pub_date and isinstance(pub_date, str):
                    try:
                        from datetime import datetime as dt
                        signal.publish_date = dt.datetime.strptime(
                            pub_date, "%Y-%m-%d"
                        )
                    except (ValueError, TypeError):
                        pass

                session.add(signal)
                stored.append(signal)

            except Exception as e:
                logger.error(f"[信号管道] 存储信号失败: {e}")
                continue

        if stored:
            await session.flush()

        return stored

    async def _analyze_signals(
        self,
        signals: list[EnterpriseSignal],
    ) -> list[dict]:
        """
        AI 分析信号

        Args:
            signals: EnterpriseSignal 对象列表

        Returns:
            分析后的信号字典列表
        """
        analyzed = []
        for signal in signals:
            try:
                signal_data = {
                    "signal_type": signal.signal_type,
                    "company_name": signal.company_name,
                    "title": signal.title,
                    "content": signal.content or "",
                    "source_url": signal.source_url,
                    "source_platform": signal.source_platform,
                }

                analysis = await signal_analyzer.analyze_signal(signal_data)

                # 更新数据库中的分析结果
                signal.analysis = analysis
                signal.signal_score = analysis.get("signal_score", 0)
                signal.signal_level = analysis.get("impact_level", "low")
                signal.status = "analyzed"

                analyzed.append({
                    "signal_type": signal.signal_type,
                    "company_name": signal.company_name,
                    "id": signal.id,
                    "analysis": analysis,
                    **signal_data,
                    "analysis": analysis,
                })

            except Exception as e:
                logger.error(f"[信号管道] 分析信号失败: {signal.title[:50]}: {e}")
                continue

        return analyzed

    async def _update_enterprise_profiles(
        self,
        analyzed_signals: list[dict],
        session: AsyncSession,
    ) -> list[str]:
        """
        按企业分组，更新企业画像

        Args:
            analyzed_signals: 已分析的信号列表
            session: 数据库会话

        Returns:
            已画像的企业名称列表
        """
        # 按公司分组
        company_signals = {}
        for signal in analyzed_signals:
            company = signal.get("company_name", "company_name", "未知企业")
            if company not in company_signals:
                company_signals[company] = []
            company_signals[company].append(signal)

        profiled_companies = []
        for company_name, signals in company_signals.items():
            if company_name == "未知企业":
                continue
            try:
                profile = await enterprise_profile.build_profile(
                    company_name=company_name,
                    signals=signals,
                    session=session,
                )
                if "error" not in profile:
                    profiled_companies.append(company_name)
            except Exception as e:
                logger.error(
                    f"[信号管道] 企业画像失败: {company_name}: {e}"
                )
                continue

        return profiled_companies

    async def trigger_manual_pipeline(self) -> dict:
        """
        手动触发信号管道

        Returns:
            执行结果
        """
        logger.info("📡 手动触发信号管道")
        return await self.run_pipeline()


# 全局单例
signal_pipeline = SignalPipeline()