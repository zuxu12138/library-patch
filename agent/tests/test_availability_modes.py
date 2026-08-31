import sqlite3
from datetime import datetime,timedelta,timezone
import pytest
from collector import seat_collector as collector
from agent.features.seat_predict.service import SeatPredictService
from agent.tests.fakes import FakeAgentLoop

@pytest.mark.parametrize('raw,expected',[
 ({'isbusy':'false','status':'可预约'},'available'),
 ({'isbusy':'true','status':'已占用'},'occupied'),
 ({'isbusy':'false','status':'不可预约'},'unavailable'),
 ({'isbusy':'false','status':''},'unknown'), ({},'unknown'),
 ({'isbusy':'false','status':'维护中'},'unknown')])
def test_state(raw,expected):
 assert collector.seat_state(raw)==expected

@pytest.mark.asyncio
async def test_plan_uses_distinct_days_not_current_or_poll_count(tmp_path,monkeypatch):
 p=tmp_path/'seats.db'; monkeypatch.setattr(collector,'DB_PATH',p)
 c=collector.init_db(); now=datetime.now(timezone(timedelta(hours=8)))
 for days,count,free in [(21,20,10),(14,1,90),(7,1,50),(0,1,0)]:
  dt=now-timedelta(days=days)
  for i in range(count):
   c.execute('INSERT INTO area_availability VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
      (dt.isoformat(),int(dt.timestamp())+i,dt.weekday(),'14:00','bochuan','1','伯川3F',100,free,0,100-free,0))
 c.commit();c.close()
 service=SeatPredictService(FakeAgentLoop(),None,str(p))
 args={'mode':'plan','weekday':now.weekday()+1,'hour':14}
 out=await service._availability_tool(args)
 row=out['ranking'][0]
 assert row['sample_days']==3 and row['predicted_available']==50
 assert row['free_now'] is None and row['unavailable_now'] is None
 assert out['realtime_available'] is False
 # No estimates from another hour, regardless of fresh current snapshot.
 args['hour']=15
 row=(await service._availability_tool(args))['ranking'][0]
 assert row['predicted_available'] is None and not row['recommendable']
 # Stale data must not be presented as current available seats.
 with sqlite3.connect(p) as c: c.execute('UPDATE area_availability SET epoch=epoch-3600')
 row=(await service._availability_tool({**args,'mode':'now'}))['ranking'][0]
 assert row['free_now'] is None and row['occupied_now'] is None
 assert not row['fresh'] and not row['recommendable']

@pytest.mark.asyncio
@pytest.mark.parametrize('hour,minute,closed', [(21,59,False),(22,0,True),(23,30,True)])
async def test_closing_time_boundary(tmp_path,monkeypatch,hour,minute,closed):
 import datetime as dtmodule
 fixed=datetime(2026,8,31,hour,minute,tzinfo=timezone(timedelta(hours=8)))
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None): return fixed
 monkeypatch.setattr(dtmodule,'datetime',Clock)
 p=tmp_path/'seats.db';monkeypatch.setattr(collector,'DB_PATH',p)
 c=collector.init_db()
 c.execute('INSERT INTO area_availability VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
   (fixed.isoformat(),int(fixed.timestamp()),0,'21:00','bochuan','1','伯川3F',100,50,20,30,0))
 c.commit();c.close()
 service=SeatPredictService(FakeAgentLoop(),None,str(p))
 result=await service._availability_tool({'mode':'now','weekday':1,'hour':21})
 assert result['closed'] is closed
 assert result['ranking'][0]['recommendable'] is (not closed)
 assert result['ranking'][0]['free_now']==(None if closed else 50)
 result=await service._availability_tool({'mode':'plan','weekday':1,'hour':21})
 assert result['closed'] is False
