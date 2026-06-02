"""
Nik Project Hunter - LLM 客户端封装

设计思路:
- 使用 OpenAI SDK 兼容接口(支持 DeepSeek / OpenAI / Claude / 任意兼容 API)
- 支持流式和非流式调用
- 错误重试机制
- 集中管理 prompt 模板(未来可外部化)
"""

import json
from typing import Optional
from openai import AsyncOpenAI
from loguru import logger
from app.config import get_settings

settings = get_settings()


class AIClient:
    """LLM 客户端"""

    def __init__(self):
        if not settings.LLM_API_KEY:
            logger.warning("LLM_API_KEY 未设置,AI 功能不可用")
        self.client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
        )
        self.model = settings.LLM_MODEL

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: Optional[dict] = None,
    ) -> str:
        """
        调用 LLM

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数(分析类用 0.3,创意类用 0.7)
            max_tokens: 最大输出 token
            response_format: 响应格式(如 {"type": "json_object"})

        Returns:
            模型输出文本
        """
        if not settings.LLM_API_KEY:
            raise ValueError("LLM_API_KEY is not configured. Set it via environment variable or .env file.")

        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format:
                kwargs["response_format"] = response_format

            response = await self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            raise

    async def analyze_project(self, project_data: dict) -> dict:
        """
        分析项目并返回结构化 JSON

        Args:
            project_data: 项目数据字典

        Returns:
            结构化分析结果
        """
        prompt = f"""你是一个企业级 AI 项目分析师。请分析以下招投标项目。

项目标题:{project_data.get('title', '未知')}
采购单位:{project_data.get('buyer', '未知')}
预算金额:{project_data.get('budget', '未知')} 元
项目描述:{project_data.get('description', '无详细描述')}

请以 JSON 格式返回分析结果,包含以下字段:
1. summary: 项目摘要(100 字以内)
2. category: 项目类别(数据治理/数据安全/AI/数字化/其他)
3. relevance: 与我方业务的关联度(高/中/低)
4. strengths: 我方在该项目中的优势(数组)
5. risks: 潜在风险点(数组)
6. recommended_action: 建议行动(立即跟进/关注/观察/放弃)

请确保输出是合法的 JSON。"""

        result = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(result)
        except json.JSONDecodeError:
            logger.error(f"AI 返回非法 JSON: {result}")
            return {"error": "AI response parsing failed", "raw": result}

    async def score_project(self, project_data: dict, analysis: dict) -> dict:
        """
        对项目进行商机评分

        Args:
            project_data: 项目数据
            analysis: AI 分析结果

        Returns:
            评分结果(含评分和理由)
        """
        prompt = f"""你是一个企业级销售评分专家。请对以下招投标项目进行商机评分(0-100分)。

项目信息:
- 标题:{project_data.get('title', '未知')}
- 预算:{project_data.get('budget', '未知')}
- 采购单位:{project_data.get('buyer', '未知')}
- 类别:{analysis.get('category', '未知')}
- 关联度:{analysis.get('relevance', '未知')}

评分权重:
- 关键词匹配(50%):标题/内容是否命中"数据安全""数据分类分级""等保测评"这三个核心关键词
- 业务关联度(20%):项目与我方数据安全产品的匹配程度
- 行业价值(20%):项目所在行业的市场规模和复制潜力
- 预算规模(10%):预算金额大小，金额越大得分越高

评分标准:
- 80-100:高价值商机,立即跟进
- 60-79:中等价值,重点关注
- 40-59:一般价值,保持观察
- 0-39:低价值,暂不跟进

请以 JSON 格式返回:
1. score: 总分(0-100)，按上述权重加权计算
2. reason: 评分理由
3. dimensions: {{"keyword_match": 0-100, "relevance_score": 0-100, "industry_score": 0-100, "budget_score": 0-100}}

请确保输出是合法的 JSON。"""

        result = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(result)
        except json.JSONDecodeError:
            logger.error(f"AI 评分返回非法 JSON: {result}")
            return {"score": 0, "reason": "AI 评分失败", "dimensions": {}}


# 全局单例
ai_client = AIClient()