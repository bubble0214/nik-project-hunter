"""
Nik Project Hunter — 信号通知服务（第五阶段）

职责第五阶段）

职责：
1. 推送信号通知到企业微信
2. 支持多种通知级别（战略客户/AI建设企业/数据资产化机会/高概率客户）
"""

from datetime import datetime
from loguru import logger
import httpx

from app.config import get_settings

settings = get_settings()


class SignalNotifier:
    """
    企业信号通知服务

    支持通知级别：
    - 【战略客户】— 战略客户识别
    - 【AI建设企业】— AI 建设趋势明显的企业
    - 【数据资产化机会】— 数据资产化信号
    - 【高概率客户】— 高概率启动项目的客户
    """

    async def notify_signal_summary(
        self,
        signals: list[dict],
        companies: list[dict],
        policy_insights: dict = None,
    ) -> bool:
        """
        推送信号摘要通知

        Args:
            signals: 新采集的信号列表
            companies: 受影响的企业画像列表
            policy_insights: 政策洞察（可选）

        Returns:
            是否推送成功
        """
        if not settings.WECHAT_WEBHOOK_URL:
            logger.debug("[信号通知] WECHAT_WEBHOOK_URL 未配置，跳过")
            return False

        message = self._build_signal_summary_markdown(signals, companies, policy_insights)
        success = await self._send_wecom_webhook(message)

        if success:
            logger.info(
                f"[信号通知] 推送成功 | "
                f"{len(signals)} 个信号 | "
                f"{len(companies)} 个企业画像"
            )
        else:
            logger.warning("[信号通知] 推送失败")

        return success

    async def notify_strategic_customer(
        self,
        company: dict,
        reason: str,
    ) -> bool:
        """
        推送战略客户识别通知

        Args:
            company: 企业画像字典
            reason: 识别理由

        Returns:
            是否推送成功
        """
        if not settings.WECHAT_WEBHOOK_URL:
            return False

        message = self._build_strategic_customer_markdown(company, reason)
        return await self._send_wecom_webhook(message)

    def _build_signal_summary_markdown(
        self,
        signals: list[dict],
        companies: list[dict],
        policy_insights: dict = None,
    ) -> dict:
        """构建信号摘要 Markdown 消息"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 统计信号类型
        signal_types = {}
        for s in signals:
            st = s.get("signal_type", "unknown")
            signal_types[st] = signal_types.get(st, 0) + 1

        # 识别战略客户
        strategic_companies = [c for c in companies if c.get("strategic_level") == "strategic"]
        ai_companies = [c for c in companies if (c.get("ai_maturity") or 0) >= 70]
        data_asset_companies = [c for c in companies if (c.get("data_maturity") or 0) >= 70]
        high_probability = [c for c in companies if (c.get("opportunity_score") or 0) >= 80]

        content = (
            f"## 📡 企业信号 Intelligence 日报\n\n"
            f"> ⏰ {now}\n\n"
            "---\n\n"
            "### 📊 信号采集统计\n\n"
            f"- 招聘信号: {signal_types.get('recruitment', 0)} 个\n"
            f"- 新闻信号: {signal_types.get('news', 0)} 个\n"
            f"- 高管变动: {signal_types.get('executive', 0)} 个\n"
            f"- 政策信号: {signal_types.get('policy', 0)} 个\n"
            f"- **总计: {len(signals)} 个信号**\n\n"
            "---\n\n"
        )

        if strategic_companies:
            content += "### 🏛️ 战略 战略客户\n\n"
            for c in strategic_companies[:5]:
                content += f"> 🏢 **{c.get('company_name', '')}** | 商机评分: {c.get('opportunity_score', 'N/A')}\n\n"
            content += "\n"

        if ai_companies:
            content += "### 🤖 AI 建设企业\n\n"
            for c in ai_companies[:5]:
                content += f"> 🏢 **{c.get('company_name', '')}** | AI 成熟度: {c.get('ai_maturity', 'N/A')}/100\n\n"
            content += "\n"

        if data_asset_companies:
            content += "### 📦 数据资产化机会\n\n"
            for c in data_asset_companies[:5]:
                content += f"> 🏢 **{c.get('company_name', '')}** | 数据成熟度: {c.get('data_maturity', 'N/A')}/100\n\n"
            content += "\n"

        if high_probability:
            content += "### 🎯 高概率客户\n\n"
            for c in high_probability[:5]:
                content += (
                    f"> 🏢 **{c.get('company_name', '')}** | "
                    f"商机评分: {c.get('opportunity_score', 'N/A')} | "
                    f"推荐: {c.get('recommended_focus', '')}\n\n"
                )
            content += "\n"

        if policy_insights:
            content += "### 📋 政策洞察\n\n"
            content += f"> {policy_insights.get('summary', '')}\n\n"
            industries = policy_insights.get("affected_industries", [])
            if industries:
                content += f"> 受影响行业: {', '.join(industries)}\n\n"
            directions = policy_insights.get("exploding_direction", [])
            if directions:
                content += f"> 爆发方向: {', '.join(directions)}\n\n"

        content += (
            "---\n"
            f"*📡 企业信号 Intelligence · 灵爪 Nova v5*"
        )

        return {"msgtype": "markdown", "markdown": {"content": content}}

    def _build_strategic_customer_markdown(self, company: dict, reason: str) -> dict:
        """构建战略客户通知"""
        content = (
            "## 🏛️ 战略客户识别\n\n"
            f"### {company.get('company_name', '')}\n\n"
            f"> 📊 **商机评分:** {company.get('opportunity_score', 'N/A')}/100\n\n"
            f"> 🏭 **行业:** {company.get('industry', '未知')}\n\n"
            f"> 🎯 **推荐方向:** {company.get('recommended_focus', '')}\n\n"
            f"> 🏢 **推荐部门:** {company.get('recommended_department', '')}\n\n"
            f"> 📝 **策略:** {company.get('recommended_strategy', {}).get('strategy', '')}\n\n"
            f"> 💡 **识别理由:** {reason}\n\n"
            "---\n"
            f"*🏛️ 企业信号 Intelligence · 灵爪 Nova v5*"
        )
        return {"msgtype": "markdown", "markdown": {"content": content}}

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
                        f"[信号通知] 企业微信错误: errcode={resp_data.get('errcode')}"
                    )
                    return False
                logger.warning(f"[信号通知] HTTP {response.status_code}")
                return False
        except httpx.TimeoutException:
            logger.error("[信号通知] Webhook 超时")
            return False
        except Exception as e:
            logger.error(f"[信号通知] Webhook 异常: {e}")
            return False


# 全局单例
signal_notifier = SignalNotifier()