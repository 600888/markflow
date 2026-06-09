-- MarkFlow: 移除分割线
-- 此过滤器只在用户关闭"保留分割线"选项时由 Pandoc 加载，
-- 因此不需要额外条件判断，始终移除所有 <hr/> 元素。
--
-- 兼容 Pandoc 2.x / 3.x：Pandoc 2.x 没有 pandoc.Null()，
-- 返回空列表 {} 在两种版本中均能移除当前元素。

function HorizontalRule()
  return {}
end
