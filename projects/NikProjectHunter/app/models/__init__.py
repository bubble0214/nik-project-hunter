"""
Nik Project Hunter — 项目模型（第四阶段升级）

设计思路：
- 新增 Opportunity Intelligence Engine 字段
- 6 个商机 Intelligence 评分字段 + opportunity_level
- score_grade 字段存储 S/A/B/C 分级
- 高价值项目属性用于通知规则
"""

import datetime
import uuid
from sqlalchemy import Column, String, Text, DateTime, Float, Integer, JSON, func
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

# Re-export SalesOpportunity for convenience
from app.sales.models import SalesOpportunity


class Project(Base):
    """
    招投标项目模型（第四阶段）

    核心字段：
    - 基础信息: id, title, source_url, source, publish_date, budget, buyer, region
    - AI 分析: summary, analysis (10 维 + Opportunity Intelligence)
    - 评分: score, score_grade, score_reason
    - 商机 Intelligence (新增):
        - customer_maturity_score: 客户成熟度评分 (0-100)
        - long_term_value_score: 长期价值评分 (0-100)
        - industry_value_score: 行业价值评分 (0-100)
        - bidding_probability_score: 中标概率评分 (0-100)
        - business_difficulty_score: 商务难度评分 (0-100)
        - opportunity_level: 商机级别 (strategic / high_value / normal / low)
    - 状态: status
    - 时间戳: created_at, updated_at
    """
    __tablename__ = "projects"

    # =========================================================================
    # 基础信息
    # =========================================================================
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False, index=True)
    source_url = Column(String(2048), nullable=False, unique=True, index=True)
    source = Column(String(100), nullable=False, index=True)
    publish_date = Column(DateTime(timezone=True), nullable=True)
    budget = Column(Float, nullable=True)
    buyer = Column(String(300), nullable=True, index=True)
    region = Column(String(100), nullable=True)

    # =========================================================================
    # AI 分析字段
    # =========================================================================
    summary = Column(Text, nullable=True)
    analysis = Column(JSON, nullable=True)  # 10 维 + Opportunity Intelligence

    # =========================================================================
    # 评分字段
    # =========================================================================
    score = Column(Integer, nullable=True)  # 商机综合评分 0-100
    score_grade = Column(String(1), nullable=True, index=True)  # S/A/B/C
    score_reason = Column(Text, nullable=True)  # 评分理由 JSON

    # =========================================================================
    # Opportunity Intelligence Engine（新增第四阶段）
    # =========================================================================
    customer_maturity_score = Column(Integer, nullable=True)  # 客户成熟度 0-100
    long_term_value_score = Column(Integer, nullable=True)    # 长期价值 0-100
    industry_value_score = Column(Integer, nullable=True)     # 行业价值 0-100
    bidding_probability_score = Column(Integer, nullable=True) # 中标概率 0-100
    business_difficulty_score = Column(Integer, nullable=True)  # 商务难度 0-100
    opportunity_level = Column(String(20), nullable=True, index=True)  # strategic/high_value/normal/low

    # =========================================================================
    # 语义过滤字段（第五阶段新增）
    # =========================================================================
    semantic_category = Column(String(20), nullable=True, index=True)  # data_governance / data_security / data_asset / ai / none
    semantic_score = Column(Integer, nullable=True)                    # 语义相关性评分 0-100
    matched_signals = Column(JSON, nullable=True)                      # 匹配到的语义信号列表
    rejection_reason = Column(String(200), nullable=True)              # 如果被过滤，记录拒绝原因

    # =========================================================================
    # 项目阶段与时效性（第六阶段新增）
    # =========================================================================
    notice_type = Column(String(20), nullable=True, index=True)        # 意向采购/招标公告/招标公示/中标公告/废标公告/供应商征集/未知
    deadline = Column(DateTime(timezone=True), nullable=True)          # 标书获取截止日期（获取招标文件截止），null 表示未知
    bid_deadline = Column(DateTime(timezone=True), nullable=True)      # 投标截止日期（递交投标文件截止），null 表示未知

    # =========================================================================
    # 状态管理
    # =========================================================================
    status = Column(String(20), nullable=False, default="new", index=True)

    # =========================================================================
    # 原始数据
    # =========================================================================
    raw_html = Column(Text, nullable=True)

    # =========================================================================
    # 时间戳
    # =========================================================================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return (
            f"<Project(id={self.id}, "
            f"title={self.title[:50]}..., "
            f"score={self.score}, "
            f"grade={self.score_grade}, "
            f"opportunity={self.opportunity_level})>"
        )

    @property
    def grade_display(self) -> str:
        """评分等级显示"""
        if self.score_grade:
            return self.score_grade
        if self.score is not None:
            if self.score >= 85:
                return "S"
            elif self.score >= 70:
                return "A"
            elif self.score >= 50:
                return "B"
            else:
                return "C"
        return "N/A"

    @property
    def is_high_value(self) -> bool:
        """是否高价值项目（现阶段：所有项目都是高价值）"""
        return True

    @property
    def is_strategic(self) -> bool:
        """
        是否战略级项目

        定义：
        1. 国企/金融/政府/能源行业
        2. 预算 > 500 万
        3. 数据资产化或 AI 平台建设方向
        4. 长期运营类
        """
        if self.opportunity_level == "strategic":
            return True
        if not self.analysis:
            return False
        analysis = self.analysis if isinstance(self.analysis, dict) else {}
        budget_ok = (self.budget or 0) >= 5_000_000
        strategic_industry = analysis.get("industry_type", "") in ["国企", "金融", "政府", "能源"]
        strategic_dir = analysis.get("is_data_asset", False) or analysis.get("is_ai_project", False)
        long_term = analysis.get("is_long_track", False)
        return budget_ok and strategic_dir and long_term

    @property
    def is_semantically_relevant(self) -> bool:
        """是否通过语义相关性过滤"""
        if self.semantic_score is None:
            return True  # 未评估则默认通过
        return self.semantic_score >= 70

    @property
    def intelligence_summary(self) -> dict:
        """商机 Intelligence 摘要"""
        return {
            "customer_maturity": self.customer_maturity_score,
            "long_term_value": self.long_term_value_score,
            "industry_value": self.industry_value_score,
            "bidding_probability": self.bidding_probability_score,
            "business_difficulty": self.business_difficulty_score,
            "opportunity_level": self.opportunity_level,
        }


# =============================================================================
# 企业画像模型（第五阶段：企业信号 Intelligence 系统）
# =============================================================================


class Company(Base):
    """
    企业画像模型（第五阶段）

    存储 AI 分析后的企业画像数据，包括：
    - 数字化成熟度
    - AI 成熟度
    - 数据资产化成熟度
    - 最新信号摘要
    - 推荐销售策略
    """
    __tablename__ = "companies"

    # =========================================================================
    # 基础信息
    # =========================================================================
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(String(300), nullable=False, unique=True, index=True)
    industry = Column(String(100), nullable=True, index=True)

    # =========================================================================
    # 成熟度评估（0-100）
    # =========================================================================
    digital_maturity = Column(Integer, nullable=True)         # 数字化成熟度
    ai_maturity = Column(Integer, nullable=True)              # AI 成熟度
    data_maturity = Column(Integer, nullable=True)            # 数据资产化成熟度

    # =========================================================================
    # 商机价值评估
    # =========================================================================
    estimated_budget_level = Column(String(20), nullable=True)  # high / medium / low
    opportunity_score = Column(Integer, nullable=True)          # 商机总分 0-100
    strategic_level = Column(String(20), nullable=True)         # strategic / high_value / normal / low

    # =========================================================================
    # 最新信号摘要
    # =========================================================================
    latest_signal_summary = Column(Text, nullable=True)        # 最新信号摘要
    latest_signals = Column(JSON, nullable=True)               # 最近信号列表
    latest_signal_at = Column(DateTime(timezone=True), nullable=True)  # 最新信号时间

    # =========================================================================
    # 推荐策略（由 AI 生成）
    # =========================================================================
    recommended_strategy = Column(JSON, nullable=True)          # 推荐销售策略 JSON
    recommended_department = Column(String(100), nullable=True) # 推荐接触部门
    recommended_focus = Column(String(100), nullable=True)      # 推荐切入方向

    # =========================================================================
    # 画像更新时间
    # =========================================================================
    profile_updated_at = Column(DateTime(timezone=True), nullable=True)

    # =========================================================================
    # 元数据
    # =========================================================================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return (
            f"<Company(id={self.id}, "
            f"name={self.company_name}, "
            f"industry={self.industry}, "
            f"strategic={self.strategic_level})>"
        )

    @property
    def is_strategic_customer(self) -> bool:
        """是否战略客户"""
        if self.strategic_level == "strategic":
            return True
        if self.industry in ["国企", "金融", "政府", "能源", "医疗"] and \
           (self.estimated_budget_level == "high" or (self.opportunity_score or 0) >= 70):
            return True
        return False

    @property
    def profile_summary(self) -> dict:
        """企业画像摘要"""
        return {
            "company_name": self.company_name,
            "industry": self.industry,
            "digital_maturity": self.digital_maturity,
            "ai_maturity": self.ai_maturity,
            "data_maturity": self.data_maturity,
            "estimated_budget_level": self.estimated_budget_level,
            "opportunity_score": self.opportunity_score,
            "strategic_level": self.strategic_level,
            "is_strategic": self.is_strategic_customer,
        }


# =============================================================================
# 企业信号模型（第五阶段：企业信号 Intelligence 系统）
# =============================================================================


class EnterpriseSignal(Base):
    """
    企业信号模型（第五阶段）

    记录监听到的各种企业信号：
    - recruitment: 招聘信号
    - news: 新闻信号
    - executive: 高管变动信号
    - policy: 政策信号

    每个信号经过 AI 分析后，关联到对应企业。
    """
    __tablename__ = "enterprise_signals"

    # =========================================================================
    # 信号基础信息
    # =========================================================================
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_type = Column(String(20), nullable=False, index=True)  # recruitment / news / executive / policy
    company_name = Column(String(300), nullable=False, index=True)

    # =========================================================================
    # 信号来源
    # =========================================================================
    source_url = Column(String(2048), nullable=True)
    source_platform = Column(String(100), nullable=True)

    # =========================================================================
    # 信号内容
    # =========================================================================
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)           # 信号原始内容
    publish_date = Column(DateTime(timezone=True), nullable=True)

    # =========================================================================
    # AI 分析结果
    # =========================================================================
    analysis = Column(JSON, nullable=True)          # AI 分析结果 JSON
    signal_score = Column(Integer, nullable=True)   # 信号价值评分 0-100
    signal_level = Column(String(20), nullable=True)  # high / medium / low

    # =========================================================================
    # 关联企业（可选）
    # =========================================================================
    company_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)

    # =========================================================================
    # 状态
    # =========================================================================
    status = Column(String(20), nullable=False, default="new", index=True)  # new / analyzed / profiled

    # =========================================================================
    # 时间戳
    # =========================================================================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return (
            f"<EnterpriseSignal(id={self.id}, "
            f"type={self.signal_type}, "
            f"company={self.company_name}, "
            f"score={self.signal_score})>"
        )

    @property
    def analysis_summary(self) -> dict:
        """分析摘要"""
        if not self.analysis:
            return {}
        analysis = self.analysis if isinstance(self.analysis, dict) else {}
        return {
            "summary": analysis.get("summary", ""),
            "impact_level": analysis.get("impact_level", "low"),
            "is_project_starter": analysis.get("is_project_starter", False),
            "recommended_action": analysis.get("recommended_action", "观察"),
            "potential_budget": analysis.get("potential_budget", "未知"),
        }


# =============================================================================
# 采购意向模型（第六阶段：采购意向 Intelligence 系统）
# =============================================================================


class ProcurementIntention(Base):
    """
    采购意向模型（第六阶段）

    比正式招标更早发现商机。
    意向采购 = 项目刚进入立项/规划期，最具提前介入价值。

    核心 Intelligence 字段：
    - project_stage: 项目阶段（规划期/预算期/立项期/招标准备期）
    - engagement_window_score: 提前介入窗口评分 (0-100)
    - estimated_tender_date: 预计招标时间
    - annual_budget_signal: 年度预算信号（high/medium/low）
    - strategic_direction: 客户战略方向（数据战略/AI战略/数据安全/数据资产化）
    - future_opportunity_score: 未来商机评分 (0-100)
    """
    __tablename__ = "procurement_intentions"

    # =========================================================================
    # 基础信息
    # =========================================================================
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False, index=True)
    source_url = Column(String(2048), nullable=False, unique=True, index=True)
    source = Column(String(100), nullable=False, index=True)
    publish_date = Column(DateTime(timezone=True), nullable=True)
    buyer = Column(String(300), nullable=True, index=True)
    region = Column(String(100), nullable=True)
    estimated_budget = Column(Float, nullable=True)

    # =========================================================================
    # 意向内容字段
    # =========================================================================
    intention_content = Column(Text, nullable=True)
    annual_plan = Column(Text, nullable=True)
    construction_goal = Column(Text, nullable=True)
    technical_direction = Column(Text, nullable=True)
    budget_description = Column(Text, nullable=True)

    # =========================================================================
    # 项目阶段 Intelligence
    # =========================================================================
    project_stage = Column(String(20), nullable=True, index=True)
    estimated_tender_date = Column(DateTime(timezone=True), nullable=True)
    engagement_window_score = Column(Integer, nullable=True)

    # =========================================================================
    # 战略方向 Intelligence
    # =========================================================================
    annual_budget_signal = Column(String(10), nullable=True)
    strategic_direction = Column(String(50), nullable=True, index=True)
    strategic_directions = Column(JSON, nullable=True)

    # =========================================================================
    # 语义分析
    # =========================================================================
    semantic_category = Column(String(20), nullable=True, index=True)
    semantic_score = Column(Integer, nullable=True)
    matched_signals = Column(JSON, nullable=True)

    # =========================================================================
    # AI 分析
    # =========================================================================
    analysis = Column(JSON, nullable=True)

    # =========================================================================
    # 未来商机评分
    # =========================================================================
    future_opportunity_score = Column(Integer, nullable=True)
    opportunity_level = Column(String(20), nullable=True, index=True)

    # =========================================================================
    # 推荐销售策略
    # =========================================================================
    recommended_action = Column(Text, nullable=True)
    recommended_department = Column(String(100), nullable=True)
    sales_notes = Column(Text, nullable=True)

    # =========================================================================
    # 状态
    # =========================================================================
    status = Column(String(20), nullable=False, default="new", index=True)

    # =========================================================================
    # 时间戳
    # =========================================================================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return (
            f"<ProcurementIntention(id={self.id}, "
            f"title={self.title[:50]}..., "
            f"buyer={self.buyer}, "
            f"stage={self.project_stage}, "
            f"window={self.engagement_window_score}, "
            f"opportunity={self.opportunity_level})>"
        )

    @property
    def is_high_value(self) -> bool:
        if self.opportunity_level in ("strategic", "high_value"):
            return True
        if (self.future_opportunity_score or 0) >= 70:
            return True
        if (self.engagement_window_score or 0) >= 70:
            return True
        return False

    @property
    def window_description(self) -> str:
        score = self.engagement_window_score or 0
        if score >= 80:
            return "立即介入"
        elif score >= 60:
            return "本月内介入"
        elif score >= 40:
            return "1-3月内关注"
        else:
            return "长期跟踪"

    @property
    def stage_priority(self) -> int:
        priority = {"招标准备期": 1, "立项期": 2, "预算期": 3, "规划期": 4}
        return priority.get(self.project_stage or "", 5)

    def to_notification_dict(self) -> dict:
        return {
            "type": "采购意向",
            "title": self.title,
            "buyer": self.buyer,
            "project_stage": self.project_stage or "未知",
            "strategic_direction": self.strategic_direction or "未知",
            "estimated_budget": f"{self.estimated_budget/10000:.0f}万" if self.estimated_budget else "未知",
            "engagement_window": self.window_description,
            "estimated_tender_date": self.estimated_tender_date.strftime("%Y-%m") if self.estimated_tender_date else "待定",
            "opportunity_level": self.opportunity_level or "observation",
            "future_opportunity_score": self.future_opportunity_score,
            "recommended_action": self.recommended_action or "",
            "recommended_department": self.recommended_department or "",
            "source_url": self.source_url,
        }