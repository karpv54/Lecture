"""Local-only learner app and separate protected companion view."""
import html
import logging
import os
import re
import secrets
from contextlib import asynccontextmanager
os.environ.setdefault('GRADIO_ANALYTICS_ENABLED','False')
import gradio as gr
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from typing import Literal
from settings import APP_ROOT, PROJECT_ROOT, DATA_DIR, settings, missing_settings, VoiceIssue
from store import Store
from voice_session import VoiceSession

LOGGER=logging.getLogger('reading_tutor')
COACH_TOKEN=secrets.token_urlsafe(32)
ACTIVE={}
store=None

@asynccontextmanager
async def lifespan(app):
    global store
    store=Store()
    yield

server=FastAPI(docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
server.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','[::1]','testserver'])

@server.middleware('http')
async def private_headers(request,call_next):
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Permissions-Policy']='microphone=(self), camera=()'
    return response

@server.get('/voice/config')
async def voice_config(request: Request):
    result=JSONResponse({'ready':not missing_settings()})
    profile=request.cookies.get('lecture_profile','')
    if not re.fullmatch(r'[a-f0-9]{64}',profile):
        result.set_cookie('lecture_profile',secrets.token_hex(32),httponly=True,samesite='strict',
                          secure=request.url.scheme=='https',max_age=60*60*24*365)
    return result

@server.get('/voice/capture.js')
async def capture_worklet():
    return FileResponse(APP_ROOT/'web/capture.js',media_type='text/javascript')

@server.get('/voice/tile.svg')
async def tile(text: str=''):
    if not text or len(text)>48 or any(ord(c)<32 for c in text):
        raise HTTPException(400,'Invalid tile')
    width=max(130,min(1000,len(text)*84+72))
    escaped=html.escape(text,quote=True)
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="190" viewBox="0 0 {width} 190"><rect x="2" y="2" width="{width-4}" height="186" rx="24" fill="#fffdf6" stroke="#d5ddcc" stroke-width="2"/><text x="50%" y="124" text-anchor="middle" font-family="Arial, sans-serif" font-size="112" fill="#223e36">{escaped}</text></svg>'
    return Response(svg,media_type='image/svg+xml',headers={'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; sandbox"})

def coach_auth(request):
    if not secrets.compare_digest(request.headers.get('X-Coach-Token',''),COACH_TOKEN):
        raise HTTPException(401,'Companion access required')
    if request.method!='GET' and request.headers.get('origin') not in {str(request.base_url).rstrip('/')}:
        raise HTTPException(403,'Same-origin request required')

@server.get('/accompagnant')
async def coach_page():
    return FileResponse(APP_ROOT/'web/coach.html',media_type='text/html')

@server.get('/coach/state')
async def coach_state(request: Request):
    coach_auth(request)
    return {'sessions':[{'id':s.id,**s.lesson.coach_snapshot()} for s in ACTIVE.values()]}

class Assessment(BaseModel):
    session_id: str=Field(min_length=32,max_length=32,pattern=r'^[a-f0-9]+$')
    attempt_id: str=Field(min_length=32,max_length=32,pattern=r'^[a-f0-9]+$')
    result: Literal['reussite','echec','non_evaluable']

@server.post('/coach/assess')
async def assess(body: Assessment,request: Request):
    coach_auth(request)
    session=next((s for s in ACTIVE.values() if s.id==body.session_id),None)
    if not session or session.lesson.attempt!=body.attempt_id or not session.lesson.coach_snapshot()['can_assess']:
        raise HTTPException(409,'This attempt is no longer awaiting observation')
    if body.attempt_id in session.coach_pending:
        raise HTTPException(409,'Assessment already queued')
    if session.coach.full():
        raise HTTPException(429,'Please wait')
    session.coach_pending.add(body.attempt_id)
    session.coach.put_nowait(body.model_dump())
    return {'queued':True}

@server.websocket('/voice/session')
async def voice_socket(socket: WebSocket):
    host=socket.headers.get('host','')
    profile=socket.cookies.get('lecture_profile','')
    if socket.headers.get('origin') not in {f'http://{host}',f'https://{host}'} or not re.fullmatch(r'[a-f0-9]{64}',profile):
        await socket.close(code=1008)
        return
    await socket.accept()
    session=None
    try:
        if missing_settings():
            raise VoiceIssue('setup')
        if ACTIVE:
            raise VoiceIssue('busy')
        session=VoiceSession(socket,settings(),profile,store)
        ACTIVE[profile]=session
        await session.run()
    except WebSocketDisconnect:
        pass
    except VoiceIssue as error:
        await report_error(socket,error.code)
    except TimeoutError:
        await report_error(socket,'timeout')
    except Exception as error:
        LOGGER.warning('Voice connection failed (%s)',type(error).__name__)
        status=getattr(error,'status',None) or getattr(getattr(error,'response',None),'status_code',None)
        await report_error(socket,'gradium_access' if status in {401,403} else 'provider_limit' if status==429 else 'connection')
    finally:
        if session and ACTIVE.get(profile) is session:
            ACTIVE.pop(profile,None)
        try:
            await socket.close()
        except (RuntimeError,WebSocketDisconnect):
            pass

async def report_error(socket,code):
    LOGGER.warning('Voice session ended: %s',code)
    try:
        await socket.send_json({'type':'error','code':code})
    except (RuntimeError,WebSocketDisconnect):
        pass

with gr.Blocks(title='Lecture — On apprend ensemble',analytics_enabled=False) as interface:
    gr.HTML((APP_ROOT/'web/voice.html').read_text(encoding='utf-8'),
            css_template=(APP_ROOT/'web/voice.css').read_text(encoding='utf-8'),
            js_on_load=(APP_ROOT/'web/voice.js').read_text(encoding='utf-8'),apply_default_css=False)

app=gr.mount_gradio_app(server,interface,path='/',footer_links=[],
    css='body,.gradio-container{background:#f6f4ed!important}.gradio-container{max-width:none!important;padding:0!important}main,.main,.contain{padding:0!important}footer{display:none!important}',
    blocked_paths=[str(PROJECT_ROOT),str(DATA_DIR)])

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(levelname)s: %(message)s')
    port=int(os.getenv('GRADIO_SERVER_PORT','7865'))
    print(f'Learner: http://127.0.0.1:{port}/',flush=True)
    print(f'Companion (private link): http://127.0.0.1:{port}/accompagnant#{COACH_TOKEN}',flush=True)
    if missing_settings():
        print('Preview only. Complete .env, then run setup_providers.py --provision. No provider calls run in preview.',flush=True)
    uvicorn.run(app,host='127.0.0.1',port=port,access_log=False,ws_max_size=8192)
