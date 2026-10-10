"""Build and register a grounded 2028 Math I chapter through actual MCP stdio.

Lesson source and authored checks are repository files; learner runtime data and
test output are written only to the explicitly selected delivery directory.
"""
from __future__ import annotations
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import html as escape
import importlib.util
import json
import os
import shutil
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"curricula/math1-2028-ch01"
sys.path.insert(0,str(ROOT/"src"))
from leap.runtime.delivery import VisibleTeaching, normalize_text, validate_teaching_package
from leap.runtime.notes import obsidian_note
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

spec=importlib.util.spec_from_file_location("chapter_teaching",SOURCE/"teaching.py")
teaching=importlib.util.module_from_spec(spec);spec.loader.exec_module(teaching)
RESOURCES={"videos":[],"keywords":{
    "core":["考研数学一 函数 定义域 复合函数 极限 εδ 连续 入门"],
    "extension":["数列 单调有界 夹逼 等价无穷小 复合极限 条件 反例"],
    "advanced":["极限定义 量词 递推收敛 根式抵消 间断分类 存在唯一 证明"]}}
NODE_IDS=["math1.v3.ch01.functions","math1.v3.ch01.limits","math1.v3.ch01.equivalents","math1.v3.ch01.continuity"]


def source_reading():
    material=json.loads((SOURCE/"sources.json").read_text(encoding="utf-8"))
    # Human-readable excerpts retained with actual original snapshot hashes.
    return material["records"],material["verification"]


def copy_source_snapshots(snapshot_dir: Path, output: Path) -> None:
    """Preserve original fetched HTML and line-addressable text without fresh-reading claims."""
    import re
    records, _ = source_reading()
    checked = set()
    for record in records:
        match = re.search(r"(sources/[^:]+):L(\d+)–L(\d+).*SHA256 ([0-9a-f]{64})", record["locator"])
        if not match:
            raise ValueError("A source record needs a precise snapshot and line locator")
        text_path = Path(match[1]).name
        original = snapshot_dir / Path(text_path).with_suffix(".html")
        text = snapshot_dir / text_path
        if hashlib.sha256(original.read_bytes()).hexdigest() != match[4]:
            raise ValueError(f"Original HTML snapshot hash changed: {original.name}")
        excerpt = "\n".join(text.read_text(encoding="utf-8").splitlines()[int(match[2])-1:int(match[3])])
        if excerpt != record["excerpt"]:
            raise ValueError(f"Source excerpt does not match recorded lines: {text.name}")
        checked.update((original, text))
    # The page also cites three previously read prerequisite chapters. Preserve
    # their original snapshots from the acquisition index when it is available.
    acquisition_index = snapshot_dir / "index.json"
    if acquisition_index.exists():
        acquired = json.loads(acquisition_index.read_text(encoding="utf-8"))
        if isinstance(acquired, list):
            for source in acquired:
                key = source["key"]
                if not re.fullmatch(r"[a-z]+", key):
                    raise ValueError("Invalid source snapshot key")
                original = snapshot_dir / (key + ".html")
                text = snapshot_dir / (key + ".txt")
                if hashlib.sha256(original.read_bytes()).hexdigest() != source["sha256"]:
                    raise ValueError(f"Acquisition snapshot hash changed: {original.name}")
                if not text.is_file():
                    raise ValueError(f"Missing extracted source text: {text.name}")
                checked.update((original, text))
    target = output / "sources"
    target.mkdir(parents=True, exist_ok=True)
    for path in sorted(checked):
        shutil.copy2(path, target / path.name)
    provenance = {
        "hash_scope": "Source locator SHA256 is of the original fetched HTML; line ranges refer to its extracted text.",
        "records": records,
        "files": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(checked)},
        "fresh_fetch": False,
    }
    (target / "index.json").write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def support(point):
    labels={"prerequisites":"前置知识","principle":"为什么成立","worked_example":"完整例题与核对",
        "misconceptions":"常见错误与修复","boundaries":"边界与适用范围","comparison":"对比辨析","practice":"基础、变式与挑战","transfer":"独立迁移"}
    out=f'<details class="deep-point"><summary>{escape.escape(point["title"])} · 完整教学链</summary>'
    for key,label in labels.items():out+=f'<h4>{label}</h4><p>{escape.escape(point[key])}</p>'
    out+='<h4>一步一步做</h4><ol>'+''.join('<li>'+escape.escape(s)+'</li>' for s in point["steps"])+"</ol></details>"
    return out


def build_bodies(data):
    template=(SOURCE/"page.template.html").read_text(encoding="utf-8")
    template=template.replace("max-width:1320px","max-width:1800px").replace("grid-template-columns:230px minmax(0,1fr);gap:60px;padding:48px 32px 80px","grid-template-columns:280px minmax(0,1fr);gap:32px;padding:48px clamp(20px,2.5vw,48px) 80px")
    template=template.replace("</style>",".deep-point h4{margin:18px 0 6px}.deep-point p{color:var(--ink)}.walk-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.step-chain{background:var(--surface);padding:18px;border-radius:8px}#walk-point{max-width:100%;padding:8px}.step-chain svg{width:100%;height:auto}.resource-tiers{border:1px solid var(--line);padding:20px;border-radius:8px;margin-bottom:30px}.resource-tiers p{font-size:14px;margin:8px 0}.walk-step{font-size:16px;color:var(--ink)!important;min-height:100px}.deep-point{padding-block:16px}.deep-point summary{color:var(--accent)}@media(max-width:850px){.walk-grid{grid-template-columns:1fr}} </style>")
    resources='<section class="resource-tiers" aria-label="学习资源"><h2>学习资源 · 分层搜索</h2><p>没有逐段核验的视频，因此提供可直接搜索的主题词；完整知识源见 <a href="knowledge.md">Obsidian 学习与答案册</a>。</p>'
    for tier,label in [("core","核心"),("extension","拓展"),("advanced","进阶")]:resources+='<p><b>'+label+'</b>：'+escape.escape(RESOURCES["keywords"][tier][0])+'</p>'
    resources+='</section>'
    template=template.replace('<main>', '<main>'+resources,1)
    template=template.replace('<main class="', '<main class="',1)
    if resources not in template:template=template.replace('<div class="hero">',resources+'<div class="hero">',1)
    if resources not in template:
        import re
        template=re.sub(r'(<main[^>]*>)',lambda m:m.group(1)+resources,template,count=1)
    options=''.join(f'<option value="{i}">{p["title"]}</option>' for i,p in enumerate(teaching.POINTS))
    walker='''<section id="chapter-walkthrough" class="experiment"><div class="body"><h3>可控推导 · 先看条件，再走步骤</h3><p>每个主题可独立选择、逐步前进与回看；文字推导与图示共同说明操作原因。</p><label>主题 <select id="walk-point">'''+options+'''</select></label><div class="walk-grid"><div><p id="walk-prerequisite"></p><p id="walk-step" class="walk-step" aria-live="polite"></p><div class="actions"><button id="walk-prev" type="button" class="btn">上一步</button><button id="walk-next" type="button" class="btn primary">下一步</button><button id="walk-reset" type="button" class="btn">重置推导</button></div></div><div class="step-chain"><svg viewBox="0 0 620 210" role="img" aria-label="条件、合法操作和独立检验的推导链"><rect x="15" y="60" width="175" height="78" rx="8" fill="#dbeafe"/><rect x="225" y="60" width="175" height="78" rx="8" fill="#dcfce7"/><rect x="435" y="60" width="175" height="78" rx="8" fill="#fef3c7"/><path d="M190 98h35m175 0h35" stroke="#5b6470" stroke-width="3"/><text x="46" y="94" font-size="18">定义与前提</text><text x="250" y="94" font-size="18">合法变形</text><text x="462" y="94" font-size="18">回代与边界</text><text x="27" y="118" font-size="13">先确定输入范围</text><text x="244" y="118" font-size="13">每一步说明理由</text><text x="450" y="118" font-size="13">核对结论依赖条件</text><text x="80" y="178" font-size="16" id="walk-graph-label">第 1 步</text></svg><p id="walk-check"></p></div></div></div></section>'''
    template=template.replace('<section id="delta-experiment"',walker+'<section id="delta-experiment"',1)
    # New diagrams make the function and cancellation units as controllable as
    # the existing analytic epsilon-delta and continuity views.
    visual='''<section id="function-experiment" class="experiment"><div class="body"><h3>函数与反函数 · 一来一回检查分支</h3><p>x² 限于 x≥0 才能用 √y 作为反函数。拖动输入，观察原输入、输出与逆对应。</p><label>x = <output id="inverse-x-label">2</output><input id="inverse-x" type="range" min="0" max="4" value="2" step="0.25"></label></div><svg viewBox="0 0 640 180" role="img" aria-label="非负输入经过平方和平方根的逆映射"><g id="inverse-svg"></g></svg><p class="result-note" id="inverse-note"></p></section><section id="cancellation-experiment" class="experiment" hidden><div class="body"><h3>首项抵消 · 共轭保存遗漏的差</h3><p>x→+∞ 时，观察 x(√(x²+1)−x)；直接把根号替成 x 会错误地得0。计算采用等价的稳定恒等式。</p><label>x = <output id="cancel-x-label">10</output><input id="cancel-x" type="range" min="1" max="100" value="10" step="1"></label></div><svg viewBox="0 0 640 210" role="img" aria-label="乘共轭后三步保留微小差"><g id="cancel-svg"></g></svg><p class="result-note" id="cancel-note"></p></section>'''
    template=template.replace('<section id="continuity-experiment"',visual+'<section id="continuity-experiment"',1)
    template=template.replace("$('#continuity-experiment').hidden=i!==3;","$('#continuity-experiment').hidden=i!==3;$('#function-experiment').hidden=i!==0;$('#cancellation-experiment').hidden=i!==2;")
    template=template.replace("const storageKey='leap-ch01-v1-'", "const storageKey='leap-ch01-v3-'")
    template=template.replace("overall_score:0,evidence_stage:","overall_score:null,evidence_stage:")
    template=template.replace("S.ui_state.hint_dependency=st.hint/4", "S.ui_state.local_hint_dependency=st.hint/4;S.ui_state.hint_dependency=contexts[S.node.node_id]?.knowledge_state?.hint_dependency??null")
    template=template.replace("__DATA__",json.dumps(data,ensure_ascii=False).replace('</','<\\/'))
    for i,lesson in enumerate(data["lessons"]):
        template=template.replace(f"__LESSON_{i}__",lesson+'<h3>逐点深化：前置—原因—操作—检验</h3>'+''.join(support(p) for p in teaching.POINTS if p["unit"]==i))
    js='''
const P='''+json.dumps(teaching.POINTS,ensure_ascii=False).replace('</','<\\/')+''';let walk=0;
function walkthrough(){const p=P[Number($('#walk-point').value)];walk=Math.min(walk,p.steps.length-1);$('#walk-prerequisite').textContent=p.prerequisites;$('#walk-step').textContent=(walk+1)+' / '+p.steps.length+' · '+p.steps[walk];$('#walk-graph-label').textContent='第 '+(walk+1)+' 步：'+p.title;$('#walk-check').textContent=p.worked_example;$('#walk-prev').disabled=walk===0;$('#walk-next').disabled=walk===p.steps.length-1}
$('#walk-point').onchange=()=>{walk=0;walkthrough()};$('#walk-prev').onclick=()=>{walk=Math.max(0,walk-1);walkthrough()};$('#walk-next').onclick=()=>{walk++;walkthrough()};$('#walk-reset').onclick=()=>{walk=0;walkthrough()};
function inverseDraw(){const x=Number($('#inverse-x').value),y=x*x,g=$('#inverse-svg');g.replaceChildren();[['输入 x',x,40],['平方 y=x²',y,235],['反函数 √y',Math.sqrt(y),430]].forEach(([label,v,pos])=>{g.append(svgEl('rect',{x:pos,y:25,width:165,height:110,rx:8,fill:'#f0f6ff',stroke:'#b6c1ce'}),svgEl('text',{x:pos+14,y:58,'font-size':16},label),svgEl('text',{x:pos+14,y:100,'font-size':26},String(v)))});g.append(svgEl('path',{d:'M205 80h30 M400 80h30',stroke:'#2f6feb','stroke-width':3}));$('#inverse-x-label').textContent=String(x);$('#inverse-note').textContent='非负分支的一来一回：√('+y+')='+x+'。若原输入是 '+(-x)+'，平方仍是 '+y+'，却无法用非负平方根找回负输入；因此必须先限制原函数范围。'}
function cancelDraw(){const x=Number($('#cancel-x').value),s=Math.sqrt(1+1/x**2),v=1/(s+1),g=$('#cancel-svg');g.replaceChildren();['x(√(x²+1)−x)','乘共轭 = x/(√(x²+1)+x)','同除正 x = 1/(√(1+1/x²)+1)'].forEach((label,i)=>{g.append(svgEl('rect',{x:25,y:15+60*i,width:590,height:45,rx:6,fill:i===2?'#dcfce7':'#f0f6ff'}),svgEl('text',{x:40,y:43+60*i,'font-size':18},label))});$('#cancel-x-label').textContent=String(x);$('#cancel-note').textContent='稳定式数值 '+v.toFixed(8)+'，逐渐趋向 1/2；图示数值不是证明，极限由分母趋2且非零推出。'}
$('#inverse-x').oninput=inverseDraw;$('#cancel-x').oninput=cancelDraw;walkthrough();inverseDraw();cancelDraw();
'''
    template=template.replace('</script></body></html>',js+'</script></body></html>')
    parser=VisibleTeaching();parser.feed(template)
    md_body="# 2028 数学一 · 高数第一章：函数、极限与连续\n\n本章面向 2028 备考；未取得该年度官方大纲，按常见基础微积分内容组织。先复习集合、代数、量词与三角弧度；12条教学链和32题均保留条件与解析。\n\n"
    for tier in RESOURCES["keywords"].values():md_body+='\n'.join(tier)+'\n\n'
    md_body+='## 学习顺序与前置依赖\n\n```mermaid\nflowchart LR\n A[集合与合法运算] --> B[函数与复合]\n B --> C[极限与量词]\n C --> D[运算法则与无穷小]\n D --> E[连续与区间定理]\n```\n\n'
    labels={"prerequisites":"前置","principle":"原理","worked_example":"完整例题","misconceptions":"易错诊断","boundaries":"边界","comparison":"比较","practice":"梯度练习与解析","transfer":"迁移"}
    for p in teaching.POINTS:
        md_body+='\n## '+p["title"]+'\n\n'
        for k,label in labels.items():md_body+='### '+label+'\n\n'+p[k]+'\n\n'
        md_body+='### 完整步骤\n\n'+'\n'.join(f'{i+1}. {s}' for i,s in enumerate(p["steps"]))+'\n'
    # Preserve every short projected passage as a formatted reading edition;
    # this is teaching text, never CSS/JS source or repeated word padding.
    md_body+='\n## 页面短读版、图示标注与操作对照\n\n本节保留页面简短讲解及全部界面/图示文本，主知识源的完整推导在前述各点。动态内容在逐题答案和可控推导的原文中同步保留。\n\n'+'\n\n'.join(parser.passages)+'\n'
    for q in data["questions"]:
        md_body+='\n## '+q["id"]+' · '+q["question"]+'\n\n条件：'+'；'.join(q["assumptions"])+"\n\n"
        if q["choices"]:md_body+='\n\n'.join(q["choices"])+"\n\n"
        md_body+='> [!question]- 三级提示\n'+''.join('> '+str(i+1)+'：'+h+'\n' for i,h in enumerate(q["hints"]))+'\n'
        md_body+='> [!example]- 完整解析与独立核对\n> 答案：'+q["answer"]+'\n> '+q["solution"]+'\n> 核对：'+q["check"]+'\n\n'
    md_body+='\n## 比页面更完整的补充推导\n\n'+''.join('> [!example]- 深化证明\n> '+e+'\n\n' for e in teaching.EXTENSIONS)
    refs,review=source_reading();md_body+='\n## 实际来源阅读记录\n\n'
    for r in refs:md_body+='### '+r["source"]+'\n\n定位：'+r["locator"]+'\n\n> '+r["excerpt"].replace('\n','\n> ')+'\n\n'
    md_body+='\n## 审校边界\n\n'+'\n'.join('- '+s for s in review["limitations"])+'\n\nRelated: [[README]] · [[knowledge-baseline]]\n'
    md=obsidian_note(md_body,title="2028 数一高数第一章完整知识源",topic="考研数学一 函数 极限 连续 条件与证明",tags=["math1","calculus","chapter1"],links=["README","knowledge-baseline"])
    manifest={"resources":RESOURCES,"teaching_points":teaching.POINTS,"html_segments":[p for p in parser.passages if normalize_text(p)],
              "markdown_extensions":teaching.EXTENSIONS,"source_ids":[],"host_semantic_audit":"Original analytic proofs and assumptions checked; no claim of full syllabus alignment"}
    result=validate_teaching_package(md,template,manifest)
    assert result["valid"],result
    return md,template,manifest


async def build(output: Path, source_snapshots: Path | None = None):
    output.mkdir(parents=True,exist_ok=True)
    if (output/"runtime-manifest.json").exists():raise RuntimeError("Preserve the registered learner session; select a new output folder")
    if source_snapshots is not None:
        copy_source_snapshots(source_snapshots, output)
    recipe=json.loads((SOURCE/"chapter.json").read_text(encoding="utf-8"));refs,review=source_reading()
    nodes=[{"node_id":n,"title":u["title"],"unit_tag":u["id"],"domain":"math","bloom_level":"analyze","transfer_requirements":"required"} for n,u in zip(NODE_IDS,recipe["units"])]
    record={"units":recipe["units"],"questions":recipe["questions"],"lessons":recipe["lessons"],"nodes":nodes,
            "session_id":"REPLACE_WITH_SESSION_ID","learner_id":"REPLACE_WITH_LEARNER_ID","contexts":{},"created_at":datetime.now(timezone.utc).isoformat()}
    calls=[];temporary_db=output/("registration-"+uuid.uuid4().hex+".sqlite")
    db=output/"learner-runtime.sqlite"
    if db.exists():
        db.rename(output/("previous-incomplete-"+uuid.uuid4().hex+".sqlite"))
    params=StdioServerParameters(command=sys.executable,args=["-m","leap.server"],env={**os.environ,"LEAP__DATABASE_PATH":str(temporary_db),"PYTHONPATH":str(ROOT/"src")})
    async with stdio_client(params) as (r,w):
        async with ClientSession(r,w) as client:
            await client.initialize();catalog=(await client.list_tools()).tools
            async def call(name,args):
                res=await client.call_tool(name,args);payload=res.structured_content or json.loads(next(c.text for c in res.content if c.type=="text"))
                calls.append({"tool":name,"args":args,"result":payload})
                assert not res.is_error and payload.get("ok"),(name,payload)
                return payload
            policy=await call("get_teaching_delivery_policy",{});assert policy["policy"]["version"]=="3.0"
            await call("get_subject_catalog",{"subject":"math"})
            session=await call("create_session",{"learner_id":"math1-2028-v3-learner","topic":"2028 数学一高数第一章：函数、极限与连续"})
            sid=session["session_id"];record.update(session_id=sid,learner_id=session["learner_id"])
            await call("set_learning_configuration",{"session_id":sid,"mode":"exam_prep"})
            await call("save_learning_goal",{"session_id":sid,"goal":"理解第一章每个条件、完成精确求解与反例论证","target_domain":"高等数学","target_outcome":"独立解题并解释前提","prior_knowledge":"尚未诊断","constraints":"尚未取得2028官方大纲；不能伪造掌握状态"})
            baseline=obsidian_note("# 知识基线\n\n"+'\n\n'.join(r["source"]+'\n\n'+r["locator"]+'\n\n> '+r["excerpt"].replace('\n','\n> ') for r in refs)+"\n\n"+'\n'.join(review["limitations"]),title="高数第一章来源阅读与核对",topic="函数 极限定义 连续 复合条件 原始教材",tags=["math1","grounding"],links=["README","knowledge"])
            grounding=await call("save_benchmark_report",{"session_id":sid,"report_text":baseline,"source_refs":refs,"verification":review})
            assert grounding["domain_grounding_stage"]=="completed"
            source_ids=grounding["sources_saved"]
            await call("save_knowledge_nodes",{"session_id":sid,"nodes":nodes})
            await call("save_knowledge_edges",{"session_id":sid,"edges":[{"pre_node_id":NODE_IDS[i],"post_node_id":NODE_IDS[i+1],"relation_type":"prerequisite"} for i in range(3)]})
            await call("validate_knowledge_dag",{"session_id":sid})
            for n in NODE_IDS:record["contexts"][n]=await call("get_teaching_context",{"session_id":sid,"node_id":n})
            md,html,manifest=build_bodies(record);manifest["source_ids"]=source_ids
            packages={}
            for n in NODE_IDS:
                packages[n]=(await call("save_teaching_package",{"session_id":sid,"node_id":n,"subject":"math","markdown":md,"html":html,"manifest":manifest}))["package_id"]
            for q in recipe["questions"]:
                await call("save_assessment_item",{"session_id":sid,"item_id":q["id"],"node_id":NODE_IDS[q["unit"]],"question":q["question"]+('\n'+'\n'.join(q["choices"]) if q["choices"] else ''),
                    "expected_answer":q["answer"],"solution":q["solution"],"assumptions":q["assumptions"],"source_ids":source_ids,"verification_checks":[{"method":"精确推导、边界与解析独立检查","result":q["check"]}],
                    "assessor_scope":"host_semantic_review" if q["kind"]=="proof" else "exact_answer","teaching_package_id":packages[NODE_IDS[q["unit"]]]})
            await call("generate_diagnostic",{"session_id":sid})
            await call("generate_assessment",{"session_id":sid,"node_id":NODE_IDS[0],"count":8})
            await call("start_unit",{"session_id":sid,"node_id":NODE_IDS[0]})
            web=await call("get_web_component_spec",{})
            await call("save_artifact",{"learner_id":session["learner_id"],"session_id":sid,"artifact_type":"chapter_delivery","path_or_uri":str(output/"第一章-函数极限连续.html"),"content":html,"metadata":{"teaching_package_id":packages[NODE_IDS[0]]}})
            bundle=await call("export_session_data",{"session_id":sid})
    temporary_db.replace(db)
    (output/"knowledge.md").write_text(md,encoding="utf-8")
    (output/"学习与答案册.md").write_text(md,encoding="utf-8")
    (output/"第一章-函数极限连续.html").write_text(html,encoding="utf-8")
    (output/"knowledge-baseline.md").write_text(baseline,encoding="utf-8")
    readme="""# 使用第一章

先打开第一章-函数极限连续.html，按四单元顺序学习。每点有完整教学链、可控推导和反例。先独立作答，再逐级提示；证明题等待宿主语义评阅。

原始最全笔记 [[knowledge]] 覆盖页面全部文字与32题解析，补充四个独立证明。[[knowledge-baseline]] 保存阅读定位。答案册 [[学习与答案册]] 可离线阅读；真实学习仍需你自己作答。

来源记录是2026-10-10实际读取的教材快照，不表示制作时重新联网阅读。使用 --source-snapshots 后提供 sources 原始HTML与定位文本；来源行号指txt，来源记录中的SHA256指对应原始HTML，sources/index.json同时列出两种文件的哈希。

本地反馈在匹配工具回执前标记为待确认。展开完整答案后的作答携带提示4，不能算无提示独立展示。制作未提交你的作答；测试只在临时数据库副本运行。

页面中“保存记录与继续评阅”支持导出学习记录、恢复记录、导入回执。生成目录提供 host_sync.py，通过本工程真实MCP核对客观答案并保存证明原文。用已安装本项目的Python环境执行：

```powershell
python host_sync.py '<学习记录.json>' --delivery . --receipt '<宿主回执.json>'
```

然后在页面导入宿主回执，查看最近一次Runtime快照。host-sync-ledger.json与Runtime请求ID日志用于重试恢复。不要把未成功的调用标成成功，也不要直接改 learner-runtime.sqlite 中的成绩。

2028官方大纲目前未取得，未声称完整对齐；原始知识源列明实际教材阅读与核对边界。页面与MCP的离线导出/回执流程已验证；WorkBuddy连接器配置及信任流程属于另一个接入步骤。

> [!note]- 文件说明
> runtime-manifest.json包含当前真实会话、节点和数据库路径；question-bank.json包含题库；mcp-calls.json保留制作调用；delivery-manifest.json记录教学正文要求。正式数据库起始作答为0，验证报告中的成绩均来自临时测试副本。
"""
    (output/"README.md").write_text(obsidian_note(readme,title="2028 数一第一章使用说明",topic="考研数学一 函数 极限 连续 学习方法",tags=["math1","index"],links=["knowledge","knowledge-baseline","学习与答案册"]),encoding="utf-8")
    shutil.copy2(ROOT/"scripts/sync_math1_chapter.py", output/"host_sync.py")
    for name,value in [("question-bank.json",recipe["questions"]),("delivery-manifest.json",manifest),("runtime-session.json",bundle),("mcp-calls.json",calls)]:
        (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
    runtime={"session_id":sid,"learner_id":session["learner_id"],"nodes":nodes,"contexts":record["contexts"],"database":str(db),"repository":str(ROOT),"registered_tools":len(catalog),"registered_items":len(recipe["questions"]),"teaching_packages":packages,"spec":web,"learner_attempts_at_delivery":0,"created_at":record["created_at"]}
    (output/"runtime-manifest.json").write_text(json.dumps(runtime,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"output":str(output),"ok":True,"tools":len(catalog),"packages":len(packages),"questions":len(recipe["questions"]),"mcp_calls":len(calls)},ensure_ascii=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--output",required=True)
    parser.add_argument("--source-snapshots",type=Path,help="Previously read source directory; verify original HTML hashes and extracted text before bundling")
    args=parser.parse_args()
    asyncio.run(build(Path(args.output).resolve(),args.source_snapshots))


if __name__=="__main__":main()
