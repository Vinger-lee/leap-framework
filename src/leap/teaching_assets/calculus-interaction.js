// Each frame is computed from the same h used by the quantity readouts.
(() => {
  const get = (id) => document.getElementById(id);
  const values = [-1, -0.5, -0.1, -0.01, 0, 0.01, 0.1, 0.5, 1];
  const slider = get("secant-h");
  const play = get("secant-play");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  let timer = null;
  const format = (value) => Number(value.toFixed(4)).toString();

  function render() {
    const h = values[Number(slider.value)];
    const x = 2 + h;
    const y = x * x;
    const qx = 54 + 108 * x;
    const qy = 164 - 15 * y;
    const slope = 4 + h;
    get("secant-h-value").textContent = format(h);
    get("secant-value").textContent = h === 0 ? "未定义（切线斜率 4）" : format(slope);
    slider.setAttribute("aria-valuetext", `h = ${format(h)}`);
    get("secant-line").setAttribute("d", `M196 ${104 + 74 * 15 * slope / 108} L400 ${104 - 130 * 15 * slope / 108}`);
    get("secant-rise").setAttribute("d", `M270 104H${qx}V${qy}`);
    get("secant-q").setAttribute("cx", qx);
    get("secant-q").setAttribute("cy", qy);
    for (const id of ["secant-line", "secant-rise", "secant-q"]) {
      get(id).setAttribute("visibility", h === 0 ? "hidden" : "visible");
    }
    const labels = [
      ["secant-q-label", qx + (h < 0 ? -86 : 12), qy - 12, `Q(${format(x)}, ${format(y)})`],
      ["secant-run-label", (270 + qx) / 2 - 18, 124, `h = ${format(h)}`],
      ["secant-rise-label", qx + 11, (104 + qy) / 2, `Δf = ${format(y - 4)}`],
    ];
    for (const [id, labelX, labelY, label] of labels) {
      const element = get(id);
      element.setAttribute("x", labelX);
      element.setAttribute("y", labelY);
      element.setAttribute("visibility", Math.abs(h) >= 0.5 ? "visible" : "hidden");
      element.textContent = label;
    }
  }

  function pause() {
    clearInterval(timer);
    timer = null;
    play.textContent = "播放趋近";
  }

  slider.addEventListener("input", () => { pause(); render(); });
  get("secant-reset").addEventListener("click", () => { pause(); slider.value = "8"; render(); });
  play.addEventListener("click", () => {
    if (timer !== null) { pause(); return; }
    if (reduced.matches) { slider.value = "4"; render(); return; }
    if (slider.value === "4") slider.value = "8";
    render();
    play.textContent = "暂停趋近";
    timer = setInterval(() => {
      const current = Number(slider.value);
      slider.value = String(current + Math.sign(4 - current));
      render();
      if (slider.value === "4") pause();
    }, 500);
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden) pause(); });
  reduced.addEventListener("change", pause);
  if (typeof IntersectionObserver !== "undefined") {
    new IntersectionObserver(([entry]) => { if (!entry.isIntersecting) pause(); }).observe(get("secant-graph"));
  }
  render();
})();

for (const item of document.querySelectorAll("[data-practice-index]")) {
  const index = Number(item.dataset.practiceIndex);
  const answerInput = item.querySelector("textarea");
  const status = item.querySelector(".practice-status");
  let hintLevel = 0;
  let pendingItem = null;
  item.querySelectorAll("[data-hint]").forEach((hint) => hint.addEventListener("toggle", () => {
    if (hint.open) hintLevel = Math.max(hintLevel, Number(hint.dataset.hint));
  }));
  item.querySelector("[data-submit-answer]").addEventListener("click", () => {
    const answer = answerInput.value;
    if (!answer.trim()) { status.textContent = "请先写出作答或推导。"; return; }
    if (hintLevel === 4) { status.textContent = "本题解析已展开，请用另一道题独立验证。"; return; }
    const itemId = window.LEAP.reviewedItemId(index);
    if (!itemId) {
      status.textContent = "可展开解析自查。连接宿主并登记本题后，才能保存作答。";
      return;
    }
    pendingItem = itemId;
    status.textContent = "原始作答已排队，等待宿主保存和评阅。";
    window.LEAP.pushEvent("attempt_submitted", {item_id: itemId, answer, hint_level: hintLevel,
      assessor_scope: "host_semantic_review"});
    window.LEAP.commitAssessment({item_id: itemId, assessor_scope: "host_semantic_review"});
  });
  window.LEAP.onRender(() => {
    const receipt = pendingItem && window.LEAP.attemptReceipt(pendingItem);
    if (receipt) {
      pendingItem = null;
      status.textContent = receipt.ok ? "作答已保存，等待宿主评阅推理。" : (receipt.error?.message || "作答保存失败。");
    }
  });
}
