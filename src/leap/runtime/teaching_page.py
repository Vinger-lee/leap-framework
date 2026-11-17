"""Assemble a standalone teaching page with the same browser bridge as the examples."""

from functools import lru_cache
from html import escape
from importlib.resources import files
import json


@lru_cache(maxsize=None)
def teaching_asset(name: str) -> str:
    return files("leap").joinpath("teaching_assets", name).read_text(encoding="utf-8")


def teaching_page(*, title: str, keywords: list[str], lesson_html: str, practice_html: str,
                  links: list[tuple[str, str]], config: dict, interaction_asset: str) -> str:
    safe_title = escape(title)
    topics = "".join(f'<a href="#{escape(anchor)}">{escape(label)}</a>' for anchor, label in links)
    config_json = json.dumps(config, ensure_ascii=True).replace("<", "\\u003c")
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title><style>{teaching_asset("lesson.css")}</style></head><body>
<header class="lesson-header"><div class="wrap">
  <h1>{safe_title}</h1>
  <p>学习资源 · {escape(" · ".join(keywords))}</p>
  <nav aria-label="教学内容">{topics}</nav>
</div></header>
<main class="wrap lesson-grid">
  <article aria-label="教学内容"><h2>教学内容</h2>{lesson_html}</article>
  <aside>
    <section class="print-panel" data-leap-print>
      <h2>打印同版讲义</h2>
      <div class="controls">
        <select aria-label="版式" data-print-edition>
          <option value="combined">讲义与练习</option><option value="handout">讲义册</option>
          <option value="workbook">题目册</option><option value="answers">答案与解析</option>
        </select>
        <select aria-label="方向" data-print-orientation>
          <option value="portrait">纵向</option><option value="landscape">横向</option>
        </select>
        <button type="button" data-print-button>导出 PDF</button>
      </div>
      <p role="status" data-print-status>连接宿主后可导出当前课件对应的 A4 资料。</p>
    </section>
    <section class="practice"><h2>交互练习</h2>{practice_html}</section>
    <details class="agent-panel"><summary id="consoleSummary">AGENT OUTPUT</summary>
      <p id="bridgeMode"></p><p id="bridgeSummary"></p>
      <section class="progress-spine" aria-label="学习证据">
        <p>证据阶段 <span id="evName"></span> · 掌握度 <span id="masVal"></span></p>
        <div class="progress-track" aria-hidden="true"><span id="masFill"></span></div>
        <p id="spineNote"></p><p id="ladderNote"></p>
      </section>
      <div id="railDots" class="evidence-rail" aria-hidden="true"></div><p id="railCount"></p><p id="railLast"></p>
      <button id="bridgeDrain" type="button">查看待发调用</button><pre id="bridgeOutbox" hidden></pre>
      <pre id="leap-interaction-output" aria-label="宿主交互记录"></pre>
    </details>
  </aside>
</main>
<script>{teaching_asset("bridge-kernel.js")}
window.LEAP = createLeapBridge({config_json});
{teaching_asset(interaction_asset)}
window.LEAP.refresh();</script></body></html>'''
