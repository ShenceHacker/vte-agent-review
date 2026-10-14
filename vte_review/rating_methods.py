"""Four configurations used by the manuscript's Table 1 / supplement.

Before/after review are paired stages of the same multi-role workflow.
An empty group is a pending import, never a copy of another group's output.
"""
DEFAULT_METHOD = 'reviewed'
METHODS = {
    'baseline':'基础单模型',
    'rag':'单模型＋RAG',
    'synthesis':'多角色汇总（未审核）',
    'reviewed':'完整审核修订系统',
}
