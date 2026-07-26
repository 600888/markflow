export interface PasteClipboardContent {
  html: string;
  plainText: string;
  types: readonly string[];
}

const CODE_EDITOR_CLIPBOARD_TYPES = new Set([
  "application/vnd.code.copyMetadata",
  "vscode-editor-data",
]);

const MARKDOWN_BLOCK_PATTERN =
  /(?:^|\n)[ \t]{0,3}(?:#{1,6}[ \t]+|>[ \t]?|`{3,}|~{3,}|(?:[-+*]|\d+[.)])[ \t]+|(?:[-*_][ \t]*){3,}(?:\n|$))/;

const MARKDOWN_INLINE_PATTERN =
  /(?:\*\*[^*\n]+\*\*|__[^_\n]+__|!\[[^\]\n]*\]\([^)]+\)|\[[^\]\n]+\]\([^)]+\)|`[^`\n]+`)/;

function isCodeEditorHtml(html: string): boolean {
  return (
    /(?:<meta[^>]+(?:vscode|code\.copyMetadata)|data-vscode-)/i.test(html) ||
    (/white-space:\s*pre(?:-wrap)?/i.test(html) &&
      /font-family\s*:/i.test(html))
  );
}

function looksLikeMarkdown(text: string): boolean {
  return (
    MARKDOWN_BLOCK_PATTERN.test(text.replace(/\r\n?/g, "\n")) ||
    MARKDOWN_INLINE_PATTERN.test(text)
  );
}

export function shouldPreservePlainText({
  html,
  plainText,
  types,
}: PasteClipboardContent): boolean {
  if (!plainText) return false;

  return (
    types.some((type) => CODE_EDITOR_CLIPBOARD_TYPES.has(type)) ||
    isCodeEditorHtml(html) ||
    looksLikeMarkdown(plainText)
  );
}
