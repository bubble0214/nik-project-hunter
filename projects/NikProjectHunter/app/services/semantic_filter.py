"""
Nik Project Hunter — 语义级项目相关性过滤器（Intelligence Sprint 升级版）

职责：
1. 联合分析标题 + 正文 + 采购需求 + 技术要求 + 项目背景 + 资质要求
2. 通过 AI 语义判断项目是否真正属于目标行业（数据治理/数据安全/数据资产/AI智能体）
3. 输出 relevance_score（0-100） + opportunity_level
4. 记录被拒绝项目及原因到 logs/semantic_filter.log
5. 保留弱趋势信号（weak_signal）供 Intelligence 分析

核心目标（Intelligence Sprint）：
- 放宽过滤阈值，保留弱信号
- 引入 opportunity_level 分级
- 宁可保留弱信号，不要错过趋势
"""

import json
import os
import logging
from typing import Optional
from loguru import logger
from app.core.ai_client import ai_client


# =============================================================================
# 日志配置
# =============================================================================
SEMANTIC_LOG_FILE = "logs/semantic_filter.log"
HEALTH_LOG_FILE = "logs/spider_health.log"
TREND_LOG_FILE = "logs/trend_intelligence.log"

# 确保日志目录存在
os.makedirs("logs", exist_ok=True)

# 语义过滤专用 logger
semantic_logger = logging.getLogger("semantic_filter")
semantic_logger.setLevel(logging.INFO)
if not semantic_logger.handlers:
    fh = logging.FileHandler(SEMANTIC_LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    semantic_logger.addHandler(fh)


# =============================================================================
# 目标行业定义 — 四象限
# =============================================================================
TARGET_CATEGORIES = {
    "data_governance": {
        "name": "数据治理",
        "keywords": [
            "数据治理", "主数据", "元数据", "数据质量", "数据中台",
            "Data Fabric", "数据编织", "数据湖", "数据标准", "数据目录",
            "数据血缘", "数据架构", "数据模型", "MDM", "湖仓一体",
            "ETL", "ELT", "数据仓库", "数据平台", "数据治理平台",
            "数据治理体系", "数据管控", "数据资源目录",
        ],
    },
    "data_security": {
        "name": "数据安全",
        "keywords": [
            "数据分类分级", "分类分级", "数据安全评估", "数据安全风险评估",
            "数据脱敏", "数据合规", "DLP", "数据防泄漏", "隐私计算",
            "数据审计", "数据风控", "零信任", "数据安全治理",
            "个人信息保护", "数据出境", "数据跨境", "数据安全法",
            "等保", "等级保护", "密评", "密码评估",
        ],
    },
    "data_asset": {
        "name": "数据资产",
        "keywords": [
            "数据资产", "数据要素", "数据入表", "数据运营", "数据确权",
            "数据流通", "数据共享", "数据交易", "数据估值", "数据资本化",
            "数据资产化", "数据资产入表", "数据要素市场化",
        ],
    },
    "ai": {
        "name": "AI智能体",
        "keywords": [
            "AI智能体", "智能体", "大模型", "AI平台", "RAG",
            "LLM", "知识库", "Agent", "多智能体", "AI分析",
            "AI中台", "机器学习", "深度学习", "NLP", "知识图谱",
            "智能客服", "Copilot", "智能决策", "智能风控", "智能营销",
            "AI应用", "AI能力", "AI算法",
        ],
    },
}

# =============================================================================
# 噪声项目特征（放宽版 — 不再直接拒绝，而是降级为 weak_signal）
# =============================================================================
NOISE_PATTERNS = [
    # 办公/行政类
    "OA系统", "OA办公", "办公自动化", "办公系统", "协同办公",
    # ERP/管理系统（不含数据治理）
    "ERP系统", "ERP", "CRM系统", "进销存", "财务系统",
    # 校园/教育类
    "智慧校园", "智慧教室", "校园一卡通", "电子班牌", "校园安防",
    # 基础设施
    "网络设备", "交换机", "路由器", "服务器采购",
    "云桌面", "桌面云", "虚拟桌面", "机房建设", "机房改造",
    # 监控/安防
    "视频监控", "安防工程", "门禁系统", "停车场",
    # 运维服务（不含数据安全运维）
    "运维服务", "IT运维", "运维管理",
    # 普通软件开发
    "APP开发", "小程序开发", "网站建设", "门户网站",
    # 硬件采购
    "电脑采购", "笔记本", "打印机", "复印机", "办公设备",
    # 通用IT（不含数据/AI）
    "系统集成", "IT服务",
]

# 如果正文中出现以下信号，可覆盖 NOISE_PATTERNS（即项目仍是相关的）
OVERWRITE_SIGNALS = [
    "数据治理", "数据资产", "数据安全", "AI智能体",
    "大模型", "分类分级", "数据要素",
]


# =============================================================================
# AI 语义分析 Prompt（Intelligence Sprint 升级版）
# =============================================================================
SEMANTIC_ANALYSIS_PROMPT = """你是一个专业的企业级数据智能、数据安全、AI 领域项目分析师。

请对以下招投标项目进行语义相关性分析。

## 目标行业（仅保留以下四类）

### 1. 数据治理
数据治理平台、主数据管理、元数据管理、数据质量管理、数据中台、Data Fabric、数据湖、数据标准、数据目录、数据血缘、数据架构、ETL/ELT、数据仓库、数据管控

### 2. 数据安全
数据分类分级、数据安全风险评估、数据安全评估、数据脱敏、数据合规、DLP、隐私计算、数据审计、零信任、个人信息保护、数据防泄漏

### 3. 数据资产
数据资产化、数据确权、数据估值、数据入表、数据要素、数据交易、数据运营、数据流通、数据共享、数据资产入表

### 4. AI 智能体
AI智能体、大模型、AI平台、RAG、LLM、知识库、Agent、多智能体系统、AI分析、AI中台、机器学习、深度学习、NLP、知识图谱、智能客服、Copilot

## 评分规则
- relevance_score >= 80: 战略级（strategic），高预算高匹配
- relevance_score >= 65: 高价值（high_value），明确相关
- relevance_score >= 50: 观察级（observation），弱相关但有信号
- relevance_score >= 35: 弱信号（weak_signal），边缘相关/新兴方向
- relevance_score < 35: 不相关

注意：放宽判断标准。即使项目是OA系统、ERP、普通IT采购，只要正文中包含明确的数据治理/安全/资产/AI 相关需求，就应判断为相关。

## 输入数据
请联合分析以下所有字段：

标题: {title}
正文内容: {content}
采购需求: {procurement_requirements}
技术要求: {technical_requirements}
项目背景: {project_background}
资质要求: {qualification_requirements}

## 输出格式（严格 JSON）
{{
    "is_relevant": true/false,
    "category": "data_governance / data_security / data_asset / ai / none",
    "relevance_score": 0-100,
    "opportunity_level": "strategic / high_value / observation / weak_signal / none",
    "reason": "判断理由（30字以内）",
    "matched_signals": ["信号1", "信号2", ...],
    "actual_project_type": "项目实际类型描述（如：OA办公系统采购）",
    "rejection_reason": "如果不相关，说明具体原因；如果相关则为空"
}}

注意：
1. 宽松判断：宁可保留弱信号，不要错过趋势
2. 如果正文包含"数据治理""数据资产""数据安全""大模型""AI""分类分级""数据要素"等信号，应放行
3. 弱信号项目入库但不通知
"""


class SemanticFilterService:
    """
    语义级项目相关性过滤器（Intelligence Sprint 升级版）

    使用 AI 对项目进行多维语义分析，判断是否属于目标行业。
    """

    LOG_FILE = SEMANTIC_LOG_FILE

    def __init__(self):
        self.logger = semantic_logger

    # ======================================================================
    # 核心方法
    # ======================================================================

    async def analyze(self, project: dict) -> dict:
        """
        对单个项目进行语义相关性分析

        Args:
            project: 项目数据字典，应包含 title, content 等字段

        Returns:
            {
                "is_relevant": bool,
                "category": str,
                "relevance_score": int,
                "opportunity_level": str,
                "reason": str,
                "matched_signals": list,
                "actual_project_type": str,
                "rejection_reason": str,
            }
        """
        title = project.get("title", "")
        content = project.get("content", "")

        # ================================================================
        # 第一步：快速关键词预检（放宽版）
        # ================================================================
        quick_result = self._quick_keyword_check(title, content)
        if quick_result is not None:
            self._log_result(title, quick_result, source="keyword_precheck")
            return quick_result

        # ================================================================
        # 第二步：AI 语义深度分析
        # ================================================================
        ai_result = await self._ai_semantic_analysis(project)
        self._log_result(title, ai_result, source="ai_semantic")
        return ai_result

    # ======================================================================
    # 快速关键词预检（Intelligence Sprint 放宽版）
    # ======================================================================

    def _quick_keyword_check(self, title: str, content: str) -> Optional[dict]:
        """
        快速关键词预检（放宽版）

        规则：
        1. 覆盖信号 → 直接放行（高价值）
        2. 噪声模式 → 不再拒绝，保留为 weak_signal
        3. 无信号 → 需要 AI 判断

        Returns:
            None = 无法快速决策，需要 AI 分析
            dict = 快速决策结果
        """
        combined = (title + " " + (content or "")[:800]).lower()

        # 检查覆盖信号（优先）
        has_overwrite = False
        overwrite_signals_found = []
        for signal in OVERWRITE_SIGNALS:
            if signal.lower() in combined:
                has_overwrite = True
                overwrite_signals_found.append(signal)

        # 检查噪声模式
        has_noise = False
        noise_matched = ""
        for pattern in NOISE_PATTERNS:
            if pattern.lower() in combined:
                has_noise = True
                noise_matched = pattern
                break

        # 决策逻辑
        if has_overwrite:
            # 有覆盖信号 → 直接放行
            return {
                "is_relevant": True,
                "category": self._quick_category(combined),
                "relevance_score": 75,
                "opportunity_level": "high_value",
                "reason": f"关键词信号匹配: {', '.join(overwrite_signals_found[:3])}",
                "matched_signals": overwrite_signals_found[:5],
                "actual_project_type": "待AI确认",
                "rejection_reason": "",
            }

        if has_noise:
            # 无覆盖信号 + 有噪声 → 保留为 weak_signal
            return {
                "is_relevant": True,
                "category": "none",
                "relevance_score": 40,
                "opportunity_level": "weak_signal",
                "reason": f"弱信号（噪声匹配: {noise_matched}）",
                "matched_signals": [],
                "actual_project_type": noise_matched,
                "rejection_reason": "",
            }

        # 无法快速决策
        return None

    def _quick_category(self, text: str) -> str:
        """快速判断类别"""
        for cat_id, cat_info in TARGET_CATEGORIES.items():
            for kw in cat_info["keywords"]:
                if kw.lower() in text.lower():
                    return cat_id
        return "none"

    # ======================================================================
    # AI 语义分析（Intelligence Sprint 升级版）
    # ======================================================================

    async def _ai_semantic_analysis(self, project: dict) -> dict:
        """
        调用 AI 进行深度语义分析

        联合分析标题、正文、采购需求、技术要求、项目背景、资质要求
        """
        title = project.get("title", "")
        content = project.get("content", "")[:3000]
        procurement_requirements = project.get("procurement_requirements", "")[:1000]
        technical_requirements = project.get("technical_requirements", "")[:1000]
        project_background = project.get("project_background", "")[:1000]
        qualification_requirements = project.get("qualification_requirements", "")[:1000]

        prompt = SEMANTIC_ANALYSIS_PROMPT.format(
            title=title or "未知",
            content=content or "无正文内容",
            procurement_requirements=procurement_requirements or "无",
            technical_requirements=technical_requirements or "无",
            project_background=project_background or "无",
            qualification_requirements=qualification_requirements or "无",
        )

        try:
            result = await ai_client.chat(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=1024,
            )
            parsed = json.loads(result)

            # 规范化输出
            return {
                "is_relevant": bool(parsed.get("is_relevant", False)),
                "category": parsed.get("category", "none"),
                "relevance_score": max(0, min(100, int(parsed.get("relevance_score", 0)))),
                "opportunity_level": parsed.get("opportunity_level", "none"),
                "reason": parsed.get("reason", "")[:100],
                "matched_signals": parsed.get("matched_signals", []),
                "actual_project_type": parsed.get("actual_project_type", ""),
                "rejection_reason": parsed.get("rejection_reason", ""),
            }
        except json.JSONDecodeError as e:
            logger.warning(f"[SemanticFilter] AI 返回非法 JSON: {str(result)[:200]}")
            return {
                "is_relevant": True,
                "category": "unknown",
                "relevance_score": 55,
                "opportunity_level": "observation",
                "reason": "AI 分析失败，保守放行",
                "matched_signals": [],
                "actual_project_type": "未知",
                "rejection_reason": "",
            }
        except Exception as e:
            logger.error(f"[SemanticFilter] AI 分析异常: {e}")
            return {
                "is_relevant": True,
                "category": "unknown",
                "relevance_score": 55,
                "opportunity_level": "observation",
                "reason": "AI 异常，保守放行",
                "matched_signals": [],
                "actual_project_type": "未知",
                "rejection_reason": "",
            }

    # ======================================================================
    # 批量分析
    # ======================================================================

    async def analyze_batch(self, projects: list[dict]) -> list[dict]:
        """
        批量分析多个项目

        Args:
            projects: 项目数据字典列表

        Returns:
            每个项目的分析结果列表（顺序一致）
        """
        results = []
        for project in projects:
            try:
                result = await self.analyze(project)
            except Exception as e:
                logger.error(f"[SemanticFilter] 批量分析异常: {project.get('title', '')[:50]}: {e}")
                result = {
                    "is_relevant": True,
                    "category": "unknown",
                    "relevance_score": 55,
                    "opportunity_level": "observation",
                    "reason": "分析异常，保守放行",
                    "matched_signals": [],
                    "actual_project_type": "未知",
                    "rejection_reason": "",
                }
            results.append(result)
        return results

    # ======================================================================
    # 日志
    # ======================================================================

    def _log_result(self, title: str, result: dict, source: str = "unknown"):
        """记录过滤结果到日志"""
        level = result.get("opportunity_level", "none")
        status = "✅ 通过" if result.get("is_relevant") else "❌ 拒绝"
        self.logger.info(
            f"[{source}] {status} | "
            f"score={result.get('relevance_score', 'N/A')} | "
            f"level={level} | "
            f"category={result.get('category', 'N/A')} | "
            f"reason={result.get('reason', '')} | "
            f"title={title[:60]}"
        )
        if not result.get("is_relevant"):
            self.logger.info(
                f"  └─ 拒绝原因: {result.get('rejection_reason', 'N/A')} | "
                f"实际类型: {result.get('actual_project_type', 'N/A')}"
            )


# =============================================================================
# 全局单例
# =============================================================================
semantic_filter = SemanticFilterService()
