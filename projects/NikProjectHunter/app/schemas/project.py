"""
Nik Project Hunter — Pydantic Schemas

设计思路：
- 请求/响应分离，不直接暴露 ORM 模型
- 未来扩展：每个 schema 增加 tenant_id 字段
- Create/Update/Response 三层分离
"""

import datetime
import uuid
from typing import Optional
from pydantic import BaseModel, Field


# =============================================================================
# 项目相关 Schema
# =============================================================================


class ProjectCreate(BaseModel):
    """创建项目请求"""
    title: str = Field(..., max_length=500, description="项目标题")
    source_url: str = Field(..., max_length=2048, description="原始 URL")
    source: str = Field(..., max_length=100, description="来源网站")
    publish_date: Optional[datetime.datetime] = None
    budget: Optional[float] = None
    buyer: Optional[str] = Field(None, max_length=300)
    region: Optional[str] = Field(None, max_length=100)
    raw_html: Optional[str] = None


class ProjectUpdate(BaseModel):
    """更新项目请求（部分更新）"""
    title: Optional[str] = None
    summary: Optional[str] = None
    analysis: Optional[dict] = None
    score: Optional[int] = Field(None, ge=0, le=100)
    score_reason: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    """项目响应（第四阶段）"""
    id: uuid.UUID
    title: str
    source_url: str
    source: str
    publish_date: Optional[datetime.datetime] = None
    budget: Optional[float] = None
    buyer: Optional[str] = None
    region: Optional[str] = None
    summary: Optional[str] = None
    analysis: Optional[dict] = None
    score: Optional[int] = None
    score_grade: Optional[str] = None
    score_reason: Optional[str] = None
    status: str
    is_high_value: bool = False
    # Opportunity Intelligence（第四阶段新增）
    customer_maturity_score: Optional[int] = None
    long_term_value_score: Optional[int] = None
    industry_value_score: Optional[int] = None
    bidding_probability_score: Optional[int] = None
    business_difficulty_score: Optional[int] = None
    opportunity_level: Optional[str] = None
    intelligence_summary: Optional[dict] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj):
        """重写 model_validate 以添加计算字段"""
        data = super().model_validate(obj)
        if hasattr(obj, 'is_high_value'):
            data.is_high_value = obj.is_high_value
        elif obj.score_grade:
            data.is_high_value = obj.score_grade == 'S' or (obj.score_grade == 'A' and obj.score is not None and obj.score >= 75)
        if hasattr(obj, 'intelligence_summary'):
            data.intelligence_summary = obj.intelligence_summary
        elif hasattr(obj, 'customer_maturity_score'):
            data.intelligence_summary = {
                "customer_maturity": obj.customer_maturity_score,
                "long_term_value": obj.long_term_value_score,
                "industry_value": obj.industry_value_score,
                "bidding_probability": obj.bidding_probability_score,
                "business_difficulty": obj.business_difficulty_score,
                "opportunity_level": obj.opportunity_level,
            }
        return data


class ProjectListResponse(BaseModel):
    """项目列表响应"""
    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# 分析相关 Schema
# =============================================================================


class AnalysisRequest(BaseModel):
    """手动触发分析请求"""
    project_id: uuid.UUID


class AnalysisResult(BaseModel):
    """AI 分析结果"""
    summary: str = Field(..., description="项目摘要")
    category: str = Field(..., description="项目类别")
    relevance: str = Field(..., description="与公司业务的关联度")
    strengths: list[str] = Field(default_factory=list, description="我方优势")
    risks: list[str] = Field(default_factory=list, description="风险点")
    recommended_action: str = Field(..., description="建议行动")


class ScoreResult(BaseModel):
    """评分结果"""
    score: int = Field(..., ge=0, le=100, description="商机评分 0-100")
    reason: str = Field(..., description="评分理由")
    dimensions: dict = Field(default_factory=dict, description="各维度得分")


# =============================================================================
# 爬虫相关 Schema
# =============================================================================


class CrawlRequest(BaseModel):
    """手动触发爬取请求"""
    url: str = Field(..., description="要爬取的 URL")
    source: str = Field(..., description="来源名称")


class CrawlResponse(BaseModel):
    """爬取响应"""
    projects_created: int
    projects: list[ProjectResponse]
    total_found: int
    elapsed_seconds: float