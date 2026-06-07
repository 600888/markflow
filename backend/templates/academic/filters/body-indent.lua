-- 正文段落映射到 Body Text 样式（带首行缩进）
-- 标题 (Header) 不受影响
function Para(el)
  if not el.attr then
    return el
  end
  -- 用 Pandoc 的 Attr 构造带 custom-style 的新属性
  local classes = el.attr.classes
  local kv = el.attr.attributes
  kv["custom-style"] = "Body Text"
  el.attr = pandoc.Attr(el.attr.identifier, classes, kv)
  return el
end
