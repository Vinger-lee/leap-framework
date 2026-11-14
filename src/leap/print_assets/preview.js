
(() => {
  const direction = document.getElementById("leapPrintDirection");
  const notice = document.getElementById("leapPrintNotice");
  const sheet = document.getElementById("leapPaper");
  const content = document.querySelector(".print-content");
  let original = null;
  const chosen = new URLSearchParams(location.search).get("orientation");
  if (chosen === "portrait" || chosen === "landscape") direction.value = chosen;

  async function printDocument() {
    if (original) return;
    await document.fonts.ready;
    const landscape = direction.value === "landscape";
    const [top, right, bottom, left] = printMargins;
    const width = (landscape ? 297 : 210) - left - right;
    const height = (landscape ? 210 : 297) - top - bottom;
    if (Math.min(width, height) < 60) {
      notice.textContent = "当前页边距在这个方向上留出的空间不足。请改回原方向或调整页边距。";
      return;
    }
    sheet.textContent = `@page { size: A4 ${direction.value}; margin: ${printMargins.map(m => m + "mm").join(" ")}; }`;
    original = content.cloneNode(true);
    content.classList.add("print-measurement");
    content.style.width = `${width}mm`;
    const issue = paginatePrint(height * 96 / 25.4, false)
      || (content.scrollWidth > content.clientWidth + 4 ? "内容超过 A4 可打印宽度，请调整图表或文本。" : null);
    content.style.removeProperty("width");
    content.classList.remove("print-measurement");
    if (issue) {
      notice.textContent = issue;
      content.replaceChildren(...original.childNodes);
      original = null;
      return;
    }
    notice.textContent = "";
    window.print();
  }

  window.addEventListener("afterprint", () => {
    if (!original) return;
    content.replaceChildren(...original.childNodes);
    original = null;
  });
  document.getElementById("leapPrintNow").addEventListener("click", printDocument);
  if (new URLSearchParams(location.search).get("print") === "1") {
    if (document.readyState === "complete") printDocument();
    else window.addEventListener("load", printDocument, {once: true});
  }
})();
