"""Finite, reviewed-in-source content. Models select IDs, never invent spelling."""
import json
import unicodedata
from settings import PROJECT_ROOT

DATA = json.loads((PROJECT_ROOT / 'assets/phonetics.json').read_text(encoding='utf-8'))
ANCHORS = {a['id']: a for a in DATA['anchors']}
STAGES = ['ancrage','decoupage','lettres_sons','graphies_composees','assemblage','transfert','mots_utiles']

def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c)).strip()

def find_anchor(text):
    return next((a for a in ANCHORS.values() if normalize(a['word']) == normalize(text)), None)

def make_card(key, stage, tiles, model, group, word='', emoji='', requires=None):
    return {'id':key,'etape':stage,'tiles':tiles,'model':model,'group':group,
            'word':word,'emoji':emoji,'requires':requires or [],
            'prompt':'À vous de lire. Prenez votre temps.'}

def cards_for(anchor_id):
    a = ANCHORS[anchor_id]
    cards = [make_card(f'{anchor_id}:first','ancrage',[a['word']],
                       f"Écoutez : {a['word']}. {a['note']}".strip(),0,a['word'],a['emoji'])]
    cards.append(make_card(f'{anchor_id}:parts','decoupage',a['syllables'],
                           'Écoutez les parties : ' + ', '.join(a['syllables']) + '.',1))
    for unit in a['patterns']:
        p = DATA['patterns'][unit]
        cards.append(make_card('pattern:'+unit,'graphies_composees' if len(unit)>1 else 'lettres_sons',
                               [p['display']],p['model'],2 if len(unit)==1 else 3))
    if 'ou' not in a['patterns']:
        p=DATA['patterns']['ou']
        cards.append(make_card('pattern:ou','graphies_composees',[p['display']],p['model'],3))
    for part in a['syllables']:
        cards.append(make_card(f'{anchor_id}:syllable:{part}','assemblage',[part],
                               f'Écoutez : {part}.',4,requires=['pattern:'+p for p in a['patterns']]))
    cards.append(make_card(f'{anchor_id}:whole','assemblage',[a['word']],
                           f"Écoutez : {a['word']}. {a['note']}".strip(),5,a['word'],a['emoji'],
                           [f'{anchor_id}:syllable:{part}' for part in a['syllables']]))
    # Transfer varies the spelling, teaches at most one unfamiliar pattern first.
    transfers=[w for w in ANCHORS.values() if w['kind']=='mot_familier' and w['id']!=anchor_id
               and len(set(w['patterns'])-set(a['patterns'])) <= 1
               and set(w['patterns']) & set(a['patterns'])]
    seen=set(a['patterns']) | {'ou'}
    for index,w in enumerate(transfers[:3]):
        group=6+index*2
        for unit in w['patterns']:
            if unit not in seen:
                p=DATA['patterns'][unit]
                cards.append(make_card('pattern:'+unit,'graphies_composees' if len(unit)>1 else 'lettres_sons',
                                       [p['display']],p['model'],group))
                seen.add(unit)
        cards.append(make_card('transfer:'+w['id'],'transfert',w['syllables'],
                               'Écoutez : ' + ', '.join(w['syllables']) + f". {w['note']}",group+1))
        cards.append(make_card('word:'+w['id'],'mots_utiles',[w['word']],
                               f"Écoutez : {w['word']}. {w['note']}".strip(),group+1.5,w['word'],w['emoji']))
    return cards

def method_catalogue(cards, anchor):
    result=[]
    for card in cards:
        for intention in ('apprentissage','revision','verification'):
            result.append({'id':card['id']+':'+intention,'etape':card['etape'],'intention':intention,
                           'cible_id':card['id'],'mot_source':anchor['word'] if card['etape']=='decoupage' else '',
                           'prerequis':card['requires'],'validee':True,
                           'objectif':'Décodage avec preuve indépendante si évaluation.',
                           'consigne_orale':card['prompt'],'texte_affiche':'-'.join(card['tiles']),
                           'repere_visuel':card['emoji'],'lecture_independante':True})
    return result
