"""Offline behavioral checks. All provider responses are explicit test doubles."""
import argparse
import asyncio
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/gradio'))
import httpx
from curriculum import ANCHORS, cards_for, method_catalogue
from dust_client import DustConversation, DustTeam, speech_from_reply
from lesson import Lesson
from method_adapter import MethodAdapter
from settings import VoiceIssue
from store import Store

class FakeTeam:
    def __init__(self):
        self.intent='answer';self.anchor='';self.adaptation='continue';self.calls={}
    async def interpret(self,text,context):
        return {'intent':self.intent,'anchor':self.anchor}
    async def choose(self,candidates,context):
        return candidates[0]['id']
    async def validate_card(self,card):
        return None
    async def support(self,text,context):
        return self.adaptation

def method_session(**updates):
    value={'etape':'decoupage','consentement_prenom':'accord','type_ancrage':'mot_familier',
        'mot_depart':'moto','ancrage_confirme':True,'phonologie_validee':True,'etape_terminee':False,
        'etapes_validees':['ancrage'],'cible_id':'moto:parts','score':75,'autre_score_bloquant':False,
        'cible_revision_id':'','maitrises':[],'evaluation':'reussite','modalite':'oral',
        'source_evaluation':'accompagnant','interaction_id':'attempt','interaction_deja_appliquee':False,
        'resultats_groupe':[],'ton':'normal'}
    value.update(updates);return value

class MethodTests(unittest.TestCase):
    def setUp(self):
        self.adapter=MethodAdapter()
        self.catalogue=method_catalogue(cards_for('moto'),ANCHORS['moto'])
    def context(self,**values):
        return self.adapter.prepare(method_session(**values),self.catalogue)
    def test_transcript_does_not_score(self):
        context=self.context(source_evaluation='transcription')
        self.assertEqual(context['preuve']['statut'],'non_evaluable')
        self.assertEqual(context['bilan']['score_suggere'],75)
    def test_independent_success_subtracts_25(self):
        self.assertEqual(self.context()['bilan']['score_suggere'],50)
    def test_unknown_score_stays_unknown(self):
        self.assertEqual(self.context(score=-1)['bilan']['score_suggere'],-1)
    def test_score_floor(self):
        self.assertEqual(self.context(score=10)['bilan']['score_suggere'],0)
    def test_duplicate_does_not_score(self):
        self.assertEqual(self.context(interaction_deja_appliquee=True)['bilan']['score_suggere'],75)
    def test_invalid_candidate_rejected(self):
        result=self.adapter.finish(self.context(),{'activite_id':'invented','justification':''})
        self.assertEqual(result['activite_id'],'')
    def test_correct_catalogue_candidate_accepted(self):
        result=self.adapter.finish(self.context(score=25),{'activite_id':'moto:parts:apprentissage','justification':''})
        self.assertEqual(result['activite_id'],'moto:parts:apprentissage')
    def test_untaught_prerequisites_rejected(self):
        result=self.adapter.finish(self.context(etape='assemblage',etapes_validees=STEPS[:4]),
            {'activite_id':'moto:whole:apprentissage','justification':''})
        self.assertEqual(result['activite_id'],'')
    def test_wrong_anchor_rejected(self):
        result=self.adapter.finish(self.context(mot_depart='Ali'),{'activite_id':'moto:parts:apprentissage','justification':''})
        self.assertEqual(result['activite_id'],'')
    def test_disjoint_five_results(self):
        context=self.context(resultats_groupe=['echec','echec','echec','reussite'])
        self.assertTrue(context['bilan']['groupe_termine'])
        self.assertEqual(context['bilan']['ton_suggere'],'doux')

STEPS=['ancrage','decoupage','lettres_sons','graphies_composees','assemblage','transfert','mots_utiles']

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'test.sqlite3')
    def tearDown(self):self.tmp.cleanup()
    def test_refusal_writes_no_profile(self):
        self.assertFalse(self.store.save('x',{'consent':False}))
        self.assertIsNone(self.store.load('x'))
    def test_deduplication_is_transactional(self):
        self.assertTrue(self.store.save('x',{'consent':True,'score':75},{'id':'turn'}))
        self.assertFalse(self.store.save('x',{'consent':True,'score':50},{'id':'turn'}))
        self.assertEqual(self.store.load('x')['score'],75)
    def test_forget_removes_history_and_profile(self):
        self.store.save('x',{'consent':True},{'id':'turn'})
        self.store.forget('x')
        self.assertIsNone(self.store.load('x'))
        with self.store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],0)

class LessonTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'test.sqlite3')
        self.team=FakeTeam();self.lesson=Lesson('person',self.store,self.team)
    def tearDown(self):self.tmp.cleanup()
    async def say(self,intent,anchor=''):
        self.team.intent=intent;self.team.anchor=anchor
        return await self.lesson.turn('not stored')
    async def start(self,consent='yes',anchor='moto'):
        await self.say(consent);await self.say('answer',anchor);return await self.say('yes')
    async def test_consent_must_be_explicit(self):
        await self.say('answer')
        self.assertEqual(self.lesson.stage,'consent');self.assertIsNone(self.store.load('person'))
    async def test_attempt_before_model_and_picture(self):
        reply=await self.start()
        self.assertNotIn('moto',reply['spoken_text'].lower())
        self.assertEqual(reply['visual']['emoji'],'')
        self.assertEqual(self.lesson.phase,'INDEPENDENT_ATTEMPT')
    async def test_transcript_never_changes_scores(self):
        await self.start();await self.say('answer')
        self.assertEqual(self.lesson.state['scores'],{})
        self.assertEqual(self.lesson.state['mastered'],[])
        self.assertNotIn('not stored',json.dumps(self.store.load('person')))
    async def test_help_is_not_assessable(self):
        await self.start();await self.say('help')
        self.assertFalse(self.lesson.coach_snapshot()['can_assess'])
    async def test_success_requires_actual_attempt(self):
        await self.start()
        with self.assertRaises(ValueError):await self.lesson.assess(self.lesson.attempt,'reussite')
    async def test_confirmed_word_reveals_matching_picture_once(self):
        await self.start();await self.say('answer');attempt=self.lesson.attempt
        reply=await self.lesson.assess(attempt,'reussite')
        self.assertEqual(reply['visual']['emoji'],'🏍️')
        self.assertEqual(self.lesson.state['scores']['moto:first'],75)
        with self.assertRaises(ValueError):await self.lesson.assess(attempt,'reussite')
    async def test_stale_observation_rejected(self):
        await self.start();await self.say('answer');attempt=self.lesson.attempt
        await self.say('no')
        with self.assertRaises(ValueError):await self.lesson.assess(attempt,'reussite')
    async def test_guided_success_no_mastery(self):
        await self.start();await self.say('help');await self.say('answer')
        await self.lesson.assess(self.lesson.attempt,'reussite')
        self.assertEqual(self.lesson.state['scores'],{})
    async def test_four_confirmations_master_one_target(self):
        await self.start()
        for _ in range(4):
            self.lesson.begin_attempt();await self.say('answer')
            await self.lesson.assess(self.lesson.attempt,'reussite')
        self.assertEqual(self.lesson.state['scores']['moto:first'],0)
        self.assertIn('moto:first',self.lesson.state['mastered'])
    async def test_failure_adds_25_removes_mastery_preserves_history(self):
        await self.start();self.lesson.state['scores']['moto:first']=0;self.lesson.state['mastered']=['moto:first']
        await self.say('answer');await self.lesson.assess(self.lesson.attempt,'echec')
        self.assertEqual(self.lesson.state['scores']['moto:first'],25)
        self.assertNotIn('moto:first',self.lesson.state['mastered'])
        with self.store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)
    async def test_unknown_name_does_not_invent_segmentation(self):
        await self.say('no');reply=await self.say('answer','an-unreviewed-name')
        self.assertEqual(self.lesson.stage,'anchor')
        self.assertIn('vérification',reply['spoken_text'])
    async def test_refused_storage_is_ephemeral(self):
        await self.start('no');await self.say('answer');await self.lesson.assess(self.lesson.attempt,'reussite')
        self.assertIsNone(self.store.load('person'))
    async def test_forget_requires_confirmation(self):
        await self.start();await self.say('forget')
        self.assertIsNotNone(self.store.load('person'))
        await self.say('yes');self.assertIsNone(self.store.load('person'))
        self.assertFalse(self.lesson.state['consent'])
    async def test_resume_keeps_personal_progress(self):
        await self.start();await self.say('answer');await self.say('no')
        self.lesson=Lesson('person',self.store,self.team)
        self.assertEqual(self.lesson.stage,'resume')
        await self.say('yes')
        self.assertIn('moto:first',self.lesson.state['done'])

class CatalogueTests(unittest.TestCase):
    def test_all_catalogue_paths_have_safe_finite_cards(self):
        for anchor in ANCHORS:
            cards=cards_for(anchor)
            self.assertEqual(len({c['id'] for c in cards}),len(cards),anchor)
            self.assertTrue(any(c['etape']=='transfert' for c in cards),anchor)
            for c in cards:
                self.assertLessEqual(len(c['model'])+25,400)
                self.assertTrue(all(0<len(tile)<=48 and '<' not in tile for tile in c['tiles']))
                self.assertLess(len(c['prompt'].split()),15)

class DustTests(unittest.IsolatedAsyncioTestCase):
    async def test_filters_specialists_old_turns_and_uses_followup_endpoint(self):
        posts=[];cycle=0
        def handler(request):
            nonlocal cycle
            if request.method=='POST':
                posts.append(str(request.url));cycle+=1
                return httpx.Response(200,json={'conversation':{'sId':'conv'}})
            messages=[{'type':'agent_message','sId':'old','configuration':{'sId':'coordinator'},'status':'succeeded','content':'{"intent":"answer"}'}]
            if cycle>=1:messages += [ {'type':'agent_message','sId':'specialist','configuration':{'sId':'academic'},'status':'succeeded','content':'internal notes'},
                {'type':'agent_message','sId':f'turn{cycle}','configuration':{'sId':'coordinator'},'status':'succeeded','content':json.dumps({'intent':'yes','cycle':cycle})}]
            return httpx.Response(200,json={'conversation':{'content':[messages]}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            conversation=DustConversation({'dust_base_url':'https://dust.tt','workspace':'test'},'coordinator',http)
            first=await conversation.ask({});second=await conversation.ask({})
        self.assertEqual(first['cycle'],1);self.assertEqual(second['cycle'],2)
        self.assertTrue(posts[-1].endswith('/conv/messages'))
    async def test_http_401_sanitized(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(401,json={'secret':'not displayed'}))) as http:
            conversation=DustConversation({'dust_base_url':'https://dust.tt','workspace':'test'},'agent',http)
            with self.assertRaises(VoiceIssue) as caught:await conversation.ask({})
        self.assertEqual(caught.exception.code,'dust_access')
    def test_raw_notes_are_never_spoken(self):
        for value in ['internal notes','[]','{"spoken_text":""}','{"spoken_text":3}','{"spoken_text":"'+('x'*401)+'"}']:
            with self.assertRaises(VoiceIssue):speech_from_reply(value)

class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        import app
        cls.module=app;cls.tmp=tempfile.TemporaryDirectory()
        cls.patcher=patch.object(app,'Store',lambda:Store(Path(cls.tmp.name)/'test.sqlite3'));cls.patcher.start()
        cls.client=TestClient(app.app);cls.client.__enter__()
    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None,None,None);cls.patcher.stop();cls.tmp.cleanup()
    def test_preview_no_keys_and_private_cookie(self):
        with patch.object(self.module,'missing_settings',return_value=['keys']):
            response=self.client.get('/voice/config')
        self.assertFalse(response.json()['ready'])
        cookie=response.headers.get('set-cookie','')
        self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=strict',cookie)
    def test_svg_escapes_content(self):
        response=self.client.get('/voice/tile.svg',params={'text':'<script>&'})
        self.assertNotIn('<script>',response.text);self.assertIn('&lt;script&gt;',response.text)
        self.assertIn('sandbox',response.headers['content-security-policy'])
    def test_private_coach_requires_token(self):
        self.assertEqual(self.client.get('/coach/state').status_code,401)
        self.assertEqual(self.client.get('/coach/state',headers={'X-Coach-Token':self.module.COACH_TOKEN}).status_code,200)
    def test_cross_site_assessment_blocked(self):
        response=self.client.post('/coach/assess',headers={'X-Coach-Token':self.module.COACH_TOKEN,'origin':'https://evil.example'},
            json={'session_id':'a'*32,'attempt_id':'b'*32,'result':'reussite'})
        self.assertEqual(response.status_code,403)
    def test_bad_websocket_origin_rejected(self):
        from starlette.websockets import WebSocketDisconnect
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect('/voice/session',headers={'origin':'https://evil.example'}):pass
    def test_unconfigured_websocket_is_explicit(self):
        self.client.get('/voice/config')
        with patch.object(self.module,'missing_settings',return_value=['keys']):
            with self.client.websocket_connect('/voice/session',headers={'origin':'http://testserver'}) as ws:
                self.assertEqual(ws.receive_json(),{'type':'error','code':'setup'})

class VoiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_flush_includes_delayed_transcript_and_stops_sender(self):
        from voice_session import VoiceSession
        class STT:
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            async def send_audio(self,data):pass
            async def send_flush(self,flush_id):self.flushed=flush_id
            async def recv(self):return self.messages.pop(0)
        stt=STT();stt.messages=[{'type':'text','text':'ma'}, {'type':'step','vad':[{'horizon_s':3,'inactivity_prob':.9}]},
            {'type':'text','text':'rie'},{'type':'flushed','flush_id':1}]
        class Gradium:
            def stt_realtime(self,**kwargs):return stt
        session=VoiceSession.__new__(VoiceSession);session.audio=asyncio.Queue();session.gradium=Gradium()
        session.state=AsyncMock()
        with patch('voice_session.time',SimpleNamespace(monotonic=Mock(side_effect=[0,1,3,4]))):
            text=await session.listen()
        self.assertEqual(text,'ma rie');self.assertEqual(stt.flushed,1);self.assertFalse(session.listening)
    async def test_run_cancels_work_when_browser_stops(self):
        from voice_session import VoiceSession
        session=VoiceSession.__new__(VoiceSession);session.dust=type('Team',(),{'close':AsyncMock()})()
        session.receive_browser=AsyncMock(return_value=None)
        cancelled=asyncio.Event()
        async def conversation():
            try:await asyncio.Event().wait()
            finally:cancelled.set()
        session.converse=conversation
        await session.run()
        self.assertTrue(cancelled.is_set());session.dust.close.assert_awaited_once()


    async def test_reading_prompt_waits_for_visible_tiles(self):
        from voice_session import VoiceSession
        session=VoiceSession.__new__(VoiceSession)
        session.visual_ready=asyncio.Event();session.visual_id=None
        session.socket=SimpleNamespace(send_json=AsyncMock());session.speak=AsyncMock()
        task=asyncio.create_task(session.deliver({'spoken_text':'À vous.','visual':{'tiles':['ma']}}))
        await asyncio.sleep(0)
        self.assertFalse(task.done());session.speak.assert_not_awaited()
        self.assertEqual(session.socket.send_json.call_args.args[0]['type'],'visual')
        session.visual_ready.set();await task
        session.speak.assert_awaited_once_with('À vous.')
    async def test_synthesis_completion_waits_for_browser_playback(self):
        from voice_session import VoiceSession
        class TTS:
            ready={'sample_rate':48000}
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            async def send_text(self,text):self.text=text
            async def send_eos(self):pass
            async def __aiter__(self):
                yield {'type':'audio','audio':b'\x00\x00'*480}
                yield {'type':'end_of_stream'}
        tts=TTS();ended=asyncio.Event();session=VoiceSession.__new__(VoiceSession)
        async def send_json(value):
            if value['type']=='speech_end':ended.set()
        session.socket=SimpleNamespace(send_json=send_json,send_bytes=AsyncMock())
        session.gradium=SimpleNamespace(tts_realtime=lambda **kwargs:tts)
        session.voice_id='test-voice';session.speech_id=0;session.played=asyncio.Event()
        task=asyncio.create_task(session.speak('Bonjour.'))
        await asyncio.wait_for(ended.wait(),1)
        self.assertFalse(task.done());self.assertFalse(session.listening)
        session.played.set();await task
        self.assertEqual(tts.text,'Bonjour.')
        self.assertFalse(session.playback_pending)

class SettingsTests(unittest.TestCase):
    def test_blank_workspace_env_does_not_override_discovered_workspace(self):
        import settings
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'setup.json';path.write_text(json.dumps({'workspace':'discovered'}))
            with patch.object(settings,'SETUP_FILE',path),patch.dict('os.environ',{'DUST_WORKSPACE_ID':''}):
                self.assertEqual(settings.settings()['workspace'],'discovered')

if __name__=='__main__':unittest.main()
