"""Cloudflare D1 queue import and sync: no network or Telegram calls."""
import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
import ngo_grants_ai as a


class GatewayTests(unittest.TestCase):
    def test_import_once_and_no_personal_data(self):
        with TemporaryDirectory() as root:
            state = a.default_state()
            requests = {'requests': [
                {'id': 272839001, 'topic': 'Гранти для культурних організацій', 'requested_at': '2026-10-16T16:00:00Z'},
                {'id': 272839002, 'topic': 'Стипендії для українських науковців', 'requested_at': '2026-10-16T16:00:02Z'},
            ]}
            with patch.object(a, 'gateway_api', return_value=requests), patch.object(a, 'save_state'):
                a.import_gateway_requests(state)
                a.import_gateway_requests(state)
            self.assertEqual(len(state['queue']), 2)
            self.assertEqual(state['gateway_seen_ids'], [272839001, 272839002])
            self.assertEqual(state['published'], [])

    def test_sync_copies_previous_catalog_and_quota(self):
        s=a.default_state()
        s['published']=[{'id':123,'topic':'Гранти для документального кіно','title':'Кіно',
                         'channel_url':'https://t.me/ngo_grants/3255','valid_until':'2026-11-30',
                         'published_on':'2026-10-16'}]
        s['gateway_seen_ids']=[35,36]
        s['queue']=[{'id':36,'topic':'Мистецькі конкурси','requested_at':'2026-10-16T10:00:00Z'}]
        s['users_days']={'a'*30:'2026-10-16'}
        sent=[]
        def fake_gateway(path,data=None):
            sent.append((path,data))
            return {'ok':True,'published':len(data['published']),'acknowledged':len(data['ack_ids'])}
        with patch.dict(a.os.environ,{'NGO_BOT_GATEWAY_URL':'https://test.worker.dev','NGO_BOT_SYNC_SECRET':'fake'}),patch.object(a,'gateway_api',side_effect=fake_gateway):
            a.notify_gateway(s)
        self.assertEqual(sent[0][0],'/internal/sync')
        self.assertEqual(sent[0][1]['ack_ids'],[35,36])
        self.assertEqual(sent[0][1]['queue_ids'],[36])
        self.assertEqual(sent[0][1]['user_days'],{'a'*30:'2026-10-16'})

    def test_already_published_duplicate_is_not_new_queued(self):
        state=a.default_state()
        state['published']=[{'id':777,'topic':'Гранти для документального кіно','title':'Гранти для документального кіно',
                             'channel_url':'https://t.me/ngo_grants/3255', 'valid_until':'2026-12-15'}]
        payload={'requests':[{'id':778,'topic':'Гранти для документального кіно','requested_at':'2026-10-16T17:00:00Z'}]}
        with patch.object(a,'gateway_api',return_value=payload),patch.object(a,'save_state'),patch.object(a,'today_kyiv',return_value=a.date(2026,10,16)):
            a.import_gateway_requests(state)
        self.assertEqual(state['queue'],[])
        self.assertEqual(state['gateway_seen_ids'],[778])


if __name__=='__main__': unittest.main()
