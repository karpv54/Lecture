"""Provider setup contract checks with in-memory official response shapes."""
import argparse
import asyncio
import json
import io
from contextlib import redirect_stdout
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/gradio'))
import httpx
import setup_providers as setup

class SetupTests(unittest.IsolatedAsyncioTestCase):
    async def run_setup(self,existing=False,check=False,workspace='workspace',editor_email='owner@example.invalid'):
        calls=[];registry={};temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        destination=Path(temporary.name)/'setup.json'
        if existing:
            for a in setup.CATALOG:
                registry[a['app_name']]={'name':a['app_name'],'sId':a['id'],'instructions':setup.bundle(a)['instructions'],
                                        'model':{'providerId':'test-provider','modelId':'test-model'}}
        def response(request):
            calls.append((request.method,request.url.path))
            path=request.url.path
            if path=='/api/user':return httpx.Response(200,json={'user':{'workspaces':[{'sId':'workspace'}]}})
            if '/voices/' in path:return httpx.Response(200,json={'uid':setup.GASPARD,'name':'Gaspard'})
            if path.endswith('/import'):
                payload=json.loads(request.content)
                self.assertEqual(payload['toolset'],[])
                self.assertEqual(payload['editors'],[editor_email])
                self.assertEqual(payload['agent']['avatar_url'],'https://dust.tt/static/systemavatar/dust_avatar_full.png')
                self.assertEqual(set(payload['generation_settings']),{'provider_id','model_id','temperature','reasoning_effort'})
                self.assertIn(setup.MARKER,payload['instructions'])
                agent={'name':payload['agent']['handle'],'sId':payload['agent']['handle'],
                       'instructions':payload['instructions'],'model':{'providerId':'test','modelId':'model'}}
                registry[agent['name']]=agent
                return httpx.Response(200,json={'agentConfiguration':agent,'skippedActions':[]})
            if path.endswith('/agent_configurations'):
                # Dust rejects the OAuth-only list view even for a valid admin API key.
                if request.url.params.get('view') in {'list','favorites'}:
                    return httpx.Response(401,json={'error':{'type':'invalid_request_error',
                        'message':'The user must be authenticated with oAuth to retrieve list agents.'}})
                if request.url.params.get('view') != 'all_unrestricted':
                    # Public all view omits the hidden app agents, even for admin keys.
                    return httpx.Response(200,json={'agentConfigurations':[
                        {'sId':'dust','name':'Dust','model':{'providerId':'test-provider','modelId':'test-model'}}]})
                return httpx.Response(200,json={'agentConfigurations':list(registry.values())+
                    [{'sId':'dust','name':'Dust','model':{'providerId':'test-provider','modelId':'test-model'}}]})
            for a in registry.values():
                if path.endswith('/'+a['sId']):return httpx.Response(200,json={'agentConfiguration':a})
            return httpx.Response(404)
        real_client=httpx.AsyncClient
        def factory(**kwargs):return real_client(transport=httpx.MockTransport(response),**kwargs)
        cfg={'dust_key':'test-key','gradium_key':'test-key','workspace':workspace,'dust_base_url':'https://dust.tt',
             'gradium_base_url':'https://eu.api.gradium.ai/api/','voice_id':''}
        args=argparse.Namespace(provision=not check,update_managed=False,check=check)
        with redirect_stdout(io.StringIO()),patch.dict(setup.os.environ,{'DUST_EDITOR_EMAIL':editor_email,'DUST_MODEL_PROVIDER':'','DUST_MODEL_ID':''}),patch.object(setup,'settings',return_value=cfg),patch.object(setup,'SETUP_FILE',destination),patch.object(setup.httpx,'AsyncClient',factory):
            await setup.configure(args)
        return calls,json.loads(destination.read_text()) if destination.exists() else None
    async def test_provisions_all_five_without_inference(self):
        calls,saved=await self.run_setup()
        self.assertEqual(len(saved['agents']),5)
        self.assertEqual(sum(method=='POST' for method,path in calls),5)
        self.assertFalse(any('conversations' in path or 'speech' in path for method,path in calls))
        self.assertNotIn('test-key',json.dumps(saved))
    async def test_existing_agents_are_reused_without_duplicates(self):
        calls,saved=await self.run_setup(existing=True)
        self.assertTrue(all(method=='GET' for method,path in calls))
    async def test_check_is_read_only_and_does_not_write_file(self):
        calls,saved=await self.run_setup(existing=True,check=True)
        self.assertIsNone(saved);self.assertTrue(all(method=='GET' for method,path in calls))
    async def test_unique_workspace_discovery(self):
        calls,saved=await self.run_setup(existing=True,workspace='')
        self.assertEqual(saved['workspace'],'workspace')
        self.assertIn(('GET','/api/user'),calls)


    async def test_missing_editor_is_explained_before_import(self):
        with self.assertRaisesRegex(RuntimeError, 'DUST_EDITOR_EMAIL'):
            await self.run_setup(editor_email='')

    async def test_existing_agents_need_no_editor_setting(self):
        calls, saved = await self.run_setup(existing=True, editor_email='')
        self.assertTrue(all(method == 'GET' for method, path in calls))

    async def test_read_only_check_needs_no_editor_setting(self):
        calls, saved = await self.run_setup(existing=True, check=True, editor_email='')
        self.assertIsNone(saved)
        self.assertTrue(all(method == 'GET' for method, path in calls))

class SetupErrorTests(unittest.IsolatedAsyncioTestCase):
    async def error_for(self, url, status):
        sentinel = 'private-test-secret-never-log'
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(status, json={'error': sentinel}))) as client:
            with self.assertRaises(RuntimeError) as caught:
                await setup.checked(client, 'GET', url + '?secret=' + sentinel,
                                    headers={'Authorization': 'Bearer ' + sentinel})
        message = str(caught.exception)
        self.assertNotIn(sentinel, message)
        self.assertNotIn('private-workspace', message)
        return message

    async def test_dust_401_names_key_without_leaking_response(self):
        message = await self.error_for('https://eu.dust.tt/api/v1/w/private-workspace/agents', 401)
        self.assertIn('Dust configuration request', message)
        self.assertIn('DUST_API_KEY', message)
        self.assertIn('DUST_WORKSPACE_ID', message)

    async def test_gradium_401_names_its_own_key(self):
        message = await self.error_for('https://eu.api.gradium.ai/api/voices/example', 401)
        self.assertIn('Gradium configuration request', message)
        self.assertIn('GRADIUM_API_KEY', message)
        self.assertNotIn('DUST_API_KEY', message)

    async def test_access_denied_is_distinguished_from_authentication(self):
        message = await self.error_for('https://dust.tt/api/agents', 403)
        self.assertIn('Access was denied', message)
        self.assertIn('permissions', message)

    async def test_rate_limit_does_not_recommend_replacing_key(self):
        message = await self.error_for('https://dust.tt/api/agents', 429)
        self.assertIn('rate or usage limit', message)
        self.assertNotIn('full active secret key', message)


    async def test_oauth_only_view_error_does_not_blame_valid_api_key(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(401, json={'error':{
                    'type':'invalid_request_error',
                    'message':'The user must be authenticated with oAuth to retrieve list agents.'}}))) as client:
            with self.assertRaises(RuntimeError) as caught:
                await setup.checked(client, 'GET', 'https://dust.tt/api/agents', params={'view':'list'})
        self.assertIn('view=all_unrestricted', str(caught.exception))
        self.assertNotIn('Check DUST_API_KEY', str(caught.exception))

if __name__=='__main__':unittest.main()
