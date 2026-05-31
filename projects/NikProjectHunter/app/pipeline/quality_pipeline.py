"""
Nik Project Hunter — Data Quality Sprint Pipeline

DataOps Engineer Mode:
1. 精准行业关键词过滤（代替宽泛的"采购/招标/项目"）
2. LLM relevance filter（AI 二次过滤）
3. 质量评分系统
4. 噪声清理
5. 日志统计
"""

import json
import re
from datetime import datetime
from typing import Optional
from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project
from app.core.ai_client import ai_client
from app.pipeline.pipeline import Pipeline
from app.services.semantic_filter import semantic_filter, SemanticFilterService
from app.core.constants import KEYWORDS_DATA_SECURITY


# 精准关键词（从 constants 导入）
PRECISION_KEYWORDS = {
    "data_security": KEYWORDS_DATA_SECURITY,  # 仅 3 个: 数据安全、数据分类分级、等保测评
}

# 所有关键词（用于快速匹配）
ALL_PRECISION_KEYWORDS = list(KEYWORDS_DATA_SECURITY)

# 噪声关键词（命中即丢弃）
NOISE_KEYWORDS = [
    "办公用品", "办公家具", "办公设备", "办公耗材", "办公用纸",
    "文具", "打印机", "复印机", "墨盒", "硒鼓",
    "空调", "电梯", "装修", "保洁", "物业",
    "绿化", "餐饮", "食品", "食材", "蔬菜",
    "车辆", "汽车", "轮胎", "汽油", "柴油",
    "服装", "制服", "工装", "鞋帽", "劳保",
    "工程", "施工", "土建", "装修", "修缮",
    "UPS", "发电机", "配电柜", "配电箱", "电缆",
    "照明", "灯具", "卫浴", "门窗", "地板",
    "食堂", "宿舍", "体育馆", "操场",
    "印刷", "广告", "宣传", "设计", "制作",
    "搬家", "运输", "物流", "快递", "仓储",
    "保洁", "保安", "绿化养护",
    "保险", "理赔", "存款", "贷款",
]


class QualityPipeline:
    """
    数据质量管道（Data Quality Sprint）

    流程：
    raw_data -> clean -> noise_filter -> precision_keyword_filter -> llm_relevance_filter -> dedup -> store
    """

    def __init__(self):
        self.base_pipeline = Pipeline()

    # ==================================================================
    # 公告类型识别
    # ==================================================================
    def _extract_notice_type(self, title: str, content: str) -> str:
        """
        从标题和内容中识别公告类型。
        优先级：意向采购 > 供应商征集 > 招标公告 > 招标公示 > 废标公告 > 中标公告 > 未知
        """
        text = (title + " " + (content or ""))[:500]

        # 采购意向
        if re.search(r'采购意向|政府采购意向|意向公告', text):
            return '意向采购'
        # 供应商征集
        if re.search(r'供应商征集|征集公告|供应商调研|调研公告', text):
            return '供应商征集'
        # 废标/流标
        if re.search(r'废标|流标|终止', text):
            return '废标公告'
        # 中标/成交
        if re.search(r'中标公告|成交公告|结果公告|中标候选|中标结果|成交结果', text):
            return '中标公告'
        # 招标公告
        if re.search(r'招标公告|公开招标|竞争性磋商|竞争性谈判|询价公告|单一来源', text):
            return '招标公告'
        # 招标公示/候选人
        if re.search(r'候选人公示|评标结果|中标公示|资格预审', text):
            return '招标公示'

        return '未知'

    # ==================================================================
    # 截止日期提取
    # ==================================================================
    def _extract_deadline(self, content: str, raw_html: str) -> tuple:
        """
        从内容中提取标书获取截止日期和投标截止日期。

        Returns:
            (deadline: 标书获取截止, bid_deadline: 投标截止)
        """
        import re
        import datetime

        text = (content or "") + " " + (raw_html or "")
        text = re.sub(r'<[^>]+>', ' ', text)

        deadline = None      # 标书获取截止
        bid_deadline = None  # 投标截止

        # 模式 1：带关键词的精确匹配
        patterns = [
            # 标书获取相关
            (r'(?:获取招标文件|文件获取|采购文件获取|报名截止|购买招标文件|获取采购文件)[^\d]*?(\d{4}[-年]\d{1,2}[-月]\d{1,2})\s*(\d{1,2}:\d{2})?', 'deadline'),
            # 投标截止相关
            (r'(?:投标截止|递交投标文件|提交投标文件|投标文件递交|响应文件提交|递交响应文件|响应文件递交|开标时间)[^\d]*?(\d{4}[-年]\d{1,2}[-月]\d{1,2})\s*(\d{1,2}:\d{2})?', 'bid'),
            # 通用截止（无前缀时，默认为投标截止）
            (r'(?:截止时间|提交截止|递交截止)[^\d]*?(\d{4}[-年]\d{1,2}[-月]\d{1,2})\s*(\d{1,2}:\d{2})?', 'bid'),
        ]

        def _parse_date(date_str: str, time_str: str = '23:59'):
            ds = date_str.replace('年', '-').replace('月', '-').replace('日', '')
            try:
                return datetime.datetime.strptime(f"{ds} {time_str}", "%Y-%m-%d %H:%M")
            except ValueError:
                return None

        for pattern, field in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                dt = _parse_date(match.group(1), match.group(2) or '23:59')
                if dt:
                    if field == 'deadline' and deadline is None:
                        deadline = dt
                    elif field == 'bid' and bid_deadline is None:
                        bid_deadline = dt

        # 模式 2：如果没找到标书获取截止，尝试从"获取文件时间"格式匹配
        if deadline is None:
            # 常见格式：获取时间：2026年05月28日 至 2026年06月03日
            range_match = re.search(r'获取[^。]*?\d{4}年\d{1,2}月\d{1,2}日[^。]*?至\s*(\d{4}年\d{1,2}月\d{1,2}日)', text)
            if range_match:
                deadline = _parse_date(range_match.group(1))

        return deadline, bid_deadline

    async def process(
        self,
        raw_projects: list[dict],
        source_platform: str,
        session: AsyncSession,
        run_llm_filter: bool = True,
        run_semantic_filter: bool = True,
    ) -> dict:
        stats = {
            "total": len(raw_projects),
            "cleaned": 0,
            "keyword_filtered": 0,
            "noise_filtered": 0,
            "llm_filtered": 0,
            "semantic_filtered": 0,  # 新增：语义过滤计数
            "duplicates": 0,
            "new": 0,
            "quality_scores": [],
        }

        # 收集所有需要语义过滤的项目
        semantic_candidates = []

        for raw in raw_projects:
            cleaned = self._clean(raw)
            if not cleaned:
                continue
            stats["cleaned"] += 1

            if self._noise_filter(cleaned):
                stats["noise_filtered"] += 1
                continue

            kw_match = self._precision_keyword_filter(cleaned)
            if not kw_match["passed"]:
                stats["keyword_filtered"] += 1
                continue

            quality_score = self._calculate_quality_score(cleaned, kw_match)
            stats["quality_scores"].append(quality_score)

            if run_llm_filter:
                llm_result = await self._llm_relevance_filter(cleaned)
                if not llm_result["relevant"]:
                    stats["llm_filtered"] += 1
                    continue
                quality_score = max(quality_score, llm_result["quality_score"])
                cleaned["llm_category"] = llm_result["category"]
                cleaned["llm_reason"] = llm_result["reason"]
                cleaned["data_quality_score"] = quality_score
            else:
                cleaned["data_quality_score"] = quality_score

            # 收集用于语义过滤（批量处理，减少 AI 调用）
            semantic_candidates.append(cleaned)

        # ================================================================
        # 语义级相关性分析（所有项目入库，仅记录分析结果）
        # ================================================================
        if run_semantic_filter and semantic_candidates:
            semantic_results = await semantic_filter.analyze_batch(semantic_candidates)

            for i, (cleaned, sem_result) in enumerate(zip(semantic_candidates, semantic_results)):
                # 更新 cleaned 数据（所有项目都入库，不拒绝）
                cleaned["semantic_category"] = sem_result.get("category", "unknown")
                cleaned["semantic_score"] = sem_result.get("relevance_score", 0)
                cleaned["opportunity_level"] = sem_result.get("opportunity_level", "observation")
                cleaned["matched_signals"] = sem_result.get("matched_signals", [])
                cleaned["rejection_reason"] = ""

        # ================================================================
        # 存储通过所有过滤的项目
        # ================================================================
        for cleaned in semantic_candidates:
            success = await self._store(cleaned, session)
            if success:
                stats["new"] += 1
            else:
                stats["duplicates"] += 1

        return stats

    # ======================================================================
    # 1. 数据清洗
    # ======================================================================

    def _clean(self, raw: dict) -> Optional[dict]:
        try:
            cleaned = {}
            title = raw.get("title", "").strip()
            if not title or len(title) < 5:
                return None
            if re.match(r"^[\d\s\-_./\\()（）\[\]]+$", title):
                return None
            cleaned["title"] = title

            source_url = raw.get("source_url", "").strip()
            if not source_url:
                return None
            cleaned["source_url"] = source_url
            # source_platform 兜底：如果 raw 没有（如 ChinaZFCG 旧版），用 process() 入参
            sp = raw.get("source_platform", "")
            if not sp:
                sp = source_platform  # 由 SpiderManager.crawl_all() 传入
            cleaned["source_platform"] = sp

            publish_date = raw.get("publish_date")
            if isinstance(publish_date, str):
                import datetime
                for fmt in [
                    "%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日",
                    "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M",
                ]:
                    try:
                        publish_date = datetime.datetime.strptime(publish_date, fmt)
                        break
                    except ValueError:
                        continue
            cleaned["publish_date"] = publish_date

            region = raw.get("region")
            if region:
                region = region.strip()
            cleaned["region"] = region
            buyer = raw.get("buyer")
            if buyer:
                buyer = buyer.strip()
            cleaned["buyer"] = buyer

            budget = raw.get("budget")
            if budget is not None:
                try:
                    budget = float(budget)
                except (ValueError, TypeError):
                    budget = None
            cleaned["budget"] = budget

            # ============================================================
            # 公告类型识别
            # ============================================================
            notice_type = self._extract_notice_type(title, raw.get("content", ""))
            cleaned["notice_type"] = notice_type

            # ============================================================
            # 截止日期提取（标书获取截止 + 投标截止）
            # ============================================================
            deadline, bid_deadline = self._extract_deadline(raw.get("content", ""), raw.get("raw_html", ""))
            cleaned["deadline"] = deadline
            cleaned["bid_deadline"] = bid_deadline

            content = raw.get("content", "")
            if content:
                content = re.sub(r"<[^>]+>", "", content)
                content = content.strip()[:10000]
            cleaned["content"] = content

            raw_html = raw.get("raw_html", "")
            if raw_html:
                raw_html = raw_html[:50000]
            cleaned["raw_html"] = raw_html
            return cleaned
        except Exception as e:
            logger.warning(f"[Quality] 数据清洗失败: {e}")
            return None

    # ======================================================================
    # 2. 噪声过滤
    # ======================================================================

    def _noise_filter(self, project: dict) -> bool:
        title = project.get("title", "")
        content = project.get("content", "")
        for keyword in NOISE_KEYWORDS:
            if keyword in title:
                logger.debug(f"[Quality] 噪声过滤: [{keyword}] {title[:60]}")
                return True
        if content:
            for keyword in NOISE_KEYWORDS:
                if keyword in content[:300]:
                    logger.debug(f"[Quality] 噪声过滤(内容): [{keyword}] {title[:60]}")
                    return True
        return False

    # ======================================================================
    # 3. 精准关键词过滤
    # ======================================================================

    def _precision_keyword_filter(self, project: dict) -> dict:
        title = project.get("title", "")
        content = project.get("content", "")

        result = {
            "passed": False, "matched_keywords": [],
            "categories": [], "match_count": 0, "match_scope": "",
        }

        title_matched = []
        for category, keywords in PRECISION_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in title.lower():
                    title_matched.append((category, keyword))

        content_matched = []
        if content:
            preview = content[:500]
            for category, keywords in PRECISION_KEYWORDS.items():
                for keyword in keywords:
                    if keyword.lower() in preview.lower():
                        content_matched.append((category, keyword))

        all_matches = title_matched + content_matched
        if not all_matches:
            return result

        cats = set()
        kws = []
        for cat, kw in all_matches:
            cats.add(cat)
            if kw not in kws:
                kws.append(kw)

        result["passed"] = True
        result["matched_keywords"] = kws
        result["categories"] = list(cats)
        result["match_count"] = len(all_matches)
        result["match_scope"] = "both" if title_matched and content_matched else ("title" if title_matched else "content")
        return result

    # ======================================================================
    # 4. 质量评分 (0-100)
    # ======================================================================

    def _calculate_quality_score(self, project: dict, kw_match: dict) -> int:
        score = 0
        # 关键词匹配度 (0-40)
        kw_score = 0
        if kw_match.get("passed"):
            kw_score = 20
            kw_score += min(kw_match.get("match_count", 0) * 5, 10)
            cats = kw_match.get("categories", [])
            if len(cats) >= 2:
                kw_score += 5
            if len(cats) >= 3:
                kw_score += 5
        score += min(kw_score, 40)

        # 标题质量 (0-20)
        title = project.get("title", "")
        ts = 0
        if len(title) >= 15:
            ts += 10
        elif len(title) >= 10:
            ts += 5
        if any(k in title for k in ["采购", "招标", "项目", "公告"]):
            ts += 5
        if any(k in title for k in ["银行", "保险", "证券", "政府", "医院", "集团"]):
            ts += 5
        score += min(ts, 20)

        # 内容完整度 (0-20)
        content = project.get("content", "")
        cs = 0
        if content and len(content) > 200:
            cs += 10
        elif content and len(content) > 50:
            cs += 5
        if project.get("buyer"):
            cs += 5
        if project.get("budget") is not None:
            cs += 5
        score += min(cs, 20)

        # 时效性 (0-20)
        if project.get("publish_date"):
            score += 20

        return min(score, 100)

    # ======================================================================
    # 5. LLM Relevance Filter
    # ======================================================================

    async def _llm_relevance_filter(self, project: dict) -> dict:
        title = project.get("title", "")
        content = project.get("content", "")[:800]

        prompt = f"""你是一个专业的数据智能/AI 行业分析师。请判断以下招投标项目是否与以下四个领域相关：

1. 数据治理 — 包括：数据治理平台、主数据管理、数据中台、元数据、数据质量、数据标准、数据架构、数据湖、数据仓库、ETL/ELT
2. 数据资产 — 包括：数据资产化、数据确权、数据估值、数据入表、数据要素、数据交易、数据运营、数据目录
3. AI — 包括：AI平台、大模型、机器学习、RAG、知识库、智能分析、智能客服、NLP、计算机视觉
4. 数据安全 — 包括：数据安全、分类分级、数据脱敏、隐私计算、数据合规、DLP、零信任

项目标题：{title}
项目内容：{content[:500]}

请返回 JSON：
{{
    "relevant": true/false,
    "category": "data_governance/data_asset/ai/data_security/none",
    "reason": "简要判断理由（20字以内）",
    "quality_score": 0-100（基于内容完整度和相关度）
}}

注意：只有真正属于以上四个领域的项目才判定为 relevant。"""

        try:
            result = await ai_client.chat(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=500,
            )
            parsed = json.loads(result)
            return {
                "relevant": parsed.get("relevant", False),
                "category": parsed.get("category", "none"),
                "reason": parsed.get("reason", ""),
                "quality_score": max(0, min(100, parsed.get("quality_score", 50))),
            }
        except Exception as e:
            logger.warning(f"[Quality] LLM filter 失败: {e}")
            return {"relevant": True, "category": "keyword_matched", "reason": "LLM unavailable", "quality_score": 50}

    # ======================================================================
    # 6. 去重 + 存储
    # ======================================================================

    async def _store(self, project_data: dict, session: AsyncSession) -> bool:
        # 确保标题有意义（过滤"采购项目名称"这类无意义标题）
        title = project_data.get("title", "")
        meaningless_prefixes = ["采购项目名称", "项目名称", "招标公告", "采购公告", "成交公告", "竞争性"]
        if not title or len(title.strip()) < 10:
            logger.info(f"[Quality] 无意义标题，跳过入库: {title}")
            return False
        for prefix in meaningless_prefixes:
            if title.strip() == prefix or title.strip().startswith(prefix):
                logger.info(f"[Quality] 无意义标题前缀，跳过入库: {title[:50]}")
                return False

        # 去重检查
        result = await session.execute(
            select(Project).where(Project.source_url == project_data["source_url"])
        )
        if result.scalar_one_or_none():
            logger.info(f"[Quality] 重复项目: {title[:60]}")
            return False

        project = Project(
            title=title,
            source_url=project_data["source_url"],
            source=project_data.get("source_platform", ""),
            publish_date=project_data.get("publish_date"),
            region=project_data.get("region"),
            buyer=project_data.get("buyer"),
            budget=project_data.get("budget"),
            summary=project_data.get("content", "")[:500] if project_data.get("content") else None,
            raw_html=project_data.get("raw_html"),
            status="new",
            # 语义过滤字段
            semantic_category=project_data.get("semantic_category"),
            semantic_score=project_data.get("semantic_score"),
            opportunity_level=project_data.get("opportunity_level"),
            matched_signals=project_data.get("matched_signals"),
            rejection_reason=project_data.get("rejection_reason", ""),
            # 第六阶段：项目阶段与时效性
            notice_type=project_data.get("notice_type"),
            deadline=project_data.get("deadline"),
            bid_deadline=project_data.get("bid_deadline"),
        )
        session.add(project)
        # 立即提交，不依赖外部 commit（避免请求超时导致回滚）
        try:
            await session.commit()
        except Exception as e:
            logger.warning(f"[Quality] 入库提交失败: {e}")
            await session.rollback()
            return False
        return True


# =============================================================================
# 数据库噪声清理
# =============================================================================

async def cleanup_noise_projects(session: AsyncSession) -> dict:
    """
    清理数据库中已存在的噪声项目
    删除不属于数据治理/数据资产/AI/数据安全的项目
    """
    result = await session.execute(select(Project))
    all_projects = result.scalars().all()
    stats = {"total": len(all_projects), "deleted": 0, "kept": 0}

    for project in all_projects:
        title = project.title or ""
        summary = project.summary or ""
        text = title + " " + summary

        # 检查是否包含精准关键词
        has_precision_kw = any(kw.lower() in text.lower() for kw in ALL_PRECISION_KEYWORDS)
        if not has_precision_kw:
            logger.info(f"[Cleanup] 删除噪声项目: {title[:60]}")
            await session.delete(project)
            stats["deleted"] += 1
        else:
            stats["kept"] += 1

    logger.info(f"[Cleanup] 数据库清理完成: 总计 {stats['total']}, 删除 {stats['deleted']}, 保留 {stats['kept']}")
    return stats


# =============================================================================
# 质量统计报告
# =============================================================================

async def generate_quality_report(session: AsyncSession) -> dict:
    """
    生成数据质量统计报告
    """
    result = await session.execute(select(Project))
    all_projects = result.scalars().all()

    total = len(all_projects)
    by_source = {}
    by_status = {}

    for p in all_projects:
        by_source[p.source] = by_source.get(p.source, 0) + 1
        by_status[p.status] = by_status.get(p.status, 0) + 1

    return {
        "total_projects": total,
        "by_source": by_source,
        "by_status": by_status,
        "avg_quality": "N/A",  # quality_score not stored in DB yet
    }


# 全局单例
quality_pipeline = QualityPipeline()