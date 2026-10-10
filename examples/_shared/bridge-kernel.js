/* LEAP_HOST_BRIDGE v3: embed this kernel inline in standalone pages.
 * Runtime receipts own evidence and completion; local exact checks own feedback.
 */
function createLeapBridge(config) {
  "use strict";
  var HINT_DEP = [0, 0.25, 0.40, 0.60, 0.85];
  var STAGE_CN = {estimated:"仅估计",practiced:"练习过",demonstrated:"独立展示",retained:"延迟保持",transferred:"已迁移"};
  var bridge = {
    mode: "demo", context: null, server: {mastery_probability:null,evidence_stage:"estimated",hint_dependency:null,next_review_at:null},
    outbox: [],
    seq: 0, hooks: [], attempts: {}, ledger: {}, receipts: {}, origins: {}, latestAssessmentCall: null
  };
  var state = {
    leap_version: "2.0", example_id: config.example_id, subject: config.subject,
    node: config.node, learner: {learner_id:"REPLACE_WITH_LEARNER_ID",session_id:"REPLACE_WITH_SESSION_ID"},
    events: [], assessment: blankAssessment(),
    ui_state: {mode:"demo",hosted:false,pending_mcp_calls:0,hint_level:0,hint_dependency:null,
      answer_revealed:false,completed:false,local_activity_completed:false}
  };
  var renderHooks = [], drainWired = false;
  function nowSec() { return Math.floor(Date.now() / 1000); }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function isHosted() { return bridge.mode === "hosted"; }
  function blankAssessment() { return {item_id:"",correctness:null,conceptual_understanding:null,reasoning_quality:null,
    application:null,transfer:null,hint_dependency:null,confidence:null,overall_score:null,error_type:"none",
    misconception:"",feedback:"尚未评估",evidence_stage:"estimated",assessor_type:"rule",provisional:true}; }
  function aggregate(d) {
    var weights = {correctness:0.4,conceptual_understanding:0.3,reasoning_quality:0.2,application:0.1}, sum=0,total=0;
    Object.keys(weights).forEach(function(k) {if(typeof d[k]==="number" && Number.isFinite(d[k])) {sum+=d[k]*weights[k];total+=weights[k];}});
    return total ? Math.round(sum/total*100)/100 : null;
  }
  function enqueue(tool,args,note) {
    var call = {call_id:"call_"+(++bridge.seq),tool:tool,args:args||{},status:"pending",created_at:nowSec(),note:note||""};
    bridge.outbox.push(call); bridge.ledger[call.call_id]=clone(call);
    bridge.origins[call.call_id]={session_id:state.learner.session_id,node_id:state.node.node_id};
    bridge.hooks.forEach(function(fn) {fn(clone(call),bridge.outbox.length);});
    return call;
  }
  function enqueueForEvent(ev) {
    if(ev.event_type === "item_completed") {
      enqueue("check_advance_unit",{session_id:state.learner.session_id,node_id:state.node.node_id},"检查推进条件；检查通过本身不代表已推进");
      return;
    }
    if(["attempt_submitted","drag_submitted","code_run"].indexOf(ev.event_type)>=0) {
      var raw=ev.answer==null?"":String(ev.answer), key=ev.item_id||"";
      var call=enqueue("submit_attempt",{session_id:state.learner.session_id,node_id:state.node.node_id,item_id:key||null,
        answer:raw,hint_level:typeof ev.hint_level==="number"?ev.hint_level:state.ui_state.hint_level,
        response_time:typeof ev.response_time==="number"?ev.response_time:null},"保留原始作答与本题 attempt 引用");
      bridge.attempts[key]={call_id:call.call_id,raw_answer:raw,hint_level:call.args.hint_level,assessor_scope:ev.assessor_scope||"exact_answer"};
    } else if(ev.event_type==="reflection_recorded") {
      enqueue("record_reflection",{session_id:state.learner.session_id,node_id:state.node.node_id,reflection:String(ev.answer||"")},"保存反思，不作为正确性评分");
    }
  }
  function pushEvent(event_type,payload) {
    var ev=Object.assign({event_type:event_type,item_id:""},payload||{},{created_at:nowSec()});
    state.events.push(ev); enqueueForEvent(ev); renderAll(); return ev;
  }
  function setHint(level) {
    if(!Number.isInteger(level)||level<0||level>4) throw new RangeError("hint level must be 0..4");
    state.ui_state.hint_level=Math.max(level,state.ui_state.hint_level);
    if(level===4) state.ui_state.answer_revealed=true;
    // Local hint usage is separate from the Runtime's historical estimate.
    state.ui_state.local_hint_dependency=HINT_DEP[state.ui_state.hint_level]; renderAll();
  }
  function commitAssessment(item) {
    var attempt=bridge.attempts[item.item_id];
    if(!attempt) throw new Error("本题尚未提交作答，不能借用其他题目的 attempt");
    if(attempt.assessor_scope==="host_semantic_review"||item.assessor_scope==="host_semantic_review") {
      bridge.latestAssessmentCall=null;
      state.assessment=Object.assign(blankAssessment(),{item_id:item.item_id,feedback:"原始作答已收集，等待宿主审核论证",evidence_stage:bridge.server.evidence_stage});
      renderAll(); return clone(state.assessment);
    }
    if(typeof item.correctness!=="number"||!Number.isFinite(item.correctness)||item.correctness<0||item.correctness>1) throw new TypeError("Exact checks require an explicit correctness value");
    // An exact answer does not establish reasoning, concepts, transfer or self-confidence.
    var value=Math.round(item.correctness*100)/100;
    var a=Object.assign(blankAssessment(),{item_id:item.item_id,correctness:value,overall_score:value,
      feedback:item.feedback||"仅核对客观答案",error_type:item.error_type||"none",misconception:item.misconception||"",
      hint_dependency:HINT_DEP[Math.min(attempt.hint_level,4)],evidence_stage:bridge.server.evidence_stage,provisional:true});
    state.assessment=a;
    var call=enqueue("commit_assessment",{attempt_id:"{{"+attempt.call_id+".attempt_id}}",raw_answer:attempt.raw_answer,
      assessor_type:"rule",correctness:a.correctness,hint_dependency:a.hint_dependency},"仅提交客观正确性；其他维度待相应证据评估");
    bridge.latestAssessmentCall=call.call_id; renderAll(); return clone(a);
  }
  function setCompleted(itemId,reason) {
    state.ui_state.local_activity_completed=true;
    pushEvent("item_completed",{item_id:itemId,reason:reason||"local_check_finished"});
  }
  function hydrate(ctx) {
    if(!ctx||typeof ctx!=="object"||ctx.ok===false) throw new TypeError("hydrate requires a successful Runtime context");
    var sess=ctx.session||{},node=ctx.current_node||ctx.node||{},ks=ctx.knowledge_state||{};
    var learner=ctx.learner_id||sess.learner_id, sid=ctx.session_id||sess.session_id;
    if(!learner||!sid||!node.node_id) throw new TypeError("Runtime context needs learner, session and node identifiers");
    if(sid!==state.learner.session_id||node.node_id!==state.node.node_id) {
      if(bridge.outbox.length) throw new Error("切换上下文前必须先取走并处理原节点的调用队列");
      bridge.attempts={}; bridge.latestAssessmentCall=null; state.ui_state.completed=false; state.ui_state.local_activity_completed=false;
      state.ui_state.hint_level=0; state.ui_state.answer_revealed=false; state.assessment=blankAssessment();
    }
    state.learner={learner_id:learner,session_id:sid}; state.node=Object.assign({},state.node,node);
    bridge.context=clone(ctx); bridge.mode="hosted";
    bridge.server={mastery_probability:typeof ks.mastery_probability==="number"?ks.mastery_probability:null,
      evidence_stage:ks.evidence_stage||"estimated",hint_dependency:typeof ks.hint_dependency==="number"?ks.hint_dependency:null,
      next_review_at:ks.next_review_at||null};
    state.assessment.evidence_stage=bridge.server.evidence_stage;
    state.ui_state.hint_dependency=bridge.server.hint_dependency;
    // A state snapshot does not confirm a particular pending assessment receipt.
    renderAll(); return snapshot();
  }
  function applyToolResults(results) {
    // Validate the whole batch before changing any receipt or displayed state.
    var merged=Object.assign({},bridge.receipts,results||{});
    Object.keys(results||{}).forEach(function(id) {
      var call=bridge.ledger[id],result=results[id];
      if(!call) throw new Error("Unknown outbox call receipt: "+id);
      if(!result||result.ok!==true) return;
      if(call.tool==="commit_assessment") {
        var match=/^\{\{(call_\d+)\.attempt_id\}\}$/.exec(call.args.attempt_id);
        var attemptReceipt=match&&merged[match[1]];
        if(!attemptReceipt||attemptReceipt.ok!==true||!attemptReceipt.attempt_id||result.attempt_id!==attemptReceipt.attempt_id) throw new Error("Assessment receipt does not match its attempt");
        if(!result.result_id||typeof result.overall_score!=="number"||!Number.isFinite(result.overall_score)) throw new Error("Incomplete assessment receipt");
      }
    });
    Object.keys(results||{}).forEach(function(id) {
      var call=bridge.ledger[id], result=results[id];
      bridge.receipts[id]=clone(result);
      if(!result||result.ok!==true) return;
      var origin=bridge.origins[id];
      if(origin.session_id!==state.learner.session_id||origin.node_id!==state.node.node_id) return;
      if(call.tool==="commit_assessment" && id===bridge.latestAssessmentCall) {
        Object.assign(state.assessment,result.scores||{},{overall_score:result.overall_score,provisional:false,result_id:result.result_id});
        if(result.learner_state) bridge.server=Object.assign({},bridge.server,result.learner_state);
      }
      if(call.tool==="advance_unit"&&result.advanced===true&&result.session_id===state.learner.session_id) state.ui_state.completed=true;
    });
    state.assessment.evidence_stage=bridge.server.evidence_stage;
    state.ui_state.hint_dependency=bridge.server.hint_dependency; renderAll(); return snapshot();
  }
  function requestAdvance() {
    var call=enqueue("advance_unit",{session_id:state.learner.session_id,node_id:state.node.node_id},"Runtime State Guard 批准后推进"); renderAll(); return clone(call);
  }
  function peekOutbox() {return clone(bridge.outbox);}
  function drainOutbox() {var out=peekOutbox();bridge.outbox.length=0;renderAll();return out;}
  function snapshot() {
    var out=clone(state); out.ui_state.mode=bridge.mode; out.ui_state.hosted=isHosted();out.ui_state.pending_mcp_calls=bridge.outbox.length;
    out.outbox=peekOutbox();return out;
  }
  function renderOutput() {
    var el=document.getElementById("leap-interaction-output");if(el) el.textContent=JSON.stringify(snapshot(),null,2);
    var sum=document.getElementById("consoleSummary");if(sum) sum.textContent="AGENT OUTPUT · 已记录 "+state.events.length+" 条事件"+(state.ui_state.completed?" · Runtime 已推进":state.ui_state.local_activity_completed?" · 本地练习已结束，待 Runtime 检查":"");
  }
  function renderSpine() {
    var cur=bridge.server.evidence_stage,stages=Object.keys(STAGE_CN),idx=stages.indexOf(cur);
    document.querySelectorAll("#evTrack .ev-seg").forEach(function(el,i){el.classList.toggle("is-on",i<=idx);});
    var name=document.getElementById("evName");if(name) name.textContent=cur+" · "+STAGE_CN[cur];
    var val=document.getElementById("masVal"),fill=document.getElementById("masFill"),m=bridge.server.mastery_probability;
    if(val) val.textContent=typeof m==="number"?m.toFixed(2):"未评估";
    if(fill) fill.style.width=typeof m==="number"?Math.round(m*100)+"%":"0%";
    var review=document.querySelector(".spine-rev .val"),at=bridge.server.next_review_at;
    if(review) review.textContent=at?new Date(at*1000).toLocaleString():"尚未安排";
    var note=document.getElementById("ladderNote");if(note) note.textContent="提示只在主动请求时展开；当前提示层级 "+state.ui_state.hint_level+"。";
  }
  function renderBridge() {
    var mode=document.getElementById("bridgeMode"),sum=document.getElementById("bridgeSummary"),note=document.getElementById("spineNote");
    if(mode) mode.textContent="BRIDGE · "+(isHosted()?"Runtime 上下文快照":"离线演示");
    if(sum) sum.textContent="待处理调用 "+bridge.outbox.length+" 条。客观答案反馈需回执确认；论证等待宿主审核。";
    if(note) note.textContent=isHosted()?"显示最近一次 Runtime 上下文；新作答等待实际调用回执。":"掌握度未评估；离线操作仅收集学习动作。";
    var button=document.getElementById("bridgeDrain"),pre=document.getElementById("bridgeOutbox");
    if(button&&!drainWired) {drainWired=true;button.addEventListener("click",function(){if(pre){pre.hidden=!pre.hidden;pre.textContent=JSON.stringify(peekOutbox(),null,2);}});}
    if(button) button.disabled=!bridge.outbox.length;
  }
  function renderRail() {
    var dots=document.getElementById("railDots"),n=state.events.length;
    if(dots) {dots.replaceChildren();state.events.forEach(function(e,i){var d=document.createElement("span");d.className="rail-dot";d.style.left=((i+1)/(n+1)*100)+"%";d.title=e.event_type;dots.appendChild(d);});}
    var count=document.getElementById("railCount"),last=document.getElementById("railLast");
    if(count) count.textContent="已产生 "+n+" 条事件（只追加，不覆盖）";
    if(last&&n) last.textContent="最近："+state.events[n-1].event_type;
  }
  function renderAll() {renderOutput();renderSpine();renderBridge();renderRail();renderHooks.forEach(function(fn){fn();});}
  function onRender(fn) {renderHooks.push(fn);fn();}
  return {hydrate:hydrate,isHosted:isHosted,getInteractionResult:snapshot,getState:function(){return state;},getMastery:function(){return bridge.server.mastery_probability;},
    peekOutbox:peekOutbox,drainOutbox:drainOutbox,onOutboxChange:function(fn){bridge.hooks.push(fn);},pushEvent:pushEvent,
    setHint:setHint,commitAssessment:commitAssessment,setCompleted:setCompleted,applyToolResults:applyToolResults,requestAdvance:requestAdvance,
    aggregate:aggregate,onRender:onRender,refresh:renderAll,HINT_DEP:HINT_DEP,STAGE_CN:STAGE_CN};
}
