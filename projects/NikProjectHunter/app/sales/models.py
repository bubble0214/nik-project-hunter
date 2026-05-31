"""
Nik Project Hunter — AI 销售副驾驶系统（第六阶段）

数据库模型：

1. SalesOpportunity — 销售商机表（核心销售数据）
   - 关联 Project 和 Company
   - 存储 AI 销售策略分析结果
   - 跟进建议和客户关系状态
"""

import datetime
import uuid
from sqlalchemy import Column, String, Text, DateTime, Float, Integer, JSON, func
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class SalesOpportunity(Base):
    """
    销售商机模型（第六阶段）

    存储 AI 销售副驾驶系统的核心数据：
    - 销售策略分析结果
    - 跟进建议
    - 客户关系状态
    - AI 销售摘要

    每个项目 + 企业组合对应一个 SalesOpportunity 记录。
    """
    __tablename__ = "sales_opportunities"

    # =========================================================================
    # 基础信息
    # =========================================================================
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 关联项目（可选 — 项目级别的销售策略）
    project_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # 关联企业（可选 — 企业级别的销售策略）
    company_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # 名称（项目名或企业名）
    company_name = Column(String(300), nullable=False, index=True)

    # =========================================================================
    # 销售阶段（Sixth Phase — Relationship Intelligence）
    # =========================================================================
    sales_stage = Column(String(30), nullable=True, index=True)
    # 可选值:
    #   research       — 调研阶段
    #   budget         — 预算阶段
    #   project_init   — 立项阶段
    #   bidding        — 招标阶段
    #   implementation — 实施阶段

    # =========================================================================
    # Sales Strategy Engine 输出（第六阶段 — 核心）
    # =========================================================================

    # 1. 最佳切入部门
    best_entry_department = Column(String(100), nullable=True)
    # 如: 信息中心 / 数据管理部 / 数字化办公室 / CIO办公室 / 数据资产部门

    # 2. 推荐销售路径
    recommended_sales_path = Column(JSON, nullable=True)
    # {
    #   "first_contact": "信息中心负责人",
    #   "second_push": "数据管理部部长",
    #   "final_decision": "CIO / 分管副总"
    # }

    # 3. 推荐切入话术
    recommended_pitch = Column(Text, nullable=True)
    # AI 自动生成的销售切入话术

    # 4. 推荐产品方案
    recommended_solution = Column(String(100), nullable=True)
    # 可选值: 数据治理 / 数据资产 / AI 平台 / 数据安全 / 数据运营

    # 5. 推荐销售策略
    recommended_strategy = Column(String(30), nullable=True)
    # 可选值: 顾问式销售 / 方案型销售 / 关系型销售 / 长周期运营

    # 6. 推荐项目优先级
    project_priority = Column(String(20), nullable=True, index=True)
    # 可选值: immediate / this_week / long_term / hold

    # =========================================================================
    # Follow-up Engine 输出（第六阶段）
    # =========================================================================

    # 首次沟通建议
    first_contact_advice = Column(Text, nullable=True)

    # 电话沟通建议
    phone_call_advice = Column(Text, nullable=True)

    # 微信沟通建议
    wechat_advice = Column(Text, nullable=True)

    # 邮件标题建议
    email_subject_suggestion = Column(String(300), nullable=True)

    # 邮件正文建议
    email_body_suggestion = Column(Text, nullable=True)

    # PPT 方案建议
    ppt_suggestion = Column(Text, nullable=True)

    # =========================================================================
    # Relationship Intelligence 输出（第六阶段）
    # =========================================================================

    # 客户当前阶段（详细描述）
    customer_stage_detail = Column(Text, nullable=True)

    # 推荐动作
    recommended_action = Column(String(100), nullable=True)
    # 如: 打电话 / 发方案 / 约拜访 / 建立关系 / 推案例

    # 客户风险
    relationship_risk = Column(JSON, nullable=True)
    # {
    #   "has_existing_vendor": true/false,
    #   "competition_intensity": "high"/"medium"/"low",
    #   "has_rigged_bid_risk": true/false,
    #   "risk_level": "high"/"medium"/"low"
    # }

    # =========================================================================
    # 下一步跟进时间
    # =========================================================================
    next_followup_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # =========================================================================
    # AI 销售摘要
    # =========================================================================
    ai_sales_summary = Column(Text, nullable=True)
    # AI 综合生成的销售建议摘要

    # =========================================================================
    # 元数据
    # =========================================================================

    # 销售策略生成时间
    strategy_generated_at = Column(DateTime(timezone=True), nullable=True)

    # 跟进建议生成时间
    followup_generated_at = Column(DateTime(timezone=True), nullable=True)

    # 关系分析生成时间
    relationship_analyzed_at = Column(DateTime(timezone=True), nullable=True)

    # =========================================================================
    # 时间戳
    # =========================================================================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return (
            f"<SalesOpportunity(id={self.id}, "
            f"company={self.company_name}, "
            f"stage={self.sales_stage}, "
            f"priority={self.project_priority})>"
        )

    @property
    def priority_display(self) -> str:
        """优先级中文显示"""
        display_map = {
            "immediate": "🔴 立即跟进",
            "this_week": "🟡 本周跟进",
            "long_term": "🟢 长期培养",
            "hold": "⚪ 暂不跟进",
        }
        return display_map.get(self.project_priority, "⚪ 待评估")

    @property
    def stage_display(self) -> str:
        """阶段中文显示"""
        display_map = {
            "research": "🔍 调研阶段",
            "budget": "💰 预算阶段",
            "project_init": "📋 立项阶段",
            "bidding": "🏛️ 招标阶段",
            "implementation": "🔧 实施阶段",
        }
        return display_map.get(self.sales_stage, "❓ 未知阶段")

    @property
    def risk_display(self) -> str:
        """风险中文显示"""
        if not self.relationship_risk:
            return "✅ 未评估"
        risk = self.relationship_risk if isinstance(self.relationship_risk, dict) else {}
        level = risk.get("risk_level", "unknown")
        display_map = {
            "high": "🔴 高风险",
            "medium": "🟡 中等风险",
            "low": "🟢 低风险",
            "unknown": "⚪ 未知",
        }
        return display_map.get(level, "⚪ 未知")

    @property
    def sales_summary(self) -> dict:
        """销售摘要（供 API 使用）"""
        return {
            "id": str(self.id),
            "company_name": self.company_name,
            "project_id": str(self.project_id) if self.project_id else None,
            "company_id": str(self.company_id) if self.company_id else None,
            "sales_stage": self.sales_stage,
            "stage_display": self.stage_display,
            "best_entry_department": self.best_entry_department,
            "recommended_sales_path": self.recommended_sales_path,
            "recommended_pitch": self.recommended_pitch,
            "recommended_solution": self.recommended_solution,
            "recommended_strategy": self.recommended_strategy,
            "project_priority": self.project_priority,
            "priority_display": self.priority_display,
            "first_contact_advice": self.first_contact_advice,
            "phone_call_advice": self.phone_call_advice,
            "wechat_advice": self.wechat_advice,
            "email_subject_suggestion": self.email_subject_suggestion,
            "email_body_suggestion": self.email_body_suggestion,
            "ppt_suggestion": self.ppt_suggestion,
            "customer_stage_detail": self.customer_stage_detail,
            "recommended_action": self.recommended_action,
            "relationship_risk": self.relationship_risk,
            "risk_display": self.risk_display,
            "next_followup_at": (
                self.next_followup_at.isoformat() if self.next_followup_at else None
            ),
            "ai_sales_summary": self.ai_sales_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }