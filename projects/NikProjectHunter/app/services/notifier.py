"""
Nik Project Hunter — 通知服务（第四阶段：战略级项目通知升级）

职责：
1. 企业微信机器人 Webhook 推送
2. 高价值项目通知（S 级 + A 级且 score >= 70，与入库阈值对齐）
3. 战略级项目通知（【战略级项目】标签）
4. 长期价值项目通知（【长期价值项目】标签）
5. 高概率成交项目通知（【高概率成交项目】标签）
"""

import json
import asyncio
from loguru import logger
import httpx

from app.config import get_settings
from app.models import Project, ProcurementIntention
from app.sales.models import SalesOpportunity

settings = get_settings()


class NotifierService:
    """项目通知服务（第四阶段）"""

    LOG_FILE = "logs/notifier.log"

    # =============================================================================
    # 通知级别
    # =============================================================================
    NOTIFY_STRATEGIC = "strategic"       # 战略级项目
    NOTIFY_HIGH_VALUE = "high_value"     # 高价值项目
    NOTIFY_HIGH_PROBABILITY = "high_probability"  # 高概率成交

    def _add_intelligence_attrs(self, project: Project):
        """解析 Intelligence 数据到临时属性"""
        # 解析评分理由
        if project.score_reason:
            try:
                parsed = json.loads(project.score_reason)
                project._grade = parsed.get("grade", project.score_grade)
                project._reason_text = parsed.get("reason", "")
                project._worth_text = parsed.get("worth_following", "")
                project._key_track = parsed.get("key_track", False)
                project._dimensions = parsed.get("dimensions", {})
                project._intel_dims = parsed.get("intelligence_dimensions", {})
            except (json.JSONDecodeError, TypeError):
                project._grade = project.score_grade
                project._reason_text = project.score_reason[:100]
                project._worth_text = ""
                project._key_track = False
                project._dimensions = {}
                project._intel_dims = {}
        else:
            project._grade = project.score_grade
            project._reason_text = ""
            project._worth_text = ""
            project._key_track = False
            project._dimensions = {}
            project._intel_dims = {}

        # 解析 Intelligence 分析
        if project.analysis and isinstance(project.analysis, dict):
            intelligence = project.analysis.get("opportunity_intelligence", {})
            project._opportunity_level = intelligence.get("opportunity_level", "normal")
            project._bidding_prob = intelligence.get("bidding_probability_score", 50)
            project._customer_maturity = intelligence.get("customer_maturity_score", 50)
            project._long_term_value = intelligence.get("long_term_value_score", 50)
            project._sales_strategy = intelligence.get("sales_strategy", {})
        else:
            project._opportunity_level = "normal"
            project._bidding_prob = 50
            project._customer_maturity = 50
            project._long_term_value = 50
            project._sales_strategy = {}

    def _should_notify(self, project: Project) -> bool:
        # 现阶段：所有项目都推送通知
        return True

    def _get_notification_level(self, project: Project) -> list[str]:
        """
        获取通知级别列表

        现阶段：所有项目都推送
        """
        levels = [self.NOTIFY_HIGH_VALUE]
        if project._opportunity_level == "strategic":
            levels.append(self.NOTIFY_STRATEGIC)
        if project._bidding_prob >= 80:
            levels.append(self.NOTIFY_HIGH_PROBABILITY)
        return levels

    async def notify_intention(self, intention: ProcurementIntention) -> bool:
        """
        推送采购意向 Intelligence 通知（第六阶段新增）

        Args:
            intention: 采购意向

        Returns:
            是否推送成功
        """
        if not settings.WECHAT_WEBHOOK_URL:
            return False

        if not intention.is_high_value:
            return False

        # 构建采购意向通知
        nd = intention.to_notification_dict()
        budget_str = nd.get("estimated_budget", "未知")
        date_str = intention.publish_date.strftime("%Y-%m-%d") if intention.publish_date else "未知"

        content = (
            f"## 🔮 采购意向 Intelligence\n\n"
            f"### {intention.title}\n\n"
            f"> 🏢 **采购单位：** {intention.buyer or '未知'}\n\n"
            f"> 📍 **地区：** {intention.region or '未知'}\n\n"
            f"> 💰 **预算：** {budget_str}\n\n"
            f"> 🏷️ **来源：** {intention.source}\n\n"
            f"> 📅 **发布日期：** {date_str}\n\n"
            "---\n\n"
            f"**📊 项目阶段：{nd.get('project_stage', '未知')}**\n\n"
            f"**🧭 战略方向：{nd.get('strategic_direction', '未知')}**\n\n"
            "---\n\n"
            f"**🔮 未来商机评分：{nd.get('future_opportunity_score', 'N/A')}/100**\n\n"
            f"> ⏰ 提前介入窗口：{nd.get('engagement_window', '')}\n\n"
            f"> 📆 预计招标时间：{nd.get('estimated_tender_date', '待定')}\n\n"
            f"> 🎯 商机级别：{nd.get('opportunity_level', 'observation')}\n\n"
            "---\n\n"
            f"> 💡 **推荐动作：** {nd.get('recommended_action', '暂无')}\n\n"
            f"> 🏗️ **推荐跟进部门：** {nd.get('recommended_department', '暂无')}\n\n"
            f"[🔗 查看原文]({intention.source_url})\n\n"
            "---\n"
            "*🔮 AI 意向 Intelligence · 灵爪 Nova · 提前布局商机*"
        )

        message = {
            "msgtype": "markdown",
            "markdown": {"content": content},
        }

        success = await self._send_wecom_webhook(message)
        if success:
            logger.info(
                f"[Notifier] 意向推送成功: {intention.title[:50]} | "
                f"stage={intention.project_stage} | "
                f"window={intention.engagement_window_score}"
            )
            intention.status = "notified"
        else:
            logger.warning(f"[Notifier] 意向推送失败: {intention.title[:50]}")

        return success

    async def notify_high_value_project(self, project: Project) -> bool:
        """
        推送高价值项目通知（含 Intelligence 增强信息）

        Args:
            project: 项目

        Returns:
            是否推送成功
        """
        if not settings.WECHAT_WEBHOOK_URL:
            logger.debug("[Notifier] WECHAT_WEBHOOK_URL 未配置，跳过通知")
            return False

        if not project.score:
            logger.debug("[Notifier] 项目无评分，跳过通知")
            return False

        if not self._should_notify(project):
            logger.info(
                f"[Notifier] 跳过通知: {project.title[:50]} | score={project.score}"
            )
            return False

        # 加载 Intelligence 属性
        self._add_intelligence_attrs(project)

        # 构建增强版 Markdown 消息
        message = self._build_enhanced_markdown(project)
        success = await self._send_wecom_webhook(message)

        if success:
            logger.info(
                f"[Notifier] 推送成功: {project.title[:50]} | "
                f"score={project.score} | grade={project.score_grade} | "
                f"level={project._opportunity_level}"
            )
        else:
            logger.warning(f"[Notifier] 推送失败: {project.title[:50]}")

        return success

    def _format_budget(self, budget) -> str:
        if budget is None:
            return "未知"
        try:
            budget = float(budget)
            if budget >= 10000_0000:
                return f"{budget / 10000_0000:.2f} 亿"
            elif budget >= 10000:
                return f"{budget / 10000:.1f} 万"
            return f"{budget:.0f} 元"
        except (ValueError, TypeError):
            return "未知"

    def _build_enhanced_markdown(self, project: Project) -> dict:
        """
        构建增强版企业微信 Markdown 消息

        包含：
        - 项目标签（战略级/长期价值/高概率）
        - Intelligence 评分（客户成熟度、长期价值、中标概率）
        - 销售策略建议
        """
        budget_str = self._format_budget(project.budget)
        date_str = (
            project.publish_date.strftime("%Y-%m-%d")
            if project.publish_date
            else "未知"
        )
        # 第六阶段：项目阶段与截止日期
        notice_type = getattr(project, "notice_type", None) or "未知"
        # 标书获取截止
        doc_deadline_str = ""
        if getattr(project, "deadline", None):
            doc_deadline_str = project.deadline.strftime("%Y-%m-%d %H:%M")
        elif notice_type in ("意向采购", "供应商征集"):
            doc_deadline_str = "待正式招标"
        else:
            doc_deadline_str = "未知"
        # 投标截止
        bid_deadline_str = ""
        bid_dl = getattr(project, "bid_deadline", None)
        if bid_dl:
            bid_deadline_str = bid_dl.strftime("%Y-%m-%d %H:%M")
        else:
            bid_deadline_str = doc_deadline_str

        reason_text = getattr(project, "_reason_text", "")[:100] or ""
        summary = project.summary or ""
        if project.analysis and isinstance(project.analysis, dict):
            summary = project.analysis.get("summary", summary)
        if len(summary) > 150:
            summary = summary[:150] + "..."

        # 通知标签
        tags = self._get_notification_level(project)
        tag_emojis = {
            self.NOTIFY_STRATEGIC: "【🏛️ 战略级项目】",
            self.NOTIFY_HIGH_VALUE: "【🔥 高价值项目】",
            self.NOTIFY_HIGH_PROBABILITY: "【🎯 高概率成交】",
        }
        tag_line = " ".join(tag_emojis.get(t, "") for t in tags) if tags else "【📊 关注项目】"

        # Intelligence 评分
        cm = getattr(project, "_customer_maturity", 50)
        ltv = getattr(project, "_long_term_value", 50)
        bp = getattr(project, "_bidding_prob", 50)
        sales_strategy = getattr(project, "_sales_strategy", {})
        main_focus = sales_strategy.get("main_focus", "数据治理")
        approach = sales_strategy.get("approach_type", "方案型")

        content = (
            f"## {tag_line}\n\n"
            f"{project.title}\n\n"
            f"🏢 采购单位：{project.buyer or '未知'}\n\n"
            f"💰 预算金额：{budget_str}\n\n"
            f"📍 地区：{project.region or '未知'}\n\n"
            f"🏷️ 来源平台：{project.source}\n\n"
            f"📅 发布日期：{date_str}\n\n"
            f"🏷️ 公告类型：{notice_type}\n\n"
            f"⏰ 标书获取截止：{doc_deadline_str}\n\n"
            f"⏰ 投标截止时间：{bid_deadline_str}\n\n"
            "---\n\n"
            f"📊 商机评分：{project.score} 分 | 等级：{project.score_grade or 'N/A'}\n\n"
            "🧠 商机 Intelligence 评估\n\n"
            f"👤 客户成熟度：{cm}/100\n\n"
            f"📈 长期价值：{ltv}/100\n\n"
            f"🎯 中标概率：{bp}/100\n\n"
            "---\n\n"
            f"💡 评分理由：{reason_text or '暂无'}\n\n"
            f"🎯 主打方向：{main_focus}\n\n"
            f"🏗️ 销售方式：{approach}\n\n"
            f"📋 项目摘要：{summary or '暂无'}\n\n"
            f"🔗 [查看原文]({project.source_url})\n\n"
            "---\n"
            f"*AI 自动生成 · 灵爪 Nova · 商机 Intelligence v4*"
        )

        return {
            "msgtype": "markdown",
            "markdown": {"content": content},
        }

    async def _send_wecom_webhook(self, message: dict) -> bool:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    settings.WECHAT_WEBHOOK_URL,
                    json=message,
                    headers={"Content-Type": "application/json"},
                )
                if response.is_success:
                    resp_data = response.json()
                    if resp_data.get("errcode") == 0:
                        return True
                    logger.warning(
                        f"[Notifier] 企业微信错误: errcode={resp_data.get('errcode')}"
                    )
                    return False
                logger.warning(f"[Notifier] HTTP {response.status_code}")
                return False
        except httpx.TimeoutException:
            logger.error("[Notifier] Webhook 请求超时")
            return False
        except Exception as e:
            logger.error(f"[Notifier] Webhook 异常: {e}")
            return False

    async def send_report(self, title: str, summary: str, projects: list) -> bool:
        """推送日报/报告到企业微信群（分批推送避免超限）"""
        if not settings.WECHAT_WEBHOOK_URL:
            logger.debug("[Notifier] WECHAT_WEBHOOK_URL 未配置，跳过报告")
            return False

        if not projects:
            logger.debug("[Notifier] 无项目，跳过报告")
            return False

        # 分批推送：每批 3 条，避免超过 4096 字节限制
        batch_size = 3
        total_projects = len(projects)
        total_batches = (total_projects + batch_size - 1) // batch_size

        all_success = True

        for batch_idx in range(total_batches):
            start = batch_idx * batch_size
            end = start + batch_size
            batch_projects = projects[start:end]
            is_last = (batch_idx == total_batches - 1)

            # 构建消息内容
            lines = [f"## 【🔥 每日商机汇报】({batch_idx+1}/{total_batches})", ""]

            for idx, p in enumerate(batch_projects, 1):
                budget_str = self._format_budget(p.budget)
                date_str = (
                    p.publish_date.strftime("%Y-%m-%d")
                    if p.publish_date
                    else "未知"
                )
                notice_type = getattr(p, "notice_type", None) or "未知"
                # 标书获取截止时间
                doc_deadline_str = ""
                if getattr(p, "deadline", None):
                    doc_deadline_str = p.deadline.strftime("%Y-%m-%d %H:%M")
                elif notice_type in ("意向采购", "供应商征集"):
                    doc_deadline_str = "待正式招标"
                else:
                    doc_deadline_str = "未知"
                # 投标截止时间
                bid_deadline_str = ""
                bid_dl = getattr(p, "bid_deadline", None)
                if bid_dl:
                    bid_deadline_str = bid_dl.strftime("%Y-%m-%d %H:%M")
                else:
                    bid_deadline_str = doc_deadline_str

                summary_text = p.summary or ""
                if p.analysis and isinstance(p.analysis, dict):
                    summary_text = p.analysis.get("summary", summary_text)
                if len(summary_text) > 150:
                    summary_text = summary_text[:150] + "..."

                analysis = p.analysis if isinstance(p.analysis, dict) else {}
                intelligence = analysis.get("opportunity_intelligence", {})
                sales_strategy = intelligence.get("sales_strategy", {})
                main_focus = sales_strategy.get("main_focus", "数据治理")
                approach = sales_strategy.get("approach_type", "方案型")
                cm = p.customer_maturity_score or intelligence.get("customer_maturity_score", 50)
                ltv = p.long_term_value_score or intelligence.get("long_term_value_score", 50)
                bp = p.bidding_probability_score or intelligence.get("bidding_probability_score", 50)

                lines.append(f"{idx}、{p.title}")
                lines.append(f"🏢 采购单位：{p.buyer or '未知'}")
                lines.append(f"💰 预算金额：{budget_str}")
                lines.append(f"📍 地区：{p.region or '未知'}")
                lines.append(f"🏷️ 来源平台：{p.source or '未知'}")
                lines.append(f"📅 发布日期：{date_str}")
                lines.append(f"🏷️ 公告类型：{notice_type}")
                lines.append(f"⏰ 标书获取截止：{doc_deadline_str}")
                lines.append(f"⏰ 投标截止时间：{bid_deadline_str}")
                lines.append("---")
                lines.append(f"📊 商机评分：{p.score} 分 | 等级：{p.score_grade or 'N/A'}")
                lines.append("🧠 商机 Intelligence 评估")
                lines.append(f"👤 客户成熟度：{cm}/100")
                lines.append(f"📈 长期价值：{ltv}/100")
                lines.append(f"🎯 中标概率：{bp}/100")
                lines.append("---")

                reason_text = getattr(p, "_reason_text", "") or ""
                if not reason_text:
                    score_reason = p.score_reason or "{}"
                    try:
                        sr = json.loads(score_reason) if isinstance(score_reason, str) else score_reason
                        reason_text = sr.get("reason", "")[:100]
                    except (json.JSONDecodeError, AttributeError):
                        reason_text = ""

                lines.append(f"💡 评分理由：{reason_text or '暂无'}")
                lines.append(f"🎯 主打方向：{main_focus}")
                lines.append(f"🏗️ 销售方式：{approach}")
                lines.append(f"📋 项目摘要：{summary_text or '暂无'}")
                lines.append(f"🔗 [查看原文]({p.source_url})")
                lines.append("")

            # 最后一批添加统计信息
            if is_last:
                lines.append("---")
                lines.append(f"*AI 自动生成 · 灵爪 Nova · {title}*")
                lines.append(f"> 共 {total_projects} 条商机 | {summary}")

            content = "\n".join(lines)
            message = {
                "msgtype": "markdown",
                "markdown": {"content": content},
            }

            success = await self._send_wecom_webhook(message)
            if not success:
                all_success = False
                logger.warning(
                    f"[Notifier] 日报批次 {batch_idx+1}/{total_batches} 推送失败"
                )
            else:
                logger.info(
                    f"[Notifier] 日报批次 {batch_idx+1}/{total_batches} 推送成功"
                )

            # 批次间延迟，避免触发频率限制
            if not is_last:
                await asyncio.sleep(1)

        return all_success

    async def send_test_message(self) -> bool:
        if not settings.WECHAT_WEBHOOK_URL:
            logger.warning("[Notifier] WECHAT_WEBHOOK_URL 未配置")
            return False
        message = {
            "msgtype": "markdown",
            "markdown": {
                "content": (
                    "## ✅ 测试消息\n\n"
                    "Nik Project Hunter v0.4 通知系统配置成功\n\n"
                    "> 商机 Intelligence Engine 已上线\n\n"
                    "> 支持：战略级项目 | 长期价值项目 | 高概率成交\n\n"
                    "*⏰ AI 自动分析 · 灵爪 Nova · 商机 Intelligence v4*"
                ),
            },
        }
        return await self._send_wecom_webhook(message)


# 全局单例
notifier_service = NotifierService()