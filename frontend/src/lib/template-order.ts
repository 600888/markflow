import type { TemplateInfo } from "../types";

const BUILTIN_TEMPLATE_ORDER = [
  "minimal",
  "academic",
  "report",
  "test_report",
] as const;

/**
 * 固定模板展示顺序：已知内置模板、其他内置模板、自定义模板。
 * 同一组内返回 0，依靠稳定排序保留后端给出的原始顺序。
 */
export function orderTemplates(templates: TemplateInfo[]): TemplateInfo[] {
  return [...templates].sort((left, right) => {
    const leftBuiltinIndex = BUILTIN_TEMPLATE_ORDER.indexOf(
      left.slug as (typeof BUILTIN_TEMPLATE_ORDER)[number],
    );
    const rightBuiltinIndex = BUILTIN_TEMPLATE_ORDER.indexOf(
      right.slug as (typeof BUILTIN_TEMPLATE_ORDER)[number],
    );

    const leftGroup = left.is_custom ? 2 : leftBuiltinIndex >= 0 ? 0 : 1;
    const rightGroup = right.is_custom ? 2 : rightBuiltinIndex >= 0 ? 0 : 1;
    if (leftGroup !== rightGroup) return leftGroup - rightGroup;

    if (leftGroup === 0) return leftBuiltinIndex - rightBuiltinIndex;
    return 0;
  });
}
