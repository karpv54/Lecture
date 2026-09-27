"""Gradium microphone -> Dust team -> controlled lesson -> Gradium playback."""
import asyncio
import json
import re
import time
import uuid
import gradium
from fastapi import WebSocketDisconnect
from dust_client import DustTeam
from lesson import Lesson
from settings import VoiceIssue

class VoiceSession:
    def __init__(self, socket, cfg, profile, store):
        self.id=uuid.uuid4().hex
        self.socket=socket
        self.gradium=gradium.client.GradiumClient(api_key=cfg['gradium_key'],base_url=cfg['gradium_base_url'])
        self.voice_id=cfg['voice_id']
        self.dust=DustTeam(cfg)
        self.lesson=Lesson(profile,store,self.dust)
        self.audio=asyncio.Queue(maxsize=50)
        self.coach=asyncio.Queue(maxsize=4)
        self.listening=False
        self.played=asyncio.Event()
        self.visual_ready=asyncio.Event()
        self.visual_id=None
        self.speech_id=0
        self.playback_pending=False
        self.coach_pending=set()

    async def run(self):
        reader=asyncio.create_task(self.receive_browser())
        conversation=asyncio.create_task(self.converse())
        try:
            done,_=await asyncio.wait([reader,conversation],timeout=900,return_when=asyncio.FIRST_COMPLETED)
            if not done:
                raise VoiceIssue('session_end')
            for task in done:
                task.result()
        finally:
            self.listening=False
            for task in (reader,conversation):
                task.cancel()
            await asyncio.gather(reader,conversation,return_exceptions=True)
            await self.dust.close()

    async def state(self,state):
        await self.socket.send_json({'type':'state','state':state})

    async def receive_browser(self):
        while True:
            message=await self.socket.receive()
            if message['type']=='websocket.disconnect':
                raise WebSocketDisconnect()
            data=message.get('bytes')
            if data is not None:
                if len(data)!=3840:
                    raise VoiceIssue('audio')
                if self.listening:
                    try:
                        self.audio.put_nowait(data)
                    except asyncio.QueueFull:
                        raise VoiceIssue('connection') from None
            elif message.get('text'):
                if len(message['text'])>512:
                    raise VoiceIssue('audio')
                try:
                    command=json.loads(message['text'])
                except ValueError:
                    raise VoiceIssue('audio') from None
                if not isinstance(command,dict):
                    raise VoiceIssue('audio')
                if command.get('type')=='stop':
                    return
                if command.get('type')=='ping':
                    await self.socket.send_json({'type':'pong'})
                if command.get('type')=='playback_done' and command.get('id')==self.speech_id and self.playback_pending:
                    self.played.set()
                if command.get('type')=='visual_ready' and command.get('id')==self.visual_id:
                    self.visual_ready.set()
                if command.get('type')=='playback_failed':
                    raise VoiceIssue('audio')

    async def deliver(self,reply):
        if reply.get('visual') is not None:
            self.visual_id=uuid.uuid4().hex
            self.visual_ready.clear()
            await self.socket.send_json({'type':'visual','id':self.visual_id,**reply['visual']})
            if reply['visual'].get('tiles'):
                await asyncio.wait_for(self.visual_ready.wait(),timeout=10)
        await self.speak(reply['spoken_text'])
        if reply.get('finished'):
            await self.socket.send_json({'type':'finished'})
            return True
        return False

    async def wait_turn(self):
        if not self.coach.empty():
            return 'assessment',self.coach.get_nowait()
        listening=asyncio.create_task(self.listen())
        assessment=asyncio.create_task(self.coach.get())
        try:
            done,_=await asyncio.wait([listening,assessment],return_when=asyncio.FIRST_COMPLETED)
            # Prefer an observed result for the current attempt over a concurrent voice turn.
            if assessment in done:
                return 'assessment',assessment.result()
            return 'speech',listening.result()
        finally:
            for task in (listening,assessment):
                task.cancel()
            await asyncio.gather(listening,assessment,return_exceptions=True)

    async def converse(self):
        await self.deliver(self.lesson.greeting())
        silent_turns=0
        while True:
            async with asyncio.timeout(150):
                kind,value=await self.wait_turn()
            await self.state('thinking')
            if kind=='assessment':
                self.coach_pending.discard(value['attempt_id'])
                try:
                    async with asyncio.timeout(140):
                        reply=await self.lesson.assess(value['attempt_id'],value['result'])
                except ValueError:
                    continue  # Attempt changed between request and application.
            else:
                if not value:
                    silent_turns+=1
                    if silent_turns>=2:
                        await self.deliver({'spoken_text':'On fait une pause. Vous pourrez reprendre avec le micro.','finished':True})
                        return
                    await self.speak('Prenez votre temps. Vous pouvez demander de l’aide, ou faire une pause.')
                    continue
                silent_turns=0
                stop_words=re.sub(r'[^\w\s]','',value.casefold()).strip()
                if stop_words in {'stop','arrête','arrêtez','on arrête','pause','on fait une pause'}:
                    await self.deliver({'spoken_text':"D’accord. On fait une pause. À bientôt.",'finished':True})
                    return
                async with asyncio.timeout(240):
                    reply=await self.lesson.turn(value)
            if await self.deliver(reply):
                return

    async def listen(self):
        while not self.audio.empty():
            self.audio.get_nowait()
        async with self.gradium.stt_realtime(model_name='default',input_format='pcm',
                json_config={'language':'fr','delay_in_frames':16},wait_for_ready_on_start=True) as stt:
            self.listening=True
            await self.state('listening')
            async def forward_audio():
                while True:
                    await stt.send_audio(await self.audio.get())
            sender=asyncio.create_task(forward_audio())
            parts=[]
            start=last_text=time.monotonic()
            flushing=False
            try:
                while True:
                    if sender.done() and not flushing:
                        sender.result()
                    message=await asyncio.wait_for(stt.recv(),timeout=12)
                    if message is None:
                        raise VoiceIssue('connection')
                    kind=message.get('type')
                    if kind=='error':
                        raise VoiceIssue('gradium')
                    if kind=='text' and message.get('text','').strip():
                        parts.append(message['text'].strip())
                        last_text=time.monotonic()
                        if sum(map(len,parts))>4000:
                            raise VoiceIssue('audio')
                    elif kind=='step' and not flushing:
                        horizons=message.get('vad',[])
                        quiet=any(v.get('horizon_s',0)>=3 and v.get('inactivity_prob',0)>.7 for v in horizons)
                        # Compatibility with SDK payloads whose VAD array omits horizon_s.
                        if len(horizons)>=4 and 'horizon_s' not in horizons[3]:
                            quiet=horizons[3].get('inactivity_prob',0)>.7
                        if (parts and quiet and time.monotonic()-last_text>.8) or time.monotonic()-start>55:
                            self.listening=False
                            await self.state('thinking')
                            sender.cancel()
                            await asyncio.gather(sender,return_exceptions=True)
                            await stt.send_flush(flush_id=1)
                            flushing=True
                    elif kind=='flushed' and flushing and message.get('flush_id')==1:
                        return ' '.join(parts).strip()
                    elif kind=='end_of_stream':
                        raise VoiceIssue('connection')
            finally:
                self.listening=False
                sender.cancel()
                await asyncio.gather(sender,return_exceptions=True)

    async def speak(self,text):
        if not isinstance(text,str) or not text.strip() or len(text)>400:
            raise VoiceIssue('reply_format')
        self.listening=False
        self.speech_id+=1
        self.played.clear()
        self.playback_pending=False
        await self.state('thinking')
        audio_bytes=0
        sample_rate=48000
        async with asyncio.timeout(90):
            async with self.gradium.tts_realtime(model_name='default',voice_id=self.voice_id,output_format='pcm',
                                                wait_for_ready_on_start=True) as tts:
                sample_rate=(tts.ready or {}).get('sample_rate') or 48000
                if not isinstance(sample_rate,int) or not 8000<=sample_rate<=96000:
                    raise VoiceIssue('audio')
                await self.socket.send_json({'type':'speech_start','id':self.speech_id,'sample_rate':sample_rate})
                await tts.send_text(text)
                await tts.send_eos()
                async for message in tts:
                    if message.get('type')=='error':
                        raise VoiceIssue('gradium')
                    if message.get('type')=='audio':
                        audio=message['audio']
                        if len(audio)%2:
                            raise VoiceIssue('audio')
                        audio_bytes+=len(audio)
                        if audio_bytes>sample_rate*2*90:
                            raise VoiceIssue('audio')
                        await self.socket.send_bytes(audio)
                    elif message.get('type')=='end_of_stream':
                        break
        if not audio_bytes:
            raise VoiceIssue('audio')
        self.playback_pending=True
        await self.socket.send_json({'type':'speech_end','id':self.speech_id})
        await asyncio.wait_for(self.played.wait(),timeout=audio_bytes/(2*sample_rate)+15)
        self.playback_pending=False
