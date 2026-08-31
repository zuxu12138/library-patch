import copy
import pytest
from agent.core.personalization import personalize
from agent.memory.models import MemoryEntry
from agent.memory.retriever import MemoryRetriever
from agent.memory.store import MemoryStore
from agent.tests.test_planner import build_loop, FakeLLM


def entry(content, scope, subject='自定义主题'):
    return MemoryEntry(user_id='u1', type='preference', subject=subject,
                       content=content, applies_to=scope, entry_id=content)


def test_topic_mismatch_is_ok_but_other_features_and_users_are_excluded():
    store = MemoryStore(':memory:')
    for e in [entry('论文综述', 'knowledge_map'), entry('喜欢伯川','seat_predict'), entry('教材','findbook'), entry('未知','*')]:
        store.add(e)
    other = entry('其他人的论文','knowledge_map'); other.user_id='u2'; store.add(other)
    got=MemoryRetriever(store).retrieve('u1',subject='知识地图',applies_to='knowledge_map')
    assert [e.content for e in got] == ['论文综述']
    store.close()


@pytest.mark.asyncio
async def test_same_feedback_has_independent_dedup_and_scope_and_conflicts():
    llm=FakeLLM(json={'memories':[{'content':'偏好入门','subject':'任意主题','applies_to':'*'}]})
    loop,store=build_loop(extractor_llm=llm)
    a=await loop.record_feedback('入门','u1',task_context='找书:')
    b=await loop.record_feedback('入门','u1',task_context='知识地图:p1')
    c=await loop.record_feedback('入门','u1',task_context='座位纠错:')
    assert len(set(a+b+c))==3
    assert {e.applies_to for e in store.query('u1')}=={'findbook','knowledge_map','seat_predict'}
    assert await loop.record_feedback('入门','u1',task_context='找书:') == a
    llm._json={'memories':[{'content':'新偏好'}],'contradicts':a}
    await loop.record_feedback('另外一条','u1',task_context='座位纠错:')
    assert store.get(a[0]).confidence == .8
    store.close()


def test_seat_preference_changes_order_but_cannot_promote_full_floor_or_change_facts():
    rows=[{'area_name':'令希_3F','free_now':10,'avg_occupancy_rate':.1},
          {'area_name':'伯川_3F','free_now':5,'avg_occupancy_rate':.5},
          {'area_name':'伯川_4F','free_now':0,'avg_occupancy_rate':1}]
    data={'ranking':rows}; original=copy.deepcopy(data)
    out=personalize(data,'seat_predict',[entry('优先伯川','seat_predict')])
    assert [r['area_name'] for r in out['ranking']]==['伯川_3F','令希_3F','伯川_4F']
    assert data==original
    assert out['ranking'][0]['free_now']==5
    assert out['ranking'][-1]['avg_occupancy_rate']==1
    assert out['personalization']['applied']
    out=personalize(data,'seat_predict',[entry('避开伯川','seat_predict')])
    assert out['ranking'][0]['area_name']=='令希_3F'
    out=personalize(data,'seat_predict',[entry('喜欢靠窗带电源的安静座位','seat_predict')])
    assert not out['personalization']['applied']


def test_graph_reorders_and_highlights_without_fabricating_nodes_or_edges():
    data={'nodes':[{'paperId':'root','title':'Root','depth':0},
                   {'paperId':'a','title':'Other','depth':1},
                   {'paperId':'b','title':'Diffusion Survey','depth':2}],
          'edges':[{'source':'root','target':'a'},{'source':'a','target':'b'}]}
    original=copy.deepcopy(data)
    out=personalize(data,'knowledge_map',[entry('喜欢扩散综述','knowledge_map')])
    assert [r['paperId'] for r in out['nodes']]==['root','b','a']
    assert out['nodes'][1]['preference_score']>0
    assert out['edges']==data['edges'] and data==original
    assert personalize(data,'knowledge_map',[])==original


@pytest.mark.asyncio
async def test_real_loop_applies_memory_after_tool_without_llm_ranking():
    e=entry('喜欢伯川','seat_predict')
    llm=FakeLLM(available=False)
    loop,store=build_loop(planner_llm=llm,entries=[e])
    async def tool(args):
        return {'ranking':[{'area_name':'令希','free_now':1,'avg_occupancy_rate':.5},
                           {'area_name':'伯川','free_now':1,'avg_occupancy_rate':.5}]}
    loop.register_tool('predict_seats',tool)
    result=await loop.run(feature='seat_predict',subject='座位预测',task='x',tool_name='predict_seats',tool_args={},user_id='u1',trace_id='x')
    assert result.output['ranking'][0]['area_name']=='伯川'
    assert llm.json_calls==0 and result.used_llm is False
    assert result.output['personalization']['memory_ids']==[e.entry_id]
    store.close()
