"""
Nik Project Hunter — Follow-up Engine（第六阶段）

AI 跟进建议引擎 — 为每个商机生成 6 维跟进建议：

1. 首次沟通建议 — 如何开启第一次接触
2. 电话沟通建议 — 电话沟通要点
3. 微信沟通建议 — 微信沟通技巧
4. 邮件标题建议 — 吸引注意力的邮件标题
5. 邮件正文建议 — 专业得体的邮件正文
6. PPT 方案建议 — 方案演示要点

设计原则：
- 每项建议都具体可执行
- 根据行业/项目类型/企业成熟度定制
- 销售团队可以直接使用的文案
"""

from datetime import datetime, timezone
from typing import Optional
from loguru import logger

from app.config import get_settings
from app.core.ai_client import ai_client
from app.models import Project, Company


class FollowUpEngine:
    """
    跟进建议引擎

    为每个商机生成 6 维跟进建议，辅助销售团队执行。
    所有输出由 AI 生成，销售团队可以直接参考使用。
    """

    async def generate_followup_advice(
        self,
        project: Optional[Project] = None,
        company: Optional[Company] = None,
        sales_stage: Optional[str] = None,
        existing_vendor: Optional[bool] = None,
    ) -> dict:
        """
        为项目/企业生成 6 维跟进建议

        Args:
            project: 项目对象（可选）
            company: 企业对象（可选）
            sales_stage: 当前销售阶段
            existing_vendor: 是否已有供应商

        Returns:
            {
                "first_contact_advice": str,          # 首次沟通建议
                "phone_call_advice": str,             # 电话沟通建议
                "wechat_advice": str,                 # 微信沟通建议
                "email_subject_suggestion": str,       # 邮件标题建议
                "email_body_suggestion": str,          # 邮件正文建议
                "ppt_suggestion": str,                 # PPT 方案建议
                "followup_generated_at": str,          # 生成时间
            }
        """
        logger.info(
            f"[FollowUp] 开始生成跟进建议: "
            f"company={company.company_name if company else 'N/A'}"
        )

        # 构建 AI prompt
        prompt = self._build_followup_prompt(project, company, sales_stage, existing_vendor)

        try:
            # 调用 AI（强制 JSON 输出）
            result = await ai_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": self._get_followup_system_prompt(),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )

            # 解析 AI 输出
            advice = self._parse_ai_response(result)

            # 添加元数据
            advice["followup_generated_at"] = datetime.now(timezone.utc).isoformat()

            logger.info("[FollowUp] 跟进建议生成完成")

            return advice

        except Exception as e:
            logger.error(f"[FollowUp] 跟进建议生成异常: {e}")
            return self._get_default_advice()

    def _get_followup_system_prompt(self) -> str:
        """获取跟进建议系统提示词"""
        return (
            "你是一位资深的企业级销售顾问，擅长 ToB 大客户销售跟进。\n\n"
            "你的任务是为销售团队生成具体、可执行的跟进建议。\n\n"
            "核心要求：\n"
            "1. 每项建议必须具体，包含具体话术/文案，不要空泛\n"
            "2. 根据行业和项目类型定制内容\n"
            "3. 邮件正文要专业、有层次、有行动号召\n"
            "4. 电话和微信建议要简短直接\n"
            "5. PPT 建议要突出方案价值\n\n"
            "输出必须为 JSON 格式。"
        )

    def _build_followup_prompt(
        self,
        project: Optional[Project],
        company: Optional[Company],
        sales_stage: Optional[str],
        existing_vendor: Optional[bool],
    ) -> str:
        """构建跟进建议 prompt"""
        parts = ["请为以下商机生成跟进建议：\n"]

        # 项目信息
        if project:
            parts.append(f"## 项目信息")
            parts.append(f"- 项目名称: {project.title}")
            parts.append(f"- 采购单位: {project.buyer or '未知'}")
            parts.append(f"- 预算: {project.budget or '未知'}")
            if project.analysis:
                analysis = project.analysis if isinstance(project.analysis, dict) else {}
                parts.append(f"- 行业类型: {analysis.get('industry_type', '未知')}")
                parts.append(f"- 项目类型: {analysis.get('project_type', '未知')}")
                parts.append(f"- 摘要: {analysis.get('summary', '')[:200]}")
            if project.score is not None:
                parts.append(f"- 商机评分: {project.score}/100")

        # 企业信息
        if company:
            parts.append(f"\n## 企业画像")
            parts.append(f"- 企业名称: {company.company_name}")
            parts.append(f"- 行业: {company.industry or '未知'}")
            parts.append(f"- 数字化成熟度: {company.digital_maturity or '未知'}/100")
            parts.append(f"- AI 成熟度: {company.ai_maturity or '未知'}/100")
            parts.append(f"- 数据成熟度: {company.data_maturity or '未知'}/100")

        # 销售阶段
        if sales_stage:
            stage_map = {
                "research": "调研阶段（客户正在了解方案）",
                "budget": "预算阶段（客户正在做预算规划）",
                "project_init": "立项阶段（客户正在走立项流程）",
                "bidding": "招标阶段（客户已发布招标）",
                "implementation": "实施阶段（客户已进入实施）",
            }
            parts.append(f"\n## 当前销售阶段")
            parts.append(f"- {stage_map.get(sales_stage, sales_stage)}")

        # 供应商情况
        if existing_vendor is not None:
            parts.append(f"\n## 供应商情况")
            parts.append(f"- {'已有供应商' if existing_vendor else '暂无明确供应商'}")

        parts.append(f"\n## 要求输出 JSON")
        parts.append("{")
        parts.append('  "first_contact_advice": "首次沟通建议（50-150字，包含开场白和要点）",')
        parts.append('  "phone_call_advice": "电话沟通建议（50-100字，包含通话重点）",')
        parts.append('  "wechat_advice": "微信沟通建议（50-100字，包含微信沟通技巧）",')
        parts.append('  "email_subject_suggestion": "email_subject_suggestion": "邮件标题（10-30字，吸引注意力）",')
        parts.append('  "email_body_suggestion": "邮件正文（200-500字，专业得体的完整邮件）",')
        parts.append('  "ppt_suggestion": "PPT 方案建议（50-150字，方案核心要点）"')
        parts.append("}")

        return "\n".join(parts)

    def _parse_ai_response(self, ai_result: str) -> dict:
        """解析 AI 响应为结构化建议"""
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
            required_fields = [
                "first_contact_advice",
                "phone_call_advice",
                "wechat_advice",
                "email_subject_suggestion",
                "email_body_suggestion",
                "ppt_suggestion",
            ]

            for field in required_fields:
                if field not in data:
                    logger.warning(f"[FollowUp] 缺少字段: {field}")
                    data[field] = "暂无建议"

            return data

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"[FollowUp] AI 响应解析失败: {e}")
            return self._get_default_advice()

    def _get_default_advice(self) -> dict:
        """获取默认跟进建议"""
        return {
            "first_contact_advice": "建议先通过行业渠道了解客户当前数字化建设情况，再制定具体沟通策略。",
            "phone_call_advice": "重点了解客户当前数据治理现状和痛点，不要急于推产品。",
            "wechat_advice": "保持专业沟通，定期分享行业洞察和案例，建立专业形象。",
            "email_subject_suggestion": "关于企业数字化转型的建议方案",
            "email_body_suggestion": (
                "尊敬的[客户姓名]：\n\n"
                "您好！我是北京霍因科技的[你的姓名]，专注企业数据治理与AI智能化建设。\n\n"
                "了解到贵单位在[相关领域]有建设需求，我们已服务过多个同行业客户，积累了丰富的实践经验。\n\n"
                "如方便，可以安排一次15分钟的电话沟通，了解贵单位的具体需求，并分享相关案例。\n\n"
                "期待与您的交流。\n\n"
                "[你的姓名]\n北京霍因科技有限公司\n[联系方式]"
            ),
            "ppt_suggestion": "建议从行业趋势切入，突出数据治理+AI智能化的价值，配合同行业案例展示。",
            "followup_generated_at": datetime.now(timezone.utc).isoformat(),
        }


# 全局单例
followup_engine = FollowUpEngine()