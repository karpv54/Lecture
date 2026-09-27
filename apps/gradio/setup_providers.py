"""Owner-run provider configuration. Listing/importing only; no inference calls.

--export is completely offline. --check only reads provider metadata.
--provision creates missing application agents; --update-managed refreshes only
agents carrying this application's marker. Existing original agents are untouched.
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from pathlib import Path
import httpx
from settings import APP_ROOT, PROJECT_ROOT, SETUP_FILE, settings, VoiceIssue

MARKER='reading-tutor-managed-v2'
CATALOG=json.loads((PROJECT_ROOT/'agents/catalog.json').read_text(encoding='utf-8'))['agents']
GASPARD='iEu63s1rhn_kegTr'  # Official French masculine flagship; confirmed with metadata before saving.

def bundle(agent, model=None, editor_email=None):
    instructions=(PROJECT_ROOT/'agents'/agent['instructions']).read_text(encoding='utf-8')+'\n\n'+(PROJECT_ROOT/'agents'/agent['app_contract']).read_text(encoding='utf-8')
    return {'agent':{'handle':agent['app_name'],'description':'French adult reading tutor · '+MARKER,
                     'scope':'hidden',
                     'avatar_url':'https://dust.tt/static/systemavatar/dust_avatar_full.png',
                     'max_steps_per_run':4,'visualization_enabled':False},
            'instructions':instructions,'generation_settings':model or {},'tags':[],
            'editors':[editor_email] if editor_email else [], 'toolset':[]}

def contract_hash():
    content=json.dumps([bundle(a) for a in CATALOG],sort_keys=True,ensure_ascii=False).encode()
    return hashlib.sha256(content).hexdigest()

async def checked(http, method, url, **kwargs):
    response=await http.request(method,url,**kwargs)
    if response.status_code>=400:
        # Never print the URL, workspace, key, headers or provider error body.
        host = httpx.URL(url).host
        if host in {'dust.tt', 'eu.dust.tt', 'us.dust.tt'}:
            provider, key_name = 'Dust', 'DUST_API_KEY'
            location = 'DUST_BASE_URL must match the workspace website; DUST_WORKSPACE_ID must belong to the same workspace as the key.'
        elif host in {'api.gradium.ai', 'eu.api.gradium.ai', 'us.api.gradium.ai'}:
            provider, key_name = 'Gradium', 'GRADIUM_API_KEY'
            location = 'Check GRADIUM_BASE_URL and the organization that issued the key.'
        else:
            provider, key_name, location = 'Provider', 'API key', 'Check the configured provider address.'
        oauth_only = False
        if provider == 'Dust' and response.status_code == 401:
            try:
                error = response.json().get('error', {})
                oauth_only = isinstance(error, dict) and error.get('message') == 'The user must be authenticated with oAuth to retrieve list agents.'
            except (ValueError, AttributeError):
                pass
        if oauth_only:
            detail = 'This agent-list view requires OAuth user sign-in. Setup must use view=all_unrestricted with a workspace admin API key; this response does not mean your key is invalid.'
        elif response.status_code == 401:
            detail = f'Authentication was rejected. Check {key_name} in apps/gradio/.env: use the full active secret key without a Bearer prefix. {location}'
        elif response.status_code == 403:
            detail = f'Access was denied. Check the permissions granted to {key_name}. {location}'
        elif response.status_code == 400:
            detail = 'The provider rejected the requested configuration. Check the agent configuration fields; this response does not by itself mean the API key or region is wrong.'
        elif response.status_code == 429:
            detail = 'A provider rate or usage limit was reached. Check the account limits before retrying.'
        else:
            detail = location
        raise RuntimeError(f'{provider} configuration request ({method}) returned HTTP {response.status_code}. {detail}')
    return response.json()

async def configure(args):
    cfg=settings()
    if not cfg['dust_key'] or not cfg['gradium_key']:
        raise RuntimeError('Add DUST_API_KEY and GRADIUM_API_KEY to apps/gradio/.env first. Never put them in chat or GitHub.')
    async with httpx.AsyncClient(timeout=30,headers={'Authorization':'Bearer '+cfg['dust_key']}) as dust:
        workspace=cfg['workspace']
        if not workspace:
            response=await dust.get(cfg['dust_base_url']+'/api/user')
            if response.status_code==200:
                choices=response.json().get('user',{}).get('workspaces',[])
                if len(choices)==1:
                    workspace=choices[0].get('sId','')
            if not workspace:
                raise RuntimeError('This key cannot identify a unique workspace. Set DUST_WORKSPACE_ID from your Dust workspace URL (/w/ID/). Workspace API keys commonly require this one non-secret setting.')
        if not re.fullmatch(r'[A-Za-z0-9_-]+',workspace):
            raise RuntimeError('Invalid workspace ID; use only the ID, not the entire URL.')
        base=f"{cfg['dust_base_url']}/api/v1/w/{workspace}/assistant/agent_configurations"
        # list requires OAuth; all hides private agents. The admin API view includes managed hidden agents.
        listing=await checked(dust,'GET',base,params={'view':'all_unrestricted'})
        agents=listing.get('agentConfigurations',[])
        if not isinstance(agents,list):
            raise RuntimeError('Unexpected Dust list response; no configuration was saved.')
        editor_email=os.getenv('DUST_EDITOR_EMAIL','').strip()
        existing_names={agent.get('name') for agent in agents}
        if args.provision and any(entry['app_name'] not in existing_names for entry in CATALOG):
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',editor_email):
                raise RuntimeError('Dust authentication succeeded. Creating agents with a workspace API key also requires DUST_EDITOR_EMAIL in apps/gradio/.env. Use the email of your existing Dust workspace account; no new account or key is needed.')
        model={}
        provider=os.getenv('DUST_MODEL_PROVIDER','').strip()
        model_id=os.getenv('DUST_MODEL_ID','').strip()
        if bool(provider)!=bool(model_id):
            raise RuntimeError('Set both DUST_MODEL_PROVIDER and DUST_MODEL_ID, or leave both empty.')
        if provider:
            model={'provider_id':provider,'model_id':model_id,'temperature':0.2,
                   'reasoning_effort':os.getenv('DUST_REASONING_EFFORT','none')}
        else:
            for agent in sorted(agents,key=lambda a:(a.get('sId')!='dust',a.get('name',''))):
                m=agent.get('model') or {}
                if m.get('providerId') and m.get('modelId'):
                    model={'provider_id':m['providerId'],'model_id':m['modelId'],
                           'temperature':m.get('temperature',0.2),'reasoning_effort':m.get('reasoningEffort') or 'none'}
                    break
        identifiers={}
        for entry in CATALOG:
            matches=[a for a in agents if a.get('name')==entry['app_name']]
            if len(matches)>1:
                raise RuntimeError(f"Several agents are named {entry['app_name']}; resolve the duplicate in Dust first.")
            if matches:
                current=await checked(dust,'GET',base+'/'+matches[0]['sId'])
                current=current.get('agentConfiguration',{})
                if MARKER not in (current.get('instructions') or ''):
                    raise RuntimeError(f"{entry['app_name']} already exists but is not managed by this app. It was not changed.")
                expected=bundle(entry,model)
                if current.get('instructions')!=expected['instructions']:
                    if not args.update_managed:
                        raise RuntimeError(f"{entry['app_name']} needs the current contract. Run setup_providers.py --provision --update-managed to refresh only managed app agents.")
                    payload={k:v for k,v in expected.items() if k!='editors'}
                    updated=await checked(dust,'PATCH',base+'/'+current['sId'],json=payload)
                    if updated.get('skippedActions'):
                        raise RuntimeError('Dust skipped configuration actions. Review the app agents before continuing.')
                identifiers[entry['id']]=current['sId']
                print(f"Verified {entry['app_name']}")
            else:
                if not args.provision:
                    raise RuntimeError(f"Missing {entry['app_name']}. Run setup_providers.py --provision to create the application agents.")
                if not model:
                    raise RuntimeError('No usable model was discoverable. Set DUST_MODEL_PROVIDER and DUST_MODEL_ID to a model enabled in your workspace.')
                created=await checked(dust,'POST',base+'/import',json=bundle(entry,model,editor_email=editor_email))
                if created.get('skippedActions') or not created.get('agentConfiguration',{}).get('sId'):
                    raise RuntimeError('Dust did not confirm a complete agent import; inspect workspace agents before retrying.')
                identifiers[entry['id']]=created['agentConfiguration']['sId']
                print(f"Created {entry['app_name']}")
        print('All five agents are connected through the backend dispatcher (no unconfigured Run agent tools).')
    async with httpx.AsyncClient(timeout=30,headers={'x-api-key':cfg['gradium_key']}) as gradium:
        voice=cfg['voice_id'] or GASPARD
        if not re.fullmatch(r'[A-Za-z0-9_-]+',voice):
            raise RuntimeError('Invalid voice ID.')
        data=await checked(gradium,'GET',cfg['gradium_base_url']+'voices/'+voice,params={'include_catalog':'true'})
        if data.get('uid')!=voice:
            raise RuntimeError('Gradium did not return the requested voice. Set GRADIUM_VOICE_ID to an available French male voice.')
        print('Verified voice metadata: '+str(data.get('name',voice))+'. Audition when ready; no synthesis was requested.')
    output={'contract_version':2,'contract_hash':contract_hash(),'workspace':workspace,'dust_base_url':cfg['dust_base_url'],
            'agents':identifiers,'voice_id':voice,'model':model}
    if args.check:
        print('Read-only metadata check passed. Live conversation and billing were not tested.')
        return
    SETUP_FILE.parent.mkdir(parents=True,exist_ok=True)
    temporary=SETUP_FILE.with_suffix('.tmp')
    temporary.write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    temporary.replace(SETUP_FILE)
    print('Configuration saved privately. Start app.py to open the tutor. No inference credits were intentionally used by setup.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export',type=Path,help='write import JSON bundles locally without network calls')
    parser.add_argument('--provision',action='store_true',help='create missing app agents')
    parser.add_argument('--update-managed',action='store_true',help='update app-marked agents to the current contract')
    parser.add_argument('--check',action='store_true',help='read-only check; no writes, creation or updates')
    args=parser.parse_args()
    if args.check and (args.provision or args.update_managed):
        parser.error('--check cannot be combined with remote writes')
    if args.export:
        args.export.mkdir(parents=True,exist_ok=True)
        for agent in CATALOG:
            (args.export/(agent['id']+'.json')).write_text(json.dumps(bundle(agent),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('Offline import bundles written. Choose a workspace-enabled model before manual import.')
        return
    try:
        asyncio.run(configure(args))
    except (RuntimeError,VoiceIssue,httpx.RequestError,KeyError,ValueError) as error:
        print(str(error) if isinstance(error,RuntimeError) else 'Configuration could not be verified. Check settings and connectivity.',file=sys.stderr)
        sys.exit(1)

if __name__=='__main__':
    main()
