"""
Pipeline 诊断脚本 — 直接测试关键词匹配和过滤逻辑
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("APP_ENV", "development")

import asyncio
from app.pipeline.quality_pipeline import (
    QualityPipeline,
    ALL_PRECISION_KEYWORDS,
    NOISE_KEYWORDS,
    PRECISION_KEYWORDS,
)

pipeline = QualityPipeline()

# 模拟中国政府采购网常见标题
test_titles = [
    # 真实可能匹配的项目
    "某银行数据分类分级系统建设项目招标公告",
    "2026年数据安全风险评估服务采购项目",
    "数据安全治理平台建设项目竞争性磋商公告",
    "某市政府数据安全评估服务采购项目",
    "省级数据安全管控平台建设项目招标公告",
    "隐私计算平台建设项目招标公告",
    "个人信息保护影响评估服务采购公告",
    "数据安全合规评估服务采购项目",
    "某医院数据安全治理体系建设项目招标公告",
    "数据安全法合规评估服务采购项目",
    "某集团数据脱敏系统采购项目招标公告",
    "数据安全监测平台建设项目采购公告",
    "零信任安全架构建设项目招标公告",
    "某省数据安全审计项目竞争性磋商公告",
    "数据分类分级与安全评估服务采购项目",
    "某市数据安全风险评估项目竞争性磋商公告",
    "银行数据安全治理平台项目招标公告",
    "某区数据安全监测平台采购项目",
    "医院数据安全风险评估服务采购项目",
    "某单位数据安全防护体系建设项目",
    # 边缘情况
    "网络安全等级保护测评服务采购公告",
    "信息安全风险评估服务采购项目",
    "某集团2026年安全运维服务采购项目",
    "等保测评服务采购项目竞争性磋商公告",
    # 可能不匹配的
    "某局办公设备采购项目",
    "某医院物业服务采购项目",
    # 搜索词匹配（标题不含关键词但内容含）
    "某市政府采购项目公开招标公告",
    "某单位信息化建设项目招标公告",
    "某集团IT基础设施升级项目",
    "某省电子政务系统建设项目",
    # 噪声
    "某单位空调采购项目",
    "某单位保洁服务采购项目",
]

print("=" * 60)
print("Pipeline 关键词匹配诊断")
print("=" * 60)

# 1. 测试 _precision_keyword_filter
print("\n## 1. 精准关键词过滤测试\n")
for title in test_titles:
    project = {"title": title, "content": ""}
    result = pipeline._precision_keyword_filter(project)
    noise = pipeline._noise_filter(project)
    status = "✅" if result["passed"] else ("❌噪声" if noise else "❌无匹配")
    print(f"{status} {title[:50]}")
    if result["passed"]:
        print(f"    匹配: {result['matched_keywords'][:3]}")
        score = pipeline._calculate_quality_score(project, result)
        print(f"    评分: {score}")

# 2. 测试 LLM 能否调用
print("\n\n## 2. LLM 调用测试\n")
try:
    result = asyncio.run(pipeline._llm_relevance_filter({
        "title": "数据分类分级系统建设项目招标公告",
        "content": "本项目为某银行数据分类分级系统建设，预算500万元。"
    }))
    print(f"LLM 返回: {result}")
except Exception as e:
    print(f"LLM 调用失败: {e}")

# 3. 列出所有关键词
print("\n\n## 3. 当前关键词列表\n")
for cat, kws in PRECISION_KEYWORDS.items():
    print(f"\n{cat}:")
    for kw in kws:
        print(f"  - {kw}")