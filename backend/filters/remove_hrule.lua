-- MarkFlow: 保留/移除分割线
-- 通过 --metadata=keep-separator=true|false 控制
--   true （默认）: 保留 --- / *** 分割线
--   false       : 移除所有分割线

function HorizontalRule()
  local meta = PANDOC_DOCUMENT and PANDOC_DOCUMENT.meta
  local keep = meta and meta['keep-separator']
  local value = keep and pandoc.utils.stringify(keep) or 'true'

  if value == 'false' then
    return pandoc.Null()
  end
  return nil
end
