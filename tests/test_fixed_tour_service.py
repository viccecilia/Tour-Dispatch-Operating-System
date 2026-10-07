import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.db import database
from backend.services import fixed_tour_service as service
from backend.services import run_document_service
from backend.services.driver_service import list_driver_assignments
from backend.services.tenant_context import set_current_tenant_id


class FixedTourServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.old = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "fixed.sqlite3"; database.init_db(seed=False); set_current_tenant_id(1)
        with closing(database.get_connection()) as conn:
            conn.execute("INSERT INTO tenants (id,name,slug) VALUES (1,'T1','t1')")
            conn.execute("INSERT INTO drivers (id,tenant_id,name,status,driver_status) VALUES (1,1,'司机','available','available')")
            conn.execute("INSERT INTO vehicles (id,tenant_id,plate_number,vehicle_type,status) VALUES (1,1,'大阪1','Alphard','available')")
            conn.execute("INSERT INTO vehicles (id,tenant_id,plate_number,vehicle_type,status) VALUES (2,1,'大阪2','HiAce','available')")
            conn.commit()
    def tearDown(self): database.DB_PATH=self.old; set_current_tenant_id(None); self.temp.cleanup()
    def route(self): return service.save_route({'route_code':'KYOTO-1','route_name':'京都经典','stops':[{'location_name':'京都','stop_type':'pickup'},{'location_name':'大阪','stop_type':'dropoff'}],'prices':[{'vehicle_type':'Alphard','price_jpy':52430}]})
    def test_snapshot_and_idempotent_materialize(self):
        route=self.route(); payload={'route_id':route['id'],'date':'2026-10-10','driver_id':1,'vehicle_id':1,'segments':[{'position':'pre','type':'airport_pickup','pickup_location':'KIX','dropoff_location':'京都','start_time':'07:00','end_time':'08:00','same_passenger':True}]}
        first=service.materialize(payload); second=service.materialize(payload)
        self.assertTrue(first['created']); self.assertFalse(second['created'])
        with closing(database.get_connection()) as conn:
            row=conn.execute('SELECT same_passenger,snapshot_json FROM fixed_tour_run_segments').fetchone()
            self.assertEqual(row['same_passenger'],1); self.assertEqual(json.loads(row['snapshot_json'])['segment_type'],'airport_pickup')
    def test_price_and_time_validation(self):
        route=self.route()
        with self.assertRaisesRegex(ValueError,'segment_time_order'): service.materialize({'route_id':route['id'],'date':'2026-10-10','driver_id':1,'vehicle_id':1,'segments':[{'pickup_location':'KIX','dropoff_location':'京都','start_time':'09:00','end_time':'08:00'}]})
    def test_same_passenger_airports_fold_into_one_order_and_existing_instruction_group(self):
        route=self.route()
        for index, airport in enumerate(('KIX','ITM','UKB'), 1):
            created=service.materialize({'route_id':route['id'],'date':f'2026-10-{10+index}','driver_id':1,'vehicle_id':1,'segments':[{'position':'pre','type':'airport_pickup','pickup_location':airport,'dropoff_location':'京都','start_time':'07:00','end_time':'08:00','same_passenger':True}]})
            with closing(database.get_connection()) as conn:
                order=conn.execute('SELECT pickup_location,dropoff_location,fee_remark FROM orders WHERE id = ?', (created['run']['order_id'],)).fetchone()
            self.assertEqual(order['pickup_location'],airport)
            self.assertEqual(order['dropoff_location'],'大阪')
            self.assertIn(f'{airport} -> 京都 -> 大阪',order['fee_remark'])
            groups=run_document_service.list_run_groups(f'2026-10-{10+index}')
            self.assertEqual((len(groups),groups[0]['order_count']),(1,1))
    def test_different_passenger_segment_creates_second_acceptance_in_same_instruction_group(self):
        route=self.route()
        created=service.materialize({'route_id':route['id'],'date':'2026-10-20','driver_id':1,'vehicle_id':1,'segments':[{'position':'pre','type':'airport_pickup','pickup_location':'KIX','dropoff_location':'京都','start_time':'07:00','end_time':'08:00','same_passenger':False}]})
        with closing(database.get_connection()) as conn:
            segment=conn.execute('SELECT order_id FROM fixed_tour_run_segments').fetchone()
            orders=conn.execute('SELECT id,pickup_location,dropoff_location FROM orders ORDER BY id').fetchall()
        self.assertIsNotNone(segment['order_id'])
        self.assertEqual(len(orders),2)
        self.assertEqual((orders[1]['pickup_location'],orders[1]['dropoff_location']),('KIX','京都'))
        groups=run_document_service.list_run_groups('2026-10-20')
        self.assertEqual((len(groups),groups[0]['order_count']),(1,2))
    def test_same_passenger_post_segment_merges_into_one_order(self):
        route=self.route()
        created=service.materialize({'route_id':route['id'],'date':'2026-10-21','driver_id':1,'vehicle_id':1,'segments':[{'position':'post','type':'airport_dropoff','pickup_location':'大阪','dropoff_location':'KIX','start_time':'18:00','end_time':'19:00','same_passenger':True}]})
        with closing(database.get_connection()) as conn:
            count=conn.execute('SELECT count(*) FROM orders').fetchone()[0]
            order=conn.execute('SELECT pickup_location,dropoff_location FROM orders WHERE id=?',(created['run']['order_id'],)).fetchone()
        self.assertEqual((count,order['pickup_location'],order['dropoff_location']),(1,'京都','KIX'))
    def test_route_snapshot_and_vehicle_specific_price_are_stable(self):
        route=service.save_route({'route_code':'V1','route_name':'V1路线','stops':[{'location_name':'京都'},{'location_name':'大阪'}],'prices':[{'vehicle_type':'Alphard','price_jpy':52430},{'vehicle_type':'HiAce','price_jpy':58390}]})
        alpha=service.materialize({'route_id':route['id'],'date':'2026-10-22','driver_id':1,'vehicle_id':1})
        hiace=service.materialize({'route_id':route['id'],'date':'2026-10-23','driver_id':1,'vehicle_id':2})
        updated=service.save_route({**route,'route_name':'V2路线'},route_id=route['id'])
        with closing(database.get_connection()) as conn:
            alpha_price=conn.execute('SELECT price,remark FROM orders WHERE id=?',(alpha['run']['order_id'],)).fetchone()
            hiace_price=conn.execute('SELECT price FROM orders WHERE id=?',(hiace['run']['order_id'],)).fetchone()[0]
        self.assertEqual((alpha_price['price'],hiace_price),(52430,58390))
        self.assertEqual(json.loads(alpha_price['remark'])['fixed_tour']['version'],1)
        self.assertEqual(updated['version'],2)
        no_hiace=service.save_route({'route_code':'NO-H','route_name':'无海狮价格','stops':[{'location_name':'京都'},{'location_name':'大阪'}],'prices':[{'vehicle_type':'Alphard','price_jpy':1}]})
        with self.assertRaisesRegex(ValueError,'missing_route_vehicle_price'):
            service.materialize({'route_id':no_hiace['id'],'date':'2026-10-24','driver_id':1,'vehicle_id':2})
    def test_route_search_is_text_scoped_and_tenant_isolated(self):
        route=self.route()
        service.save_route({'route_code':'OSAKA-FAST','route_name':'大阪快捷','stops':[{'location_name':'大阪城'},{'location_name':'大阪'}],'prices':[{'vehicle_type':'Alphard','price_jpy':1}]})
        self.assertEqual([item['id'] for item in service.list_routes('KYOTO-1')],[route['id']])
        self.assertEqual([item['route_code'] for item in service.list_routes('大阪城')],['OSAKA-FAST'])
        set_current_tenant_id(2)
        self.assertEqual(service.list_routes('KYOTO-1'),[])
        set_current_tenant_id(1)
    def test_run_change_stales_existing_document_and_increments_revision(self):
        route=self.route()
        created=service.materialize({'route_id':route['id'],'date':'2026-10-10','driver_id':1,'vehicle_id':1,'segments':[{'position':'pre','type':'airport_pickup','pickup_location':'KIX','dropoff_location':'京都','start_time':'07:00','end_time':'08:00','same_passenger':True}]})
        run=created['run']
        with closing(database.get_connection()) as conn:
            conn.execute("INSERT INTO driver_run_documents (tenant_id,business_date,driver_id,vehicle_id,version,status,source_hash,file_name,file_path,file_url) VALUES (1,'2026-10-10',1,1,1,'generated','old','old.pdf','/tmp/old.pdf','')")
            conn.commit()
        result=service.update_run(run['id'], {'start_time':'09:00','segments':[{'position':'post','type':'airport_dropoff','pickup_location':'大阪','dropoff_location':'KIX','start_time':'18:00','end_time':'19:00','same_passenger':False}]})
        self.assertTrue(result['stale'])
        with closing(database.get_connection()) as conn:
            order=conn.execute('SELECT run_revision,start_time,remark FROM orders WHERE id = ?', (run['order_id'],)).fetchone()
            document=conn.execute('SELECT status FROM driver_run_documents').fetchone()
            segment=conn.execute('SELECT segment_position,same_passenger,snapshot_json FROM fixed_tour_run_segments').fetchone()
        self.assertEqual((order['run_revision'],order['start_time'],document['status']),(2,'09:00','stale'))
        self.assertEqual((segment['segment_position'],segment['same_passenger']),('post',0))
        self.assertEqual(json.loads(segment['snapshot_json'])['segment_type'],'airport_dropoff')
        self.assertIn('airport_dropoff',order['remark'])
    def test_today_run_reuses_workflow_and_tenant_scoped_location(self):
        route=self.route()
        created=service.materialize({'route_id':route['id'],'date':'2026-10-10','driver_id':1,'vehicle_id':1,'segments':[{'position':'pre','pickup_location':'KIX','dropoff_location':'京都','same_passenger':True},{'position':'post','pickup_location':'大阪','dropoff_location':'KIX','same_passenger':False}]})
        run=created['run']
        with closing(database.get_connection()) as conn:
            conn.execute("INSERT INTO driver_workflow_events (tenant_id,driver_id,assignment_id,order_id,event_type,event_time,location_text) VALUES (1,1,?,?, 'roll_call_out','2026-10-10 07:00:00','大阪车库')", (run['assignment_id'],run['order_id']))
            conn.execute("INSERT INTO driver_workflow_events (tenant_id,driver_id,assignment_id,order_id,event_type,event_time,location_text) VALUES (1,1,?,?, 'roll_call_in','2026-10-10 20:00:00','大阪车库')", (run['assignment_id'],run['order_id']))
            conn.execute("INSERT INTO location_logs (tenant_id,driver_id,vehicle_id,assignment_id,order_id,latitude,longitude,location_text,reported_at) VALUES (1,1,1,?,?,34.68,135.50,'大阪市内','2026-10-10 12:00:00')", (run['assignment_id'],run['order_id']))
            conn.execute("INSERT INTO location_logs (tenant_id,driver_id,location_text,reported_at) VALUES (2,1,'跨租户位置','2026-10-10 21:00:00')")
            conn.execute("INSERT INTO driver_run_documents (tenant_id,business_date,driver_id,vehicle_id,version,status,source_hash,file_name,file_path,file_url) VALUES (1,'2026-10-10',1,1,1,'reviewed','hash','fixed.pdf','/tmp/fixed.pdf','')")
            conn.commit()
        runs=service.list_today_runs('2026-10-10')
        self.assertEqual(len(runs),1)
        item=runs[0]
        self.assertEqual((item['route_name'],item['order_count'],item['pdf_status']['status']),('京都经典',1,'reviewed'))
        self.assertEqual((len(item['pre_segments']),len(item['post_segments'])),(1,1))
        self.assertEqual(item['roll_call_out']['location_text'],'大阪车库')
        self.assertEqual(item['roll_call_in']['event_type'],'roll_call_in')
        self.assertEqual(item['latest_location']['location_text'],'大阪市内')
        self.assertEqual(item['execution_status'],'draft')
        set_current_tenant_id(2)
        self.assertEqual(service.list_today_runs('2026-10-10'),[])

    def test_published_fixed_tour_assignment_appears_in_driver_chain(self):
        route = self.route()
        created = service.materialize({'route_id': route['id'], 'date': '2026-10-25', 'driver_id': 1, 'vehicle_id': 1})
        with closing(database.get_connection()) as conn:
            conn.execute("UPDATE assignments SET execution_status = 'assigned', published_at = CURRENT_TIMESTAMP WHERE id = ?", (created['run']['assignment_id'],))
            conn.commit()
        assignments = list_driver_assignments(1)
        self.assertEqual(len(assignments), 1)
        self.assertEqual((assignments[0]['assignment_id'], assignments[0]['order_id']), (created['run']['assignment_id'], created['run']['order_id']))
    def test_route_version_and_tenant_scope(self):
        route=self.route(); updated=service.save_route({**route,'route_name':'京都经典 V2'}, route_id=route['id'])
        self.assertEqual(updated['version'], 2)
        set_current_tenant_id(2)
        self.assertEqual(service.list_routes(), [])

if __name__ == '__main__': unittest.main()
