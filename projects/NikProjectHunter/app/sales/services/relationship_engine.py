"""
Nik Project Hunter — Relationship Intelligence Engine（第六阶段）

AI 客户关系智能引擎 — 分析客户关系和推荐动作：

1. 客户当前阶段 — 调研 / 预算 / 立项 / 招标 / 实施
2. 推荐动作 — 打电话 / 发方案 / 约拜访 / 建立关系 / 推案例
3. 客户风险 — 已有供应商 / 竞争激烈 / 陪标风险

设计原则：
- 基于项目数据和信号数据综合分析
- 输出可执行的下一步动作
- 风险判断帮助销售团队规避坑位
"""

from datetime import datetime, timezone
from typing import Optional
from loguru import logger

from app.config import get_settings
from app.core.ai_client import ai_client
from app.models import Project, Company, EnterpriseSignal


class RelationshipIntelligenceEngine:
    """
    客户关系智能引擎

    分析客户当前阶段、推荐下一步动作、判断客户风险。
    """

    # 销售阶段定义
    SALES_STAGES = [
        "research",
        "budget",
        "project_init",
        "bidding",
        "implementation",
    ]

    # 推荐动作定义
    RECOMMENDED_ACTIONS = [
        "打电话",
        "发方案",
        "约拜访",
        "建立关系",
        "推案例",
    ]

    async def analyze_relationship(
        self,
        project: Optional[Project] = None,
        company: Optional[Company] = None,
        signals: Optional[list[EnterpriseSignal]] = None,
    ) -> dict:
        """
        分析客户关系和推荐动作

        Args:
            project: 项目对象（可选）
            company: 企业对象（可选）
            signals: 企业信号列表（可选）

        Returns:
            {
                "sales_stage": str,                   # 客户当前阶段
                "customer_stage_detail": str,         # 阶段详细说明
                "recommended_action": str,            # 推荐动作
                "relationship_risk": {
                    "has_existing_vendor": bool,       # 是否已有供应商
                    "competition_intensity": str,      # 竞争激烈程度
                    "has_rigged_bid_risk": bool,       # 是否陪标风险
                    "risk_level": str,                 # 总体风险等级
                    "risk_detail": str,                # 风险详细说明
                },
                "relationship_analyzed_at": str,      # 分析时间
            }
        """
        logger.info(
            f"[RelIntel] 开始分析客户关系: "
            f"company={company.company_name if company else 'N/A'}"
        )

        # 构建 AI prompt
        prompt = self._build_relationship_prompt(project, company, signals)

        try:
            # 调用 AI（强制 JSON 输出）
            result = await ai_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": self._get_relationship_system_prompt(),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )

            # 解析 AI 输出
            analysis = self._parse_ai_response(result)

            # 添加元数据
            analysis["relationship_analyzed_at"] = datetime.now(timezone.utc).isoformat()

            logger.info(
                f"[RelIntel] 关系分析完成 | "
                f"阶段={analysis['sales_stage']} | "
                f"动作={analysis['recommended_action']} | "
                f"风险={analysis.get('relationship_risk', {}).get('risk_level', 'unknown')}"
            )

            return analysis

        except Exception as e:
            logger.error(f"[RelIntel] 关系分析异常: {e}")
            return self._get_default_analysis()

    def _get_relationship_system_prompt(self) -> str:
        """获取关系分析系统提示词"""
        return (
            "你是一位资深的企业级销售顾问，擅长 ToB 大客户关系管理和销售阶段判断。\n\n"
            "你的任务：\n"
            "1. 根据项目信息和信号数据，判断客户当前所处的销售阶段\n"
            "2. 推荐销售团队下一步应该执行的具体动作\n"
            "3. 识别客户关系风险（已有供应商、竞争激烈度、陪标风险）\n\n"
            f"销售阶段选项: {', '.join(self.SALES_STAGES)}\n"
            f"推荐动作选项: {', '.join(self.RECOMMENDED_ACTIONS)}\n\n"
            "输出必须为 JSON 格式。"
        )

    def _build_relationship_prompt(
        self,
        project: Optional[Project],
        company: Optional[Company],
        signals: Optional[list[EnterpriseSignal]],
    ) -> str:
        """构建关系分析 prompt"""
        parts = ["请分析以下客户的销售关系：\n"]

        # 项目信息
        if project:
            parts.append(f"## 项目信息")
            parts.append(f"- 项目名称: {project.title}")
            parts.append(f"- 采购单位: {project.buyer or '未知'}")
            parts.append(f"- 预算: {project.budget or '未知'}")
            parts.append(f"- 发布日期: {project.publish_date or '未知'}")
            if project.analysis:
                analysis = project.analysis if isinstance(project.analysis, dict) else {}
                parts.append(f"- 行业类型: {analysis.get('industry_type', '未知')}")
                parts.append(f"- 项目类型: {analysis.get('project_type', '未知')}")

        # 企业信息
        if company:
            parts.append(f"\n## 企业画像")
            parts.append(f"- 企业名称: {company.company_name}")
            parts.append(f"- 行业: {company.industry or '未知'}")
            parts.append(f"- 战略级别: {company.strategic_level or '未知'}")

        # 信号数据
        if signals:
            parts.append(f"\n## 企业信号")
            for s in signals[:5]:  # 最多取 5 条
                parts.append(f"- [{s.signal_type}] {s.title[:100]}")
                if s.analysis:
                    sig_analysis = s.analysis if isinstance(s.analysis, dict) else {}
                    parts.append(f"  分析: {sig_analysis.get('summary', '')[:100]}")
                    parts.append(f"  影响: {sig_analysis.get('impact_level', 'low')}")

        parts.append(f"\n## 要求输出 JSON")
        parts.append("{")
        parts.append('  "sales_stage": "客户当前阶段（从销售阶段选项选一个）",')
        parts.append('  "customer_stage_detail": "阶段详细说明（30-100字）",')
        parts.append('  "recommended_action": "推荐动作（从推荐动作选项选一个）",')
        parts.append('  "relationship_risk": {')
        parts.append('    "has_existing_vendor": true/false,')
        parts.append('    "competition_intensity": "high/medium/low",')
        parts.append('    "has_rigged_bid_risk": true/false,')
        parts.append('    "risk_level": "high/medium/low",')
        parts.append('    "risk_detail": "风险详细说明（20-100字）"')
        parts.append("  }")
        parts.append("}")

        return "\n".join(parts)

    def _parse_ai_response(self, ai_result: str) -> dict:
        """解析 AI 响应为结构化分析"""
        import json

        try:
            if isinstance(ai_result, dict):
                data = ai_result
            else:
                text = ai_result.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[-1]
                    text = text.rsplit("```", 1)[0]
                data = json.loads(text)

            # 验证必要字段
            if "sales_stage" not in data:
                data["sales_stage"] = "research"

            if "recommended_action" not in data:
                data["recommended_action"] = "打电话"

            if "relationship_risk" not in data:
                data["relationship_risk"] = {
                    "has_existing_vendor": False,
                    "competition_intensity": "low",
                    "has_rigged_bid_risk": False,
                    "risk_level": "low",
                    "risk_detail": "暂无数据",
                }

            # 验证枚举值
            if data["sales_stage"] not in self.SALES_STAGES:
                data["sales_stage"] = "research"

            if data["recommended_action"] not in self.RECOMMENDED_ACTIONS:
                data["recommended_action"] = "打电话"

            # 验证风险结构
            risk = data.get("relationship_risk", {})
            if not isinstance(risk, dict):
                risk = {}
            risk.setdefault("has_existing_vendor", False)
            risk.setdefault("competition_intensity", "low")
            risk.setdefault("has_rigged_bid_risk", False)
            risk.setdefault("risk_level", "low")
            risk.setdefault("risk_detail", "")
            data["relationship_risk"] = risk

            if "customer_stage_detail" not in data:
                data["customer_stage_detail"] = "暂无详细分析"

            return data

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"[RelIntel] AI 响应解析失败: {e}")
            return self._get_default_analysis()

    def _get_default_analysis(self) -> dict:
        """获取默认关系分析"""
        return {
            "sales_stage": "research",
            "customer_stage_detail": "建议先通过公开信息了解客户当前状态",
            "recommended_action": "打电话",
            "relationship_risk": {
                "has_existing_vendor": False,
                "competition_intensity": "low",
                "has_rigged_bid_risk": False,
                "risk_level": "low",
                "risk_detail": "暂无风险数据，建议主动了解",
            },
            "relationship_analyzed_at": datetime.now(timezone.utc).isoformat(),
        }


# 全局单例
relationship_intelligence_engine = RelationshipIntelligenceEngine()