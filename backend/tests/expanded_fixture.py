"""Synthetic seven-field output shared by isolated acceptance tests."""

import copy

SOURCE = '客户：我是云杉公司的林晓，负责采购。需要150件文化衫。请下周五交货。\n商家：收到，我先核实产能。'
OUTPUT = {
    'requirements': [{'field': '数量', 'value': '150件', 'evidence': '需要150件文化衫'}],
    'questions': [{'question': '下周五交货日期是否正确？', 'initial_guess': '暂按2026-10-30，请确认。', 'related_ddl_index': 0}],
    'tasks': ['核对客户提供的标识文件'],
    'reply': '收到150件文化衫需求，请确认交货日期与尺码。',
    'ddl_tasks': [{'title': '安排文化衫交货', 'ddl_date': '2026-10-30', 'start_date': '2026-10-20',
                   'source_quote': '请下周五交货', 'date_basis': 'inferred'}],
    'suggested_tasks': [{'title': '准备阶梯报价', 'reason': '客户正在核对采购数量，可提供不同数量的价格方案。', 'priority': 'high'}],
    'customer_profile': {'display_name': '林晓', 'role': '采购', 'company': '云杉公司', 'industry': '未知',
                         'concerns': ['交期'], 'decision_style': '未知', 'communication_preferences': [],
                         'risk_points': ['交货日期需要核实'], 'next_follow_up': '确认可行交期',
                         'communication_strategy': '', 'communication_points': []},
}


def output():
    return copy.deepcopy(OUTPUT)


def review_output(**corrections):
    return {'approved': not bool(corrections), **{key:corrections.get(key) for key in OUTPUT}}
