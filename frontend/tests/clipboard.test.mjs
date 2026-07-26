import assert from "node:assert/strict";
import test from "node:test";

import { shouldPreservePlainText } from "../src/lib/clipboard.ts";

test("preserves Markdown copied from VS Code instead of converting its HTML", () => {
  const markdown = `# IEC 104 系列（二）

> **核心目标**：精通报文格式。

\`\`\`mermaid
flowchart TB
  APDU["APDU = APCI + ASDU"]
\`\`\``;

  assert.equal(
    shouldPreservePlainText({
      plainText: markdown,
      html: `<div style="color: #ccc; font-family: Consolas; white-space: pre;">
        <span style="color: #569cd6;"># IEC 104 系列（二）</span>
      </div>`,
      types: ["text/plain", "text/html"],
    }),
    true,
  );
});

test("preserves plain text when VS Code clipboard metadata is present", () => {
  assert.equal(
    shouldPreservePlainText({
      plainText: "普通文本",
      html: "<div>普通文本</div>",
      types: ["text/plain", "text/html", "application/vnd.code.copyMetadata"],
    }),
    true,
  );
});

test("keeps rich web content on the HTML conversion path", () => {
  assert.equal(
    shouldPreservePlainText({
      plainText: "A bold web paragraph",
      html: "<p>A <strong>bold</strong> web paragraph</p>",
      types: ["text/plain", "text/html"],
    }),
    false,
  );
});
