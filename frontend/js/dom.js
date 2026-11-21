// Small DOM helpers. Everything that comes from data goes in as text, never as HTML.

const SVG_NS = "http://www.w3.org/2000/svg";

/** el("p", { class: "x", hidden: false }, "text", childNode, ...) */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  setAttrs(node, attrs);
  append(node, children);
  return node;
}

export function svg(tag, attrs = {}, ...children) {
  const node = document.createElementNS(SVG_NS, tag);
  setAttrs(node, attrs);
  append(node, children);
  return node;
}

function setAttrs(node, attrs) {
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "on") {
      for (const [type, handler] of Object.entries(value)) node.addEventListener(type, handler);
    } else {
      node.setAttribute(key, value === true ? "" : String(value));
    }
  }
}

// Children may be nested lists (a view maps its data to groups of nodes), so flatten all the way down.
function append(node, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

export function clear(node) {
  node.replaceChildren();
  return node;
}

/** Only http and https links are followed; anything else is shown as plain text. */
export function safeUrl(value) {
  try {
    const url = new URL(String(value));
    return url.protocol === "http:" || url.protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}

/** A source link that shows the host name, or the raw text when it is not a web address. */
export function sourceLink(value) {
  const url = safeUrl(value);
  if (!url) return el("span", { class: "source-plain" }, value ? String(value) : "source unknown");
  return el("a", { class: "source-link", href: url.href, target: "_blank", rel: "noopener noreferrer" }, url.hostname.replace(/^www\./, ""));
}
