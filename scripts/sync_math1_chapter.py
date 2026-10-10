"""Execute the page's reviewed objective-answer queue via real MCP stdio.

Open proofs are persisted and listed for semantic review, never automatically scored.
Call receipts and a durable ledger make ordinary retries safe; recovery reads Runtime's
request-id event log when a call succeeded before the ledger was written.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import re
import sqlite3
import sys
from contextlib import closing
from fractions import Fraction
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def number(s):
    s=re.sub(r'\s+','',s.strip().replace('−','-').replace('＋','+'))
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:/[+-]?(?:\d+(?:\.\d*)?|\.\d+))?',s): raise ValueError('Only finite decimal or rational answers supported')
    parts=s.split('/')
    return Fraction(parts[0])/(Fraction(parts[1]) if len(parts)>1 else 1)

def objective_matches(question, raw):
    if question['kind']=='choice':
        return raw==question['answer']
    if question['kind']!='numeric':
        raise ValueError('Only objective questions can be rule-scored')
    try:
        return number(raw)==number(question['answer'])
    except (ValueError, ZeroDivisionError):
        # An invalid learner expression is a wrong answer, not a transport failure.
        return False

def atomic_json(path,data):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(path)

async def sync(record,db,session_id,ledger_path,repo,questions,node_ids):
    if record.get('learner',{}).get('session_id')!=session_id:raise ValueError('Session mismatch')
    pending=record.get('outbox',[])
    if len({c['call_id'] for c in pending})!=len(pending):raise ValueError('Duplicate call identifiers')
    bank={q['id']:q for q in questions}
    ledger=json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else {}
    calls=[]
    semantic=[]
    env={**os.environ,'LEAP__DATABASE_PATH':str(db),'PYTHONPATH':str(repo/'src'),'LEAP_LOG_LEVEL':'WARNING'}
    async with stdio_client(StdioServerParameters(command=sys.executable,args=['-m','leap.server'],env=env)) as (r,w):
      async with ClientSession(r,w) as client:
        await client.initialize()
        async def call(tool,args):
            res=await client.call_tool(tool,args)
            data=res.structured_content or json.loads(next(c.text for c in res.content if c.type=='text'))
            if res.is_error or not data.get('ok'): raise RuntimeError((tool,data))
            return data
        await call('get_session_info',{'session_id':session_id})
        async def recover(c,args):
            if not db.exists():return None
            with closing(sqlite3.connect(db)) as con:
                con.row_factory=sqlite3.Row
                ev=con.execute('SELECT event_type,payload FROM event_log WHERE request_id=? AND session_id=? ORDER BY rowid DESC LIMIT 1',(c['call_id'],session_id)).fetchone()
                if not ev:return None
                payload=json.loads(ev['payload'])
                if c['tool']=='submit_attempt' and ev['event_type']=='attempt_submitted':
                    row=con.execute('SELECT * FROM learning_attempts WHERE attempt_id=?',(payload['attempt_id'],)).fetchone()
                    if row['answer']!=args['answer'] or row['item_id']!=args['item_id']:raise ValueError('Recovery payload mismatch')
                    return {'ok':True,'attempt_id':row['attempt_id'],'session_id':session_id,'recovered':True}
                if c['tool']=='record_reflection' and ev['event_type']=='reflection_recorded':
                    row=con.execute('SELECT content FROM artifacts WHERE artifact_id=?',(payload['artifact_id'],)).fetchone()
                    if row['content']!=args['reflection']:raise ValueError('Reflection recovery mismatch')
                    return {'ok':True,'artifact_id':payload['artifact_id'],'recovered':True}
                if c['tool']=='commit_assessment' and ev['event_type']=='assessment_committed':
                    row=con.execute('SELECT * FROM assessment_results WHERE result_id=?',(payload['result_id'],)).fetchone()
                    if row['raw_answer']!=args['raw_answer'] or row['attempt_id']!=args['attempt_id']:raise ValueError('Assessment recovery mismatch')
                    return {'ok':True,'attempt_id':row['attempt_id'],'result_id':row['result_id'],'overall_score':row['overall_score'],'stage_after':payload['stage_after'],'recovered':True}
            raise RuntimeError('Request-id event exists but cannot safely recover; inspect Runtime before retry')
        for c in pending:
            tool=c['tool'];args=dict(c['args']);cid=c['call_id']
            if tool not in ('submit_attempt','commit_assessment','record_reflection'):raise ValueError('Unsupported delivery call: '+tool)
            for key,value in args.items():
                match=re.fullmatch(r'\{\{(.+)\.(\w+)\}\}',value) if isinstance(value,str) else None
                if match:
                    previous=ledger.get(match[1])
                    if not previous or previous['result'].get('ok') is not True:raise ValueError('Unresolved previous call')
                    args[key]=previous['result'][match[2]]
            if args.get('request_id')!=cid:raise ValueError('Request identifier mismatch')
            if tool=='submit_attempt':
                q=bank.get(args.get('item_id'))
                if not q or args.get('node_id')!=node_ids[q['unit']] or args.get('session_id')!=session_id:raise ValueError('Item registration mismatch')
                if not isinstance(args.get('answer'),str) or not args['answer'].strip():raise ValueError('Empty answer')
            elif tool=='record_reflection':
                if args.get('session_id')!=session_id or args.get('node_id') not in node_ids or not isinstance(args.get('reflection'),str):raise ValueError('Reflection mismatch')
            else:
                ref=re.fullmatch(r'\{\{(.+)\.attempt_id\}\}',c['args']['attempt_id'])
                previous=ledger[ref[1]] if ref else None
                if not previous or previous['tool']!='submit_attempt':raise ValueError('Commit must reference a submitted attempt')
                q=bank[previous['args']['item_id']]
                raw=previous['args']['answer']
                if q['kind']=='proof':raise ValueError('Proof needs host semantic review; no rule commit')
                if args.get('raw_answer')!=raw:raise ValueError('Raw answer differs from attempt')
                correct=objective_matches(q,raw)
                expected={'attempt_id':args['attempt_id'],'raw_answer':raw,'assessor_type':'rule','correctness':int(correct),'hint_dependency':previous['args']['hint_level']/4,'request_id':cid}
                if args!=expected:raise ValueError('Assessment exceeds exact-answer scope or differs from independent host check')
            if cid in ledger:
                entry=ledger[cid]
                if entry['tool']!=tool or entry['args']!=args:raise ValueError('Call identifier reused with different arguments')
            else:
                result=await recover(c,args) or await call(tool,args)
                entry={'call_id':cid,'tool':tool,'args':args,'result':result}
                ledger[cid]=entry;atomic_json(ledger_path,ledger)
            calls.append(entry)
            if tool=='submit_attempt' and q['kind']=='proof':semantic.append({'item_id':q['id'],'attempt_id':entry['result']['attempt_id'],'source_call_id':cid,'raw_answer':args['answer'],'hint_level':args['hint_level'],'question':q['question'],'reference_solution':q['solution'],'status':'awaiting_host_semantic_review'})
        contexts=[await call('get_teaching_context',{'session_id':session_id,'node_id':nid}) for nid in node_ids]
    return {'session_id':session_id,'calls':calls,'contexts':contexts,'pending_semantic_reviews':semantic,'connection':'MCP stdio completed; receipt is a snapshot, not a persistent live connection'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('record',type=Path)
    p.add_argument('--delivery',type=Path,required=True,help='Folder containing runtime-manifest.json and question-bank.json')
    p.add_argument('--receipt',type=Path,required=True)
    args=p.parse_args()
    root=args.delivery.resolve()
    manifest=json.loads((root/'runtime-manifest.json').read_text(encoding='utf-8'))
    questions=json.loads((root/'question-bank.json').read_text(encoding='utf-8'))
    record=json.loads(args.record.read_text(encoding='utf-8'))
    node_ids=[n['node_id'] for n in manifest['nodes']]
    receipt=asyncio.run(sync(record,root/'learner-runtime.sqlite',manifest['session_id'],root/'host-sync-ledger.json',Path(manifest['repository']),questions,node_ids))
    atomic_json(args.receipt,receipt)
    print(json.dumps({'synced_calls':len(receipt['calls']),'proofs_awaiting_review':len(receipt['pending_semantic_reviews']),'receipt':str(args.receipt)},ensure_ascii=False))

if __name__=='__main__': main()
