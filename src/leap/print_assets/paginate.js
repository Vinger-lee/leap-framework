(pageHeight, checkOverflow = true) => {
  const spare = 14;
  const limit = pageHeight - spare;
  const images = [...document.querySelectorAll("img")];
  if (images.some(img => !img.complete || !img.naturalWidth)) {
    return "A print image did not load. Use embedded raster images or inline SVG.";
  }

  let gridRevision = 0;
  function continuation(question) {
    const part = document.createElement("article");
    part.className = "print-question print-new-page";
    part.dataset.question = question.dataset.question;
    const heading = document.createElement("h2");
    heading.textContent = `第 ${part.dataset.question} 题（续）`;
    part.append(heading);
    return part;
  }

  // Oversize text can break at normal text boundaries. For repeatable answer
  // areas, pack whole rows into labelled continuation pages instead.
  function takeUnits(block, available) {
    if (block.matches(".answer-lines, .answer-code, .answer-table")) {
      const source = block.matches("table") ? block.tBodies[0] : block;
      const child = source.firstElementChild;
      if (!child) return null;
      const rowHeight = Math.max(child.getBoundingClientRect().height, 1);
      const headerHeight = block.tHead?.getBoundingClientRect().height || 0;
      const count = Math.floor((available - headerHeight - 3) / rowHeight);
      if (count < 1) return null;
      const piece = block.cloneNode(block.matches("table"));
      const target = block.matches("table") ? piece.tBodies[0] : piece;
      target.replaceChildren();
      for (let i = 0; i < count && source.firstElementChild; i++) {
        target.append(source.firstElementChild);
      }
      if (!source.firstElementChild) block.remove();
      return piece;
    }
    if (block.matches(".answer-grid, .answer-space, .answer-axes") && available >= 32) {
      const height = block.getBoundingClientRect().height;
      const piece = block.cloneNode(true);
      const pattern = piece.querySelector("pattern[id]");
      if (pattern) {
        const id = `${pattern.id}-part-${++gridRevision}`;
        piece.querySelector("rect").setAttribute("fill", `url(#${id})`);
        pattern.id = id;
      }
      const taken = Math.min(Math.floor(available - 2), height);
      piece.style.height = `${taken}px`;
      if (height - taken > 2) block.style.height = `${height - taken}px`;
      else block.remove();
      return piece;
    }
    return null;
  }

  const questions = [...document.querySelectorAll(".print-question[data-question]")];
  for (const [index, question] of questions.entries()) {
    const bounds = question.getBoundingClientRect();
    if (bounds.height <= limit) continue;
    const combined = question.parentElement.matches("section.print-new-page");
    const beginsPage = question.classList.contains("print-new-page");
    const parentTop = question.parentElement.getBoundingClientRect().top;
    const firstLimit = index === 0 && !beginsPage ? limit - (bounds.top - parentTop) : limit;
    if (!combined && index === 0 && beginsPage) question.classList.remove("print-new-page");
    const body = [...question.children].slice(1).flatMap(block => {
      // Direct prompt paragraphs, figures and lists are natural boundaries.
      if (block.matches(".print-prompt") && block.children.length &&
          [...block.childNodes].every(node => node.nodeType !== 3 || !node.textContent.trim())) {
        const pieces = [...block.children];
        for (const piece of pieces) question.insertBefore(piece, block);
        block.remove();
        return pieces;
      }
      return [block];
    });
    for (const block of body) block.remove();
    let part = question;
    for (const block of body) {
      part.append(block);
      const available = part === question ? firstLimit : limit;
      if (part.getBoundingClientRect().height <= available) continue;
      const height = block.getBoundingClientRect().height + 8;
      const divisible = block.matches(".answer-lines, .answer-code, .answer-table, .answer-grid, .answer-space, .answer-axes");
      if (divisible && height > limit - 38) {
        while (block.isConnected) {
          const used = block.getBoundingClientRect().top - part.getBoundingClientRect().top;
          const piece = takeUnits(block, (part === question ? firstLimit : limit) - used);
          if (piece) {
            if (block.isConnected) part.insertBefore(piece, block);
            else part.append(piece);
          }
          if (!block.isConnected) break;
          if (!piece && part.children.length === 2 && (part !== question || firstLimit === limit)) {
            return "An answer row cannot fit on an A4 page.";
          }
          const next = continuation(question);
          part.after(next);
          part = next;
          part.append(block);
        }
      } else {
        if (part.children.length > 2) {
          const next = continuation(question);
          part.after(next);
          part = next;
          part.append(block);
        }
        if (part.getBoundingClientRect().height > limit) part.style.breakInside = "auto";
      }
    }
  }
  if (checkOverflow && document.documentElement.scrollWidth > document.documentElement.clientWidth + 4) {
    return "Print content extends past the A4 margins. Resize wide figures, tables, or text.";
  }
  return null;
}
