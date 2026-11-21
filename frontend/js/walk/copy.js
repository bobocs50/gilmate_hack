/** Copies text. Where the browser has no clipboard (a page not on https or localhost), the shown text is selected and copied. */
export async function copyText(text, shown = null) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch { /* the older way below */ }
  if (!shown) return false;
  try {
    const range = document.createRange();
    range.selectNodeContents(shown);
    const selection = getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    return document.execCommand("copy");
  } catch {
    return false;
  }
}
