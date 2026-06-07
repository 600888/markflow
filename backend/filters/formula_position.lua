-- MarkFlow: 公式位置过滤器
-- 通过 --metadata=formula-position=inline|display|smart 控制
--   inline  : 将 $$ 块级公式转为 $ 行内公式
--   display : 将 $ 行内公式转为 $$ 块级公式
--   smart   : 保持原样（默认）

function Math(el)
  local meta = PANDOC_DOCUMENT and PANDOC_DOCUMENT.meta
  local pos = meta and meta['formula-position']
  local value = pos and pandoc.utils.stringify(pos) or 'smart'

  if value == 'display' and el.mathtype == 'InlineMath' then
    return pandoc.Math('DisplayMath', el.text)
  elseif value == 'inline' and el.mathtype == 'DisplayMath' then
    return pandoc.Math('InlineMath', el.text)
  end
  -- smart / default: 无操作
  return nil
end
