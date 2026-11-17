"""Retrieve and revalidate locally reviewed course evidence."""

from __future__ import annotations

from datetime import date, datetime, timezone
from functools import lru_cache
import hashlib
from html import escape
from importlib.resources import files
import json
from typing import TypedDict

from leap.runtime.delivery import VisibleTeaching, delivery_policy, html_teaching_text
from leap.runtime.teaching_page import teaching_asset, teaching_page

FORMAT_VERSION = 2
COURSE_NODE = "limits-derivative"
POINT_FIELDS = (
    "title", "prerequisites", "principle", "worked_example", "misconceptions",
    "boundaries", "comparison", "practice", "transfer",
)


class GroundingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fingerprint(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def reviewed_course() -> dict:
    catalog = files("leap").joinpath("specs", "grounded_calculus.json")
    return json.loads(catalog.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _reviewed_chapters() -> str:
    chapters = files("leap").joinpath("specs", "grounded_calculus_chapters.fragment").read_text(encoding="utf-8")
    parser = VisibleTeaching()
    parser.feed(chapters)
    if parser.teaching_anchors != point_ids(reviewed_course()):
        raise ValueError("Reviewed handout chapters must match the course teaching points in order")
    return chapters


def revision(course: dict) -> str:
    # Rechecking unchanged content extends the review window without discarding
    # the learner's existing report or invalidating its lesson and exercises.
    pack = {key: value for key, value in course.items() if key not in {"reviewed_on", "review_due_on", "status"}}
    assets = [teaching_asset(name) for name in ("lesson.css", "bridge-kernel.js", "calculus-interaction.js")]
    return fingerprint({"delivery_format": FORMAT_VERSION, "pack": pack, "chapters": _reviewed_chapters(),
                        "courseware": assets})


def course_node_id(session_id: str) -> str:
    return f"{session_id}.{COURSE_NODE}"


def resolve_course(topic: str) -> dict:
    course = reviewed_course()
    labels = [course["course_id"], course["title"], *course["aliases"]]
    if topic.strip().casefold() not in {label.casefold() for label in labels}:
        raise GroundingError("grounding_unsupported", "No reviewed source pack covers this topic")
    today = datetime.now(timezone.utc).date()
    if course["status"] != "approved":
        raise GroundingError("grounding_withdrawn", "The reviewed source pack has been withdrawn")
    if not date.fromisoformat(course["reviewed_on"]) <= today < date.fromisoformat(course["review_due_on"]):
        raise GroundingError("grounding_expired", "The source pack requires maintainer review")
    return course


def paragraphs(course: dict):
    for point in course["points"]:
        point_id = point["point_id"]
        for source_id, summary in point["evidence"].items():
            chunk = {"chunk_id": f"{point_id}:{source_id}", "point_id": point_id,
                     "source_id": source_id, **course["sources"][source_id],
                     "summary": summary, "conditions": point["boundaries"]}
            chunk.pop("markers")
            yield {**chunk, "fingerprint": fingerprint(chunk)}


class EvidenceState(TypedDict, total=False):
    topic: str
    point_ids: list[str] | None
    course: dict
    sources: list[dict]
    course_revision: str


@lru_cache(maxsize=1)
def _retrieval_graph():
    from langchain_core.documents import Document
    from langgraph.graph import END, START, StateGraph

    def resolve(state: EvidenceState):
        return {"course": resolve_course(state["topic"])}

    def retrieve(state: EvidenceState):
        requested = state["point_ids"]
        documents = [Document(id=record["chunk_id"], page_content=record["summary"],
                              metadata=record) for record in paragraphs(state["course"])
                     if requested is None or record["point_id"] in requested]
        return {"sources": [document.metadata for document in documents]}

    def validate(state: EvidenceState):
        found = {record["point_id"] for record in state["sources"]}
        expected = set(state["point_ids"]) if state["point_ids"] is not None else {
            point["point_id"] for point in state["course"]["points"]}
        if not found or found != expected:
            raise GroundingError("grounding_coverage_missing", "No reviewed passage covers every requested teaching point")
        return {"course_revision": revision(state["course"])}

    graph = StateGraph(EvidenceState)
    graph.add_node("resolve_course", resolve)
    graph.add_node("retrieve_passages", retrieve)
    graph.add_node("validate_coverage", validate)
    graph.add_edge(START, "resolve_course")
    graph.add_edge("resolve_course", "retrieve_passages")
    graph.add_edge("retrieve_passages", "validate_coverage")
    graph.add_edge("validate_coverage", END)
    return graph.compile()


def retrieve_evidence(topic: str, point_ids: list[str] | None = None) -> EvidenceState:
    from langsmith import tracing_context

    # This workflow uses the local pack even when the host enables cloud tracing.
    with tracing_context(enabled=False):
        return _retrieval_graph().invoke({"topic": topic, "point_ids": point_ids})


def normalized_answer(value: object) -> str:
    return "".join(str(value).split()).replace("−", "-").replace("，", ",").casefold()


def point_ids(course: dict) -> list[str]:
    return [point["point_id"] for point in course["points"]]


def reviewed_items(course: dict, source_ids: list[str]) -> list[dict]:
    ids_by_point = {point_id: [] for point_id in point_ids(course)}
    for source_id, record in zip(source_ids, paragraphs(course)):
        ids_by_point[record["point_id"]].append(source_id)
    return [{"question": point["item"]["question"], "expected_answer": point["item"]["answer"],
             "solution": point["item"]["solution"], "assumptions": [point["boundaries"]],
             "verification_checks": [{"method": "用课内定义独立复算", "result": point["item"]["answer"]}],
             "source_ids": ids_by_point[point["point_id"]]}
            for point in course["points"]]


def print_draft(course: dict) -> dict:
    bibliography = ['<h2>参考文献</h2><ol>']
    for source in course["sources"].values():
        url = escape(source["url"])
        bibliography.append(
            f'<li style="break-inside: avoid; padding-bottom: 2mm">{escape(source["publisher"])}. '
            f'<cite>{escape(source["work"])}</cite>. {escape(source["edition"])}. '
            f'{escape(source["locator"])}. '
            f'<br><a href="{url}" style="font-size: 9pt; overflow-wrap: anywhere">{url}</a></li>'
        )
    bibliography.extend(["</ol>", f'<p>引用版本 {revision(course)[:12]} · 预审日期 {escape(course["reviewed_on"])}</p>'])
    questions = []
    for point in course["points"]:
        item = point["item"]
        questions.append({"title": point["title"], "point_ids": [point["point_id"]], "kind": "short_answer",
                          "prompt_html": f'<p>{escape(item["question"])}</p>',
                          "answer_html": f'<p>{escape(item["answer"])}</p><p>{escape(item["solution"])}</p>'})
    return {"title": course["title"].split("：", 1)[-1], "handout_html": _reviewed_chapters(),
            "questions": questions, "language": "zh-CN", "bibliography_html": "\n".join(bibliography)}


_SECANT_CONTROLS = '''<section class="secant-controls" aria-label="割线趋近实验">
  <label for="secant-h">横坐标增量 h</label>
  <div class="controls">
    <input id="secant-h" type="range" min="0" max="8" step="1" value="8" aria-valuetext="h = 1">
    <button id="secant-play" type="button">播放趋近</button>
    <button id="secant-reset" type="button">重置</button>
  </div>
  <p>h = <span id="secant-h-value">1</span>　割线斜率 = <span id="secant-value">5</span>（无量纲）</p>
  <p>将 h 调到 0 的两边，对照割线的位置与斜率。h = 0 时观察留下来的切线。</p>
  <math aria-label="非零 h 时割线斜率等于四加 h"><mi>m</mi><mo>=</mo><mn>4</mn><mo>+</mo><mi>h</mi></math>（h ≠ 0）
</section>'''


def _visual_contract(course: dict, records: list[dict], source_ids: list[str]) -> tuple[dict, list[str]]:
    research = [dict(id=record["source_id"], evidence_source_id=evidence_id, source=record["url"],
                     locator=record["locator"], excerpt=record["summary"], checked_at=course["reviewed_on"])
                for record, evidence_id in zip(records, source_ids, strict=True)]
    limitations = "图示由课程公式绘出，资料用于核对定义、差商和反例，图中仅展示有限范围。"
    notes = [limitations]
    for source in research:
        notes.extend(source[key] for key in ("source", "locator", "excerpt", "checked_at"))
    figures = []
    visuals = (
        ("limit-graph", "空心点表示左右两段各自逼近的高度", ["左侧", "右侧"]),
        ("secant-graph", "初始图取 h = 1，割线斜率为 (9 − 4)/1 = 5", ["割线", "切线", "横坐标增量"]),
        ("absolute-graph", "两条线在原点接上。左右两侧的斜率不同", ["左支斜率", "右支斜率"]),
    )
    for point, (identifier, caption, labels) in zip(course["points"], visuals, strict=True):
        figures.append(dict(id=identifier, role="data", selector=f"#{identifier}", static_frame=f"#{identifier}",
                            animated=False, caption=caption, labels=labels, source_refs=list(point["evidence"])))
    states = ["当 h 为非零时，显示经过 P 点和 Q 点的割线以及它的斜率。",
              "当 h 为零时两点重合，差商未定义，保留斜率为四的切线。"]
    binding = dict(source="依据平方函数图像及独立展开的差商公式，所有读数共用同一个 h。",
                   assumptions="固定观察点横坐标为二，函数在整个实数范围内定义。",
                   domain="控件在负一至正一之间选择有限的 h 样本。",
                   limits="图形仅展示部分抛物线，差商极限由代数推导确认。",
                   source_refs=figures[1]["source_refs"],
                   quantities=[dict(name="割线斜率", unit="无量纲", selector="#secant-value")],
                   checks=[dict(kind="typical", inputs="取 h 为 1 时，两个点分别在二和三。",
                                expected="两点函数值为四和九，割线斜率为五。",
                                method="直接计算平方，再用纵坐标之差除以横坐标之差。",
                                result="函数值差为五，横坐标差为一，核算斜率为五。"),
                           dict(kind="boundary", inputs="取 h 等于零，两点在同一位置。",
                                expected="割线斜率未定义，左右差商趋近四。",
                                method="只在 h 非零时展开并约分，再计算左右极限。",
                                result="差商等于四加 h，两边极限都为四。")])
    notes.extend([*states, *(binding[key] for key in ("source", "assumptions", "domain", "limits")),
                  *(check[key] for check in binding["checks"] for key in ("inputs", "expected", "method", "result"))])
    figures[1].update(animated=True, model_binding=binding, states=states,
                      controls=dict(parameter="#secant-h", play_pause="#secant-play", reset="#secant-reset"))
    return {"profile": "anatomy.v2", "research": {"sources": research, "limitations": limitations},
            "figures": figures}, notes


def lesson_pair(course: dict, source_ids: list[str]) -> tuple[str, str, dict]:
    """Project the reviewed material into canonical notes and interactive courseware."""
    keywords = {
        "core": ["函数的左右极限与导数定义"],
        "extension": ["割线斜率与瞬时变化率"],
        "advanced": ["可导性与连续性 条件与反例"],
    }
    records = list(paragraphs(course))
    contract, model_notes = _visual_contract(course, records, source_ids)
    points = [{**{key: point[key] for key in POINT_FIELDS},
               "point_id": point["point_id"], "steps": point["steps"],
               "visualization": {"type": "数量关系图", "selector": figure["selector"]}}
              for point, figure in zip(course["points"], contract["figures"], strict=True)]
    queries = [word for words in keywords.values() for word in words]
    course_revision = revision(course)
    source_version = f"引用版本 {course_revision[:12]} · 预审日期 {course['reviewed_on']}"
    content = ["学习资源", *queries]
    extension = (
        "用 ε 语言精确检查导数样例。对任意 ε>0 取 δ=ε。当 0<|h|<δ，"
        "差商 4+h 与 4 的距离为 |h|<ε。这就证明差商极限为 4。"
    )
    markdown = [f"---\ntitle: {json.dumps(course['title'], ensure_ascii=False)}\n"
                "tags: [calculus, limits, derivative]\naliases: [高数导数入门]\n---",
                f"# {course['title']}", "## 学习资源", *queries, source_version, "[[Knowledge_Index]]"]
    lesson = _reviewed_chapters().replace("<!-- LEAP_SECANT_CONTROLS -->", _SECANT_CONTROLS)
    supplements = ['<details class="source-list"><summary>补充推导与引用位置</summary>']
    practice = ['<p>理解检查：写出推理，再查看提示或解析。</p>',
                '<p>评阅时分别核对<span data-review="answer_error">答案</span>和'
                '<span data-review="reasoning_error">推理</span>，帮助你找到下一步该检查什么。</p>']
    for point in points:
        title = point["title"]
        segments = [title, point["prerequisites"], point["principle"], *point["steps"],
                    *(point[key] for key in POINT_FIELDS[3:])]
        content.extend(segments)
        markdown.extend([f"## {title}", *segments[1:]])
        supplements.extend([f'<h3>{escape(title)}</h3>', *(f"<p>{escape(segment)}</p>" for segment in segments[1:])])
        for record in records:
            if record["point_id"] == point["point_id"]:
                label = f"{record['publisher']} · {record['locator']}"
                markdown.append(f"[{label}]({record['url']})")
                supplements.append(f'<p><a href="{escape(record["url"])}">{escape(label)}</a></p>')
    for number, point in enumerate(course["points"], 1):
        item = point["item"]
        practice.append(f'''<article data-practice-index="{number - 1}"><h3>第 {number} 题 · {escape(point['title'])}</h3>
<p>{escape(item['question'])}</p>
<label for="practice-{number}">写出你的推导</label><textarea id="practice-{number}"></textarea>
<button type="button" data-submit-answer>提交作答</button><p class="practice-status" role="status"></p>
<details data-hint="1"><summary>提示 · 回看定义</summary><p>{escape(point['principle'])}</p></details>
<details data-hint="2"><summary>提示 · 写出第一步</summary><p>{escape(point['steps'][0])}</p></details>
<details data-hint="3"><summary>提示 · 检查容易遗漏的条件</summary><p>{escape(point['misconceptions'])}</p></details>
<details><summary>查看解析</summary><details data-hint="4"><summary>确认展开完整解析</summary>
<p>{escape(item['solution'])}</p><p>看完后，请选另一道练习做后置验证。</p></details></details></article>''')
    supplements.extend([f'<p>{escape(source_version)}</p>', '</details>'])
    html = teaching_page(title=course["title"], keywords=queries, lesson_html=lesson + "\n".join(supplements),
                         practice_html="\n".join(practice),
                         links=[(point["point_id"].replace(".", "-"), point["title"]) for point in points],
                         config={"example_id": course["course_id"], "subject": "math", "course_revision": course_revision,
                                 "node": {"node_id": course["course_id"], "title": course["title"], "unit_tag": "calculus"}},
                         interaction_asset="calculus-interaction.js")
    markdown.extend(["## 图示推导与交互练习", html_teaching_text(html),
                     "## 图示模型与核对记录", *model_notes, f"> [!example]- 精确验证\n> {extension}"])
    policy = delivery_policy()
    manifest = {"resources": {"keywords": keywords, "videos": []},
                "teaching_points": points, "html_segments": content,
                "markdown_extensions": [extension], "source_ids": source_ids, "visual_contract": contract,
                "policy_id": policy["policy_id"], "policy_version": policy["version"]}
    return "\n\n".join(markdown), html, manifest
