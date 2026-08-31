"""Local-only preference matching; source facts and graph edges are immutable."""
import re
from datetime import datetime

SCOPES = {'找书': 'findbook', '知识地图': 'knowledge_map', '座位预测': 'seat_predict', '座位纠错': 'seat_predict', '座位': 'seat_predict'}


def scope_for(context):
    return SCOPES.get(context.split(':', 1)[0].strip(), 'unassigned')


def belongs(entry, feature):
    # Legacy wildcard entries are only reusable when their original topic identifies one feature.
    return entry.applies_to == feature or (entry.applies_to == '*' and scope_for(entry.subject) == feature)


def personalize(output, feature, memories):
    if not isinstance(output, dict) or output.get('error') or not memories:
        return output
    seat = feature == 'seat_predict'
    key = 'ranking' if seat else 'nodes'
    rows = output.get(key, [])
    used = set()
    scored = []
    for index, row in enumerate(rows):
        score, reasons = 0, []
        text = str(row.get('area_name' if seat else 'title', '')).lower()
        for memory in memories:
            content = memory.content.lower()
            delta, why = 0, []
            # Split preferences so negation does not accidentally favor an avoided item.
            for clause in re.split(r'[，。；,;\n]', content):
                sign = -1 if re.search(r'不喜欢|不要|避开|不去|不想|排除|不看', clause) else 1
                if seat:
                    for word, code in [('伯川','bochuan'),('令希','lingxi'),('盘锦','panjin'),('开发区','kaifaqu')]:
                        if word in clause and (word in text or row.get('lib_code') == code):
                            delta += sign * 3
                            why.append(('避开' if sign < 0 else '偏好') + word)
                    for digit, cn in [('1','一'),('2','二'),('3','三'),('4','四'),('5','五'),('6','六')]:
                        terms = [digit+'楼', digit+'层', cn+'楼', cn+'层', digit+'f']
                        if any(t in clause for t in terms) and any(t in text for t in terms):
                            delta += sign * 2
                            why.append(('避开' if sign < 0 else '偏好') + digit+'层')
                    if any(t in clause for t in ['空闲','人少','不拥挤','空位多']):
                        delta += 1 - (row.get('avg_occupancy_rate') if row.get('avg_occupancy_rate') is not None else 1)
                        why.append('按占用率匹配人少偏好')
                elif index > 0:
                    for triggers, words in [(['综述'],['survey','review','综述']),(['扩散'],['diffusion','扩散']),(['图像'],['image','visual','图像']),(['入门'],['introduction','tutorial','入门']),(['强化学习'],['reinforcement','强化学习'])]:
                        if any(t in clause for t in triggers) and any(w in text for w in words):
                            delta += sign * 2
                            why.append(('避开' if sign < 0 else '匹配') + triggers[0])
                    tokens = set(re.findall(r'[a-z][a-z0-9-]{2,}', clause)) - {'the','and','for','with','paper'}
                    if any(re.search(r'\b'+re.escape(t)+r'\b', text) for t in tokens):
                        delta += sign * 2; why.append('匹配论文主题关键词')
                    if any(t in clause for t in ['最新','近年','近期','近五年','近三年']):
                        year = row.get('year')
                        if isinstance(year, int):
                            delta += sign * max(0, 1 - (datetime.now().year - year) / 5)
                            why.append('按出版年份匹配近期论文偏好')
                    if any(t in clause for t in ['高被引','引用多','经典']):
                        count = row.get('citationCount')
                        if isinstance(count, int) and count > 0:
                            import math
                            delta += sign * min(2, math.log1p(count) / 5)
                            why.append('按被引量匹配偏好')
            if delta:
                score += delta * memory.confidence
                reasons.extend(why); used.add(memory.entry_id)
        item = dict(row)
        if reasons:
            item['preference_score'] = round(score, 4)
            item['preference_reason'] = '；'.join(dict.fromkeys(reasons))
        scored.append((index, score, item))
    if used:
        if seat:
            def order(pair):
                i, score, row = pair
                free = row.get('predicted_available') if output.get('mode') == 'plan' else row.get('free_now')
                tier = 0 if free is not None and free > 0 else (2 if free == 0 else 1)
                return tier, -score, (row.get('avg_occupancy_rate') if row.get('avg_occupancy_rate') is not None else 1), i
            scored.sort(key=order)
        else:
            scored = scored[:1] + sorted(scored[1:], key=lambda x: -x[1])
    return {**output, key: [r for _, _, r in scored], 'personalization': {
        'applied': bool(used), 'memory_ids': sorted(used),
        'note': ('已按本功能记忆调整排序' + ('，满座楼层不优先推荐。' if seat else '并描边标记偏好论文，引用关系保持不变。')) if used else
                '记忆已读取，但暂无可验证的匹配；靠窗、电源、安静等缺失属性不会猜测。'}}
