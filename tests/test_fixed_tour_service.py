import json
import tempfile
import unittest
import uuid
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
    def test_duplicate_route_code_returns_domain_error_but_update_keeps_own_code(self):
        route = self.route()
        with self.assertRaisesRegex(ValueError, 'fixed_tour_route_code_exists'):
            self.route()
        updated = service.save_route({**route, 'route_name': '京都经典 V2'}, route_id=route['id'])
        self.assertEqual((updated['route_code'], updated['route_name'], updated['version']), ('KYOTO-1', '京都经典 V2', 2))

    def test_applicant_company_and_application_method_are_independent(self):
        route = service.save_route({
            'route_code': 'SPI-1',
            'route_name': 'SPI 路线',
            'applicant_name': 'SPI',
            'application_method': '電話',
            'stops': [{'location_name': '日本橋駅'}, {'location_name': '日本橋駅'}],
        })
        self.assertEqual((route['applicant_name'], route['application_method']), ('SPI', '電話'))

    def test_delete_unused_route_removes_template_children_and_is_tenant_scoped(self):
        route = self.route()
        set_current_tenant_id(2)
        self.assertFalse(service.delete_route(route['id']))
        set_current_tenant_id(1)
        self.assertTrue(service.delete_route(route['id']))
        self.assertIsNone(service.route_detail(route['id']))
        with closing(database.get_connection()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM fixed_tour_route_stops WHERE route_id = ?', (route['id'],)).fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM fixed_tour_route_prices WHERE route_id = ?', (route['id'],)).fetchone()[0], 0)

    def test_delete_used_route_is_blocked_to_preserve_run_history(self):
        route = self.route()
        service.materialize({'route_id': route['id'], 'date': '2026-10-30', 'driver_id': 1, 'vehicle_id': 1})
        with self.assertRaisesRegex(ValueError, 'fixed_tour_route_in_use'):
            service.delete_route(route['id'])
        self.assertIsNotNone(service.route_detail(route['id']))
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

    def test_effective_price_override_is_saved_on_run_not_route_template(self):
        route = self.route()
        created = service.materialize({'route_id': route['id'], 'date': '2026-10-26', 'driver_id': 1, 'vehicle_id': 1, 'effective_price_jpy': '60000'})
        with closing(database.get_connection()) as conn:
            order = conn.execute('SELECT price,price_jpy,remark FROM orders WHERE id = ?', (created['run']['order_id'],)).fetchone()
        snapshot = json.loads(order['remark'])['fixed_tour']
        self.assertEqual((order['price'], order['price_jpy']), (60000, 60000))
        self.assertEqual((snapshot['suggested_price_jpy'], snapshot['effective_price_jpy']), (52430, 60000))
        self.assertEqual(service.route_detail(route['id'])['prices'][0]['price_jpy'], 52430)

    def test_manual_effective_price_allows_vehicle_without_suggested_price(self):
        route = service.save_route({
            'route_code': 'MANUAL-PRICE',
            'route_name': '手动金额路线',
            'stops': [{'location_name': '日本橋駅'}, {'location_name': '奈良公園'}],
            'prices': [],
        })
        created = service.materialize({
            'route_id': route['id'],
            'date': '2026-10-27',
            'driver_id': 1,
            'vehicle_id': 2,
            'effective_price_jpy': '58390',
        })
        with closing(database.get_connection()) as conn:
            order = conn.execute('SELECT price,remark FROM orders WHERE id = ?', (created['run']['order_id'],)).fetchone()
        snapshot = json.loads(order['remark'])['fixed_tour']
        self.assertEqual(order['price'], 58390)
        self.assertIsNone(snapshot['suggested_price_jpy'])
        self.assertEqual(snapshot['effective_price_jpy'], 58390)
    def test_route_search_is_text_scoped_and_tenant_isolated(self):
        route=self.route()
        service.save_route({'route_code':'OSAKA-FAST','route_name':'大阪快捷','stops':[{'location_name':'大阪城'},{'location_name':'大阪'}],'prices':[{'vehicle_type':'Alphard','price_jpy':1}]})
        self.assertEqual([item['id'] for item in service.list_routes('KYOTO-1')],[route['id']])
        self.assertEqual([item['route_code'] for item in service.list_routes('大阪城')],['OSAKA-FAST'])
        set_current_tenant_id(2)
        self.assertEqual(service.list_routes('KYOTO-1'),[])
        set_current_tenant_id(1)

    def test_mobile_multiday_preset_search_and_time_validation(self):
        route = service.save_route({
            'route_code': 'KUMANO-2D',
            'route_name': '熊野古道两日',
            'description': '大阪出发，第二天返回',
            'trip_type': 'multi_day',
            'duration_days': 2,
            'route_summary': '大阪 → 那智勝浦 → 熊野本宮 → 大阪',
            'stops': [
                {'day_index': 1, 'location_name': '大阪市内', 'default_departure_time': '08:00'},
                {'day_index': 1, 'location_name': '那智勝浦', 'default_arrival_time': '13:00'},
                {'day_index': 2, 'location_name': '熊野本宮大社', 'default_arrival_time': '09:30'},
                {'day_index': 2, 'location_name': '大阪市内', 'default_arrival_time': '18:00'},
            ],
        })
        self.assertEqual((route['trip_type'], route['duration_days'], len(route['days'])), ('multi_day', 2, 2))
        self.assertEqual(service.list_routes('熊野本宮')[0]['id'], route['id'])
        with self.assertRaisesRegex(ValueError, 'fixed_tour_time_invalid'):
            service.save_route({
                'route_code': 'BAD-TIME', 'route_name': '错误时间',
                'stops': [{'location_name': 'A', 'default_departure_time': '24:10'}, {'location_name': 'B'}],
            })

    def test_save_and_use_is_idempotent_and_copies_route_nodes(self):
        payload = {
            'client_request_id': 'mobile-save-use-1',
            'business_start_date': '2026-11-01',
            'route': {
                'route_name': '京都私人两日',
                'trip_type': 'multi_day',
                'duration_days': 2,
                'stops': [
                    {'day_index': 1, 'location_name': '日本橋駅', 'default_departure_time': '08:00'},
                    {'day_index': 1, 'location_name': '清水寺', 'default_arrival_time': '10:00'},
                    {'day_index': 2, 'location_name': '嵐山', 'default_departure_time': '09:00'},
                    {'day_index': 2, 'location_name': '京都駅八条口', 'default_arrival_time': '17:30'},
                ],
            },
        }
        first = service.save_preset_and_create_draft(payload)
        second = service.save_preset_and_create_draft(payload)
        self.assertTrue(first['created'])
        self.assertFalse(second['created'])
        self.assertEqual(first['draft']['id'], second['draft']['id'])
        preset_node_ids = {stop['preset_node_id'] for stop in first['route']['stops']}
        draft_nodes = first['draft']['route_snapshot']['stops']
        self.assertTrue(all(node['route_node_id'].startswith('node-') for node in draft_nodes))
        self.assertTrue(all(node['time_confirmed'] is False for node in draft_nodes))
        self.assertEqual(first['draft']['route_snapshot']['time_confirmation_status'], 'pending')
        self.assertTrue(preset_node_ids.isdisjoint({node['route_node_id'] for node in draft_nodes}))
        self.assertEqual([day['date'] for day in first['draft']['route_snapshot']['days']], ['2026-11-01', '2026-11-02'])
        with closing(database.get_connection()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM fixed_tour_routes').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM fixed_tour_charter_drafts').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 1)

    def test_save_and_use_recovers_order_when_draft_insert_previously_failed(self):
        request_id = 'mobile-recover-after-draft-failure'
        route_payload = {
            'route_name': '京都奈良日本桥日游',
            'trip_type': 'day',
            'duration_days': 1,
            'stops': [
                {'location_name': '京都', 'default_departure_time': '08:00'},
                {'location_name': '奈良公园', 'default_arrival_time': '10:00', 'default_departure_time': '12:00'},
                {'location_name': '日本桥2号口', 'default_arrival_time': '18:00'},
            ],
        }
        route_code = f"DT-MOBILE-{uuid.uuid5(uuid.NAMESPACE_URL, f'1:{request_id}').hex[:12].upper()}"
        preset = service.save_route({**route_payload, 'route_code': route_code})
        snapshot = service._draft_snapshot(
            preset,
            '2026-11-06',
            source_preset_id=preset['id'],
            source_preset_version=preset['version'],
        )
        orphan = service.create_order(service._charter_order_payload(snapshot, None, request_id))

        recovered = service.save_preset_and_create_draft({
            'client_request_id': request_id,
            'business_start_date': '2026-11-06',
            'route': route_payload,
        })
        repeated = service.save_preset_and_create_draft({
            'client_request_id': request_id,
            'business_start_date': '2026-11-06',
            'route': route_payload,
        })

        self.assertTrue(recovered['created'])
        self.assertFalse(repeated['created'])
        self.assertEqual(recovered['draft']['id'], repeated['draft']['id'])
        self.assertEqual(recovered['draft']['order_id'], orphan['id'])
        with closing(database.get_connection()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM fixed_tour_routes').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM fixed_tour_charter_drafts').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 1)
            order = conn.execute('SELECT pickup_location,dropoff_location,remark FROM orders WHERE id = ?', (orphan['id'],)).fetchone()
        self.assertEqual((order['pickup_location'], order['dropoff_location']), ('京都', '日本桥2号口'))
        self.assertEqual(json.loads(order['remark'])['fixed_tour']['client_request_id'], request_id)

        edited_stops = [dict(node) for node in recovered['draft']['route_snapshot']['stops']]
        edited_stops[1]['location'] = edited_stops[1]['location_name'] = '奈良公园东门（本次）'
        updated = service.update_charter_draft(recovered['draft']['id'], {
            'business_start_date': '2026-11-06',
            'route': {'route_name': '京都奈良日本桥日游（本次）', 'stops': edited_stops},
        })
        reopened = service.charter_draft_detail(updated['id'])
        preset_after = service.list_routes('京都奈良日本桥')[0]
        self.assertEqual(reopened['route_snapshot']['stops'][1]['location'], '奈良公园东门（本次）')
        self.assertEqual(preset_after['stops'][1]['location_name'], '奈良公园')
        self.assertEqual(preset_after['id'], recovered['route']['id'])

    def test_draft_edit_isolated_from_preset_and_preserves_node_ids(self):
        route = self.route()
        created = service.create_charter_draft({
            'source_preset_id': route['id'],
            'business_start_date': '2026-11-03',
            'client_request_id': 'use-existing-1',
        })['draft']
        original_ids = [node['route_node_id'] for node in created['route_snapshot']['stops']]
        edited_stops = [dict(node) for node in created['route_snapshot']['stops']]
        edited_stops[0]['location_name'] = edited_stops[0]['location'] = '地下鉄なんば駅14番出口'
        updated = service.update_charter_draft(created['id'], {
            'business_start_date': '2026-11-04',
            'route': {'route_name': '本次专用路线', 'stops': edited_stops},
        })
        self.assertEqual([node['route_node_id'] for node in updated['route_snapshot']['stops']], original_ids)
        self.assertEqual(updated['route_snapshot']['stops'][0]['location'], '地下鉄なんば駅14番出口')
        self.assertEqual(service.route_detail(route['id'])['stops'][0]['location_name'], '京都')
        service.save_route({**route, 'route_name': '模板后来修改'}, route_id=route['id'])
        reopened = service.charter_draft_detail(created['id'])
        self.assertEqual(reopened['route_snapshot']['route_name'], '本次专用路线')
        self.assertEqual(reopened['source_preset_version'], 1)

    def test_one_time_custom_charter_does_not_create_preset(self):
        result = service.create_charter_draft({
            'client_request_id': 'custom-once-1',
            'business_start_date': '2026-11-05',
            'route': {
                'route_name': '一次性私人订制',
                'trip_type': 'day',
                'stops': [
                    {'location_name': '大阪市泛称原样保留', 'default_departure_time': '09:00'},
                    {'location_name': '地下鉄心斎橋駅4-B出口', 'default_arrival_time': '18:00'},
                ],
            },
        })
        draft = result['draft']
        self.assertIsNone(draft['source_preset_id'])
        self.assertEqual(draft['route_snapshot']['stops'][0]['location'], '大阪市泛称原样保留')
        with closing(database.get_connection()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM fixed_tour_routes').fetchone()[0], 0)
            order = conn.execute('SELECT pickup_location,dropoff_location,remark FROM orders WHERE id = ?', (draft['order_id'],)).fetchone()
        self.assertEqual((order['pickup_location'], order['dropoff_location']), ('大阪市泛称原样保留', '地下鉄心斎橋駅4-B出口'))
        self.assertIn('route_node_id', order['remark'])
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
        with closing(database.get_connection()) as conn:
            route_count = conn.execute('SELECT COUNT(*) FROM fixed_tour_routes WHERE tenant_id = 1 AND route_code = ?', ('KYOTO-1',)).fetchone()[0]
        self.assertEqual((updated['route_name'], updated['version'], route_count), ('京都经典 V2', 2, 1))
        set_current_tenant_id(2)
        self.assertEqual(service.list_routes(), [])

    def test_phase2c2_options_report_conflicts_and_document_generation_is_idempotent(self):
        route = service.save_route({
            'route_code': 'C2-QUICK', 'route_name': '京都・奈良快速派车',
            'stops': [
                {'location_name': '京都駅', 'stop_type': 'pickup', 'default_departure_time': '09:00'},
                {'location_name': '奈良公園', 'stop_type': 'waypoint', 'default_arrival_time': '11:00', 'default_departure_time': '13:00'},
                {'location_name': '日本橋2号口', 'stop_type': 'dropoff', 'default_arrival_time': '18:00'},
            ],
        })
        created = service.create_charter_draft({
            'source_preset_id': route['id'], 'business_start_date': '2026-11-12',
            'client_request_id': 'phase2c2-quick-1',
        })
        actor = {'id': 1, 'tenant_id': 1, 'role': 'operations_manager', 'username': 'ops'}
        first = service.generate_charter_draft_documents(created['draft']['id'], {'driver_id': 1, 'vehicle_id': 1}, actor)
        second = service.generate_charter_draft_documents(created['draft']['id'], {'driver_id': 1, 'vehicle_id': 1}, actor)
        self.assertEqual(first['group_key'], '2026-11-12:1:1')
        self.assertEqual(first['document']['id'], second['document']['id'])
        self.assertEqual(first['document']['page_count'], 2)
        self.assertTrue(first['document']['document_id'])
        self.assertTrue(first['document']['document_version_id'])
        self.assertTrue(first['document']['source_sha256'])
        self.assertTrue(first['document']['renderer_version'])
        self.assertTrue(second['assignment']['reused'])
        self.assertEqual(second['draft']['status'], 'document_draft')
        self.assertTrue(second['preview']['nodes'])
        options = service.charter_dispatch_options('2026-11-12', created['draft']['id'])
        self.assertFalse(options['drivers'][0]['date_conflict'])
        self.assertFalse(options['vehicles'][0]['date_conflict'])
        with closing(database.get_connection()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM assignments WHERE order_id = ? AND status = 'active'", (created['draft']['order_id'],)).fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM driver_run_documents WHERE business_date = '2026-11-12'").fetchone()[0], 1)

if __name__ == '__main__': unittest.main()
