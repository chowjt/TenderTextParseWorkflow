"""
输出模型模块 - 一比一还原JSON中4种公告类型的OutputFormat结构。
使用Pydantic BaseModel定义，用于LangChain结构化输出。
"""

from pydantic import BaseModel, Field
from typing import List, Optional


# ============================================================
# 招标公告 - 输出模型
# 一比一还原JSON中 hpBjDyzAQKiDHAwx 节点的 OutputFormat
# ============================================================

class ZhaobiaoNotice(BaseModel):
    """招标公告解析结果"""
    dupUid: str = Field(default="", description="主表业务主键")
    projectName: str = Field(default="", description="项目名称")
    projectNumber: str = Field(default="", description="项目编号")
    tendererName: str = Field(default="", description="招标人名称")
    tendererPhoneNumber: str = Field(default="", description="招标人联系电话")
    projectScale: str = Field(default="", description="项目规模")
    tenderContentandScope: str = Field(default="", description="招标内容与范围")
    packageName: List[str] = Field(default_factory=list, description="包名称（标段名称）数组")
    bidSubmissionDeadline: str = Field(default="", description="投标截止日期")
    bidOpenDate: str = Field(default="", description="开标日期")
    spare1: str = Field(default="", description="备用字段1")
    spare2: str = Field(default="", description="备用字段2")
    spare3: str = Field(default="", description="备用字段3")


# ============================================================
# 变更公告 - 输出模型
# 一比一还原JSON中 rAOYghkLtueUuZ15 节点的 OutputFormat
# ============================================================

class BiangengNotice(BaseModel):
    """变更公告解析结果"""
    dupUid: str = Field(default="", description="主表业务主键")
    projectName: str = Field(default="", description="项目名称")
    projectNumber: str = Field(default="", description="项目编号")
    tendererName: str = Field(default="", description="招标人名称")
    tendererPhoneNumber: str = Field(default="", description="招标人联系电话")
    changeContent: str = Field(default="", description="变更内容")
    spare1: str = Field(default="", description="备用字段1")
    spare2: str = Field(default="", description="备用字段2")
    spare3: str = Field(default="", description="备用字段3")


# ============================================================
# 中标候选人公示 - 候选人子模型 + 输出模型
# 一比一还原JSON中 ksn44PyEpRZRitcf 节点的 OutputFormat
# ============================================================

class CandidateItem(BaseModel):
    """中标候选人信息"""
    packageNumber: str = Field(default="", description="包号（标段号）")
    packageName: str = Field(default="", description="包名称（标段名称）")
    supplierRanking: str = Field(default="", description="中标候选人排名")
    candidateName: str = Field(default="", description="中标候选人名称")
    bidPriceIncludingTax: str = Field(default="", description="投标报价（含税）")
    bidPriceExcludingTax: str = Field(default="", description="投标报价（不含税）")
    currencyUnit: str = Field(default="", description="金额单位")


class ZhongbiaoHouxuanrenNotice(BaseModel):
    """中标候选人公示解析结果"""
    dupUid: str = Field(default="", description="主表业务主键")
    projectName: str = Field(default="", description="项目名称")
    projectNumber: str = Field(default="", description="项目编号")
    tendererName: str = Field(default="", description="招标人名称")
    tendererPhoneNumber: str = Field(default="", description="招标人联系电话")
    candidates: List[CandidateItem] = Field(default_factory=list, description="候选人列表")
    spare1: str = Field(default="", description="备用字段1")
    spare2: str = Field(default="", description="备用字段2")
    spare3: str = Field(default="", description="备用字段3")


# ============================================================
# 结果公告 - 中标人子模型 + 输出模型
# 一比一还原JSON中 iO6Xy8ZZgVVBI6H3 节点的 OutputFormat
# ============================================================

class WinBidderItem(BaseModel):
    """中标人信息"""
    packageNumber: str = Field(default="", description="包号（标段号）")
    packageName: str = Field(default="", description="包名称（标段名称）")
    supplierRanking: str = Field(default="", description="中标人排名")
    winBidderName: str = Field(default="", description="中标人名称")
    winBidderContactNumber: str = Field(default="", description="中标人联系电话")
    bidAmountIncludingTax: str = Field(default="", description="中标金额（含税）")
    bidAmountExcludingTax: str = Field(default="", description="中标金额（不含税）")
    currencyUnit: str = Field(default="", description="金额单位")


class JieguoNotice(BaseModel):
    """结果公告解析结果"""
    dupUid: str = Field(default="", description="主表业务主键")
    projectName: str = Field(default="", description="项目名称")
    projectNumber: str = Field(default="", description="项目编号")
    tendererName: str = Field(default="", description="招标人名称")
    tendererPhoneNumber: str = Field(default="", description="招标人联系电话")
    winBidders: List[WinBidderItem] = Field(default_factory=list, description="中标人列表")
    spare1: str = Field(default="", description="备用字段1")
    spare2: str = Field(default="", description="备用字段2")
    spare3: str = Field(default="", description="备用字段3")


# ============================================================
# 工作流输入模型 - 一比一还原JSON中 chatConfig.variables
# ============================================================

class WorkflowInput(BaseModel):
    """工作流输入参数"""
    id: str = Field(default="", description="自增id")
    dupUid: str = Field(default="", description="业务主键")
    procureMethod: str = Field(default="", description="招采方式")
    noticeType: str = Field(description="公告类型")
    content: str = Field(description="公告正文")
    spare1: str = Field(default="", description="备用字段1")
    spare2: str = Field(default="", description="备用字段2")
    spare3: str = Field(default="", description="备用字段3")
