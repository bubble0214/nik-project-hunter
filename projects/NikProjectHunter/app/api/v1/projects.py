"""
Nik Project Hunter — 项目 CRUD API

设计思路：
- RESTful 风格
- 分页查询支持
- 按状态、评分、来源、日期过滤
- 为未来 SaaS 多租户预留 tenant_id 过滤
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Project
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="最低评分"),
    source: Optional[str] = Query(None, description="按来源筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取项目列表（分页）
    """
    # 构建查询
    query = select(Project)

    if status:
        query = query.where(Project.status == status)
    if min_score is not None:
        query = query.where(Project.score >= min_score)
    if source:
        query = query.where(Project.source == source)
    if keyword:
        # Escape LIKE wildcards to prevent wildcard injection
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(Project.title.ilike(f"%{escaped}%", escape="\\"))

    # 按创建时间倒序
    query = query.order_by(desc(Project.created_at))

    # 总记录数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    projects = result.scalars().all()

    return ProjectListResponse(
        items=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取项目详情
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    return ProjectResponse.model_validate(project)


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    手动创建项目
    """
    # 检查重复
    result = await db.execute(
        select(Project).where(Project.source_url == project_data.source_url)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该项目已存在")

    project = Project(**project_data.model_dump())
    db.add(project)
    await db.flush()

    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    project_data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    更新项目
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    for field, value in project_data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    await db.flush()
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    删除项目
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    await db.delete(project)