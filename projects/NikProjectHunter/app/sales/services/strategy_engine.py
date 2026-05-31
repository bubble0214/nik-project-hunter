"""
Nik Project Hunter — Sales Strategy Engine（第六阶段）

AI 销售策略引擎 — 为每个商机生成 6 维销售策略：

1. 最佳切入部门 — 信息中心 / 数据管理部 / 数字化办公室 / CIO办公室 / 数据资产部门
2. 推荐销售路径 — 第一接触 → 第二推进 → 最终决策
3. 推荐切入话术 — 行业 + 项目类型 + 企业成熟度 定制
4. 推荐产品方案 — 数据治理 / 数据资产 / AI 平台 / 数据安全 / 数据运营
5. 推荐销售策略 — 顾问式 / 方案型 / 关系型 / 长周期运营
6. 推荐项目优先级 — 立即跟进 / 本周跟进 / 长期培养 / 暂不跟进

设计原则：
- AI 辅助决策，非自动销售
- 每维度都有明确的 prompt 和 response 约束
- 可扩展的维度设计
"""

from datetime import datetime, timezone
from typing import Optional
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.ai_client import ai_client
from app.models import Project, Company


class SalesStrategyEngine:
    """
    销售策略引擎

    为每个项目/企业生成 6 维销售策略。
    所有输出由 AI 生成，辅助销售团队决策。
    """

    # =============================================================================
    # 维度定义（用于 Prompt 构建）
    # =============================================================================

    # 1. 切入部门候选
    ENTRY_DEPARTMENTS = [
        "信息中心",
        "数据管理部",
        "数字化办公室",
        "CIO办公室",
        "数据资产部门",
        "信息化部",
        "科技部",
        "战略规划部",
        "业务部门（直接使用方）",
    ]

    # 2. 销售路径阶段
    SALES_PATH_STEPS = [
        "first_contact",
        "second_push",
        "final_decision",
    ]

    # 3. 产品方案候选
    SOLUTION_TYPES = [
        "数据治理",
        "数据资产",
        "AI 平台",
        "数据安全",
        "数据运营",
    ]

    # 4. 销售策略候选
    STRATEGY_TYPES = [
        "顾问式销售",
        "方案型销售",
        "关系型销售",
        "长周期运营",
    ]

    # 5. 优先级候选
    PRIORITY_LEVELS = [
        "immediate",
        "this_week",
        "long_term",
        "hold",
    ]

    # =============================================================================
    # 核心方法
    # =============================================================================

    async def generate_strategy(
        self,
        project: Optional[Project] = None,
        company: Optional[Company] = None,
        session: Optional[AsyncSession] = None,
    ) -> dict:
        """
        为项目/企业生成 6 维销售策略

        Args:
            project: 项目对象（可选）
            company: 企业对象（可选）
            session: 数据库会话（可选，用于获取补充信息）

        Returns:
            {
                "best_entry_department": str,      # 最佳切入部门
                "recommended_sales_path": dict,     # 推荐销售路径
                "recommended_pitch": str,           # 推荐切入话术
                "recommended_solution": str,        # 推荐产品方案
                "recommended_strategy": str,        # 推荐销售策略
                "project_priority": str,            # 项目优先级
                "strategy_reasoning": str,          # AI 推理过程
            }
        """
        logger.info(f"[SalesStrategy] 开始生成策略: company={company.company_name if company else 'N/A'}")

        # 构建 AI prompt
        prompt = self._build_strategy_prompt(project, company)

        try:
            # 调用 AI（强制 JSON 输出）
            result = await ai_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": self._get_strategy_system_prompt(),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )

            # 解析 AI 输出
            strategy = self._parse_ai_response(result)

            # 添加元数据
            strategy["strategy_generated_at"] = datetime.now(timezone.utc).isoformat()

            logger.info(
                f"[SalesStrategy] 策略生成完成 | "
                f"部门={strategy['best_entry_department']} | "
                f"方案={strategy['recommended_solution']} | "
                f"策略={strategy['recommended_strategy']} | "
                f"优先级={strategy['project_priority']}"
            )

            return strategy

        except Exception as e:
            logger.error(f"[SalesStrategy] 策略生成异常: {e}")
            # 返回默认策略（防止空数据）
            return self._get_default_strategy()

    def _get_strategy_system_prompt(self) -> str:
        """获取销售策略系统提示词"""
        return (
            "你是一位资深的企业级 AI 和数据智能销售顾问。你的任务是为销售团队提供精准的销售策略建议。\n\n"
            "核心原则：\n"
            "1. 所有建议必须基于实际数据和行业经验\n"
            "2. 输出必须结构化，使用 JSON 格式\n"
            "3. 切入话术要具体、可执行、有说服力\n"
            "4. 产品方案选择要匹配客户实际需求\n"
            "5. 优先级判断要基于商机真实价值\n\n"
            f"可选的切入部门: {', '.join(self.ENTRY_DEPARTMENTS)}\n"
            f"可选的产品方案: {', '.join(self.SOLUTION_TYPES)}\n"
            f"可选的销售策略: {', '.join(self.STRATEGY_TYPES)}\n"
            f"可选的优先级: {', '.join(self.PRIORITY_LEVELS)}\n\n"
            "请严格按 JSON 格式输出。"
        )

    def _build_strategy_prompt(
        self,
        project: Optional[Project],
        company: Optional[Company],
    ) -> str:
        """构建策略生成 prompt"""
        parts = ["请为以下商机生成 6 维销售策略：\n"]

        # 项目信息
        if project:
            parts.append(f"## 项目信息")
            parts.append(f"- 项目名称: {project.title}")
            parts.append(f"- 采购单位: {project.buyer or '未知'}")
            parts.append(f"- 预算: {project.budget or '未知'}")
            parts.append(f"- 地区: {project.region or '未知'}")
            parts.append(f"- 来源: {project.source}")
            if project.analysis:
                analysis = project.analysis if isinstance(project.analysis, dict) else {}
                parts.append(f"- 行业类型: {analysis.get('industry_type', '未知')}")
                parts.append(f"- 项目类型: {analysis.get('project_type', '未知')}")
                parts.append(f"- 数据资产化项目: {analysis.get('is_data_asset', False)}")
                parts.append(f"- AI 项目: {analysis.get('is_ai_project', False)}")
                parts.append(f"- 长期运营项目: {analysis.get('is_long_track', False)}")
                parts.append(f"- 项目摘要: {analysis.get('summary', '')[:300]}")
            if project.summary:
                parts.append(f"- 摘要: {project.summary[:300]}")
            if project.score is not None:
                parts.append(f"- 商机评分: {project.score}/100")
                parts.append(f"- 评分等级: {project.score_grade}")
            if project.opportunity_level:
                parts.append(f"- 商机级别: {project.opportunity_level}")

        # 企业信息
        if company:
            parts.append(f"\n## 企业画像")
            parts.append(f"- 企业名称: {company.company_name}")
            parts.append(f"- 行业: {company.industry or '未知'}")
            parts.append(f"- 数字化成熟度: {company.digital_maturity or '未知'}/100")
            parts.append(f"- AI 成熟度: {company.ai_maturity or '未知'}/100")
            parts.append(f"- 数据成熟度: {company.data_maturity or '未知'}/100")
            parts.append(f"- 预算水平: {company.estimated_budget_level or '未知'}")
            parts.append(f"- 商机总分: {company.opportunity_score or '未知'}/100")
            parts.append(f"- 战略级别: {company.strategic_level or '未知'}")
            if company.recommended_strategy:
                parts.append(f"- 历史推荐策略: {company.recommended_strategy}")
            if company.latest_signal_summary:
                parts.append(f"- 最新信号: {company.latest_signal_summary[:200]}")

        parts.append(f"\n## 要求输出 JSON")
        parts.append("{")
        parts.append('  "best_entry_department": "最佳切入部门（从候选列表中选一个）",')
        parts.append('  "recommended_sales_path": {')
        parts.append('    "first_contact": "第一接触对象",')
        parts.append('    "second_push": "第二推进对象",')
        parts.append('    "final_decision": "最终决策部门"')
        parts.append("  },")
        parts.append('  "recommended_pitch": "推荐的销售切入话术（50-150字，具体可执行）",')
        parts.append('  "recommended_solution": "推荐产品方案（从候选列表选一个）",')
        parts.append('  "recommended_strategy": "推荐销售策略（从候选列表选一个）",')
        parts.append('  "project_priority": "推荐项目优先级（从候选列表选一个）",')
        parts.append('  "strategy_reasoning": "AI 推理过程（50-200字，解释为什么做这个推荐）"')
        parts.append("}")

        return "\n".join(parts)

    def _parse_ai_response(self, ai_result: str) -> dict:
        """解析 AI 响应为结构化策略"""
        import json

        try:
            # 尝试直接解析 JSON
            if isinstance(ai_result, dict):
                data = ai_result
            else:
                # 清理可能的 markdown 标记
                text = ai_result.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[-1]
                    text = text.rsplit("```", 1)[0]
                data = json.loads(text)

            # 验证必要字段
            required_fields = [
                "best_entry_department",
                "recommended_sales_path",
                "recommended_pitch",
                "recommended_solution",
                "recommended_strategy",
                "project_priority",
            ]

            for field in required_fields:
                if field not in data:
                    logger.warning(f"[SalesStrategy] 缺少字段: {field}")
                    data[field] = self._get_default_for_field(field)

            # 验证枚举值
            if data.get("best_entry_department") not in self.ENTRY_DEPARTMENTS:
                data["best_entry_department"] = self.ENTRY_DEPARTMENTS[0]

            if data.get("recommended_solution") not in self.SOLUTION_TYPES:
                data["recommended_solution"] = self.SOLUTION_TYPES[0]

            if data.get("recommended_strategy") not in self.STRATEGY_TYPES:
                data["recommended_strategy"] = self.STRATEGY_TYPES[0]

            if data.get("project_priority") not in self.PRIORITY_LEVELS:
                data["project_priority"] = self.PRIORITY_LEVELS[2]

            # 确保 sales_path 是 dict
            sales_path = data.get("recommended_sales_path", {})
            if not isinstance(sales_path, dict):
                sales_path = {
                    "first_contact": str(sales_path),
                    "second_push": "",
                    "final_decision": "",
                }
            data["recommended_sales_path"] = sales_path

            return data

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"[SalesStrategy] AI 响应解析失败: {e}, raw={ai_result[:200]}")
            return self._get_default_strategy()

    def _get_default_for_field(self, field: str):
        """获取字段默认值"""
        defaults = {
            "best_entry_department": "信息中心",
            "recommended_sales_path": {
                "first_contact": "信息中心负责人",
                "second_push": "数据管理部部长",
                "final_decision": "CIO / 分管副总",
            },
            "recommended_pitch": "建议先了解客户当前数字化建设现状，再制定具体切入话术。",
            "recommended_solution": "数据治理",
            "recommended_strategy": "顾问式销售",
            "project_priority": "long_term",
        }
        return defaults.get(field, "")

    def _get_default_strategy(self) -> dict:
        """获取默认策略"""
        return {
            "best_entry_department": "信息中心",
            "recommended_sales_path": {
                "first_contact": "信息中心负责人",
                "second_push": "数据管理部部长",
                "final_decision": "CIO / 分管副总",
            },
            "recommended_pitch": "建议先了解客户当前数字化建设现状，再制定具体切入话术。",
            "recommended_solution": "数据治理",
            "recommended_strategy": "顾问式销售",
            "project_priority": "long_term",
            "strategy_reasoning": "默认策略 — 信息不足时保守建议",
            "strategy_generated_at": datetime.now(timezone.utc).isoformat(),
        }


# 全局单例
sales_strategy_engine = SalesStrategyEngine()