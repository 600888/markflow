-- Turn Markdown code blocks and images into Confluence storage elements.
local function escape_attribute(value)
  return value:gsub('&', '&amp;'):gsub('"', '&quot;'):gsub('<', '&lt;'):gsub('>', '&gt;')
end

function CodeBlock(block)
  local language = block.classes[1]
  local parameter = ''
  if language and language ~= '' then
    parameter = '<ac:parameter ac:name="language">' .. escape_attribute(language) .. '</ac:parameter>'
  end
  local body = block.text:gsub(']]>', ']]]]><![CDATA[>')
  return pandoc.RawBlock('html',
    '<ac:structured-macro ac:name="code">' .. parameter ..
    '<ac:plain-text-body><![CDATA[' .. body .. ']]></ac:plain-text-body>' ..
    '</ac:structured-macro>')
end

function Image(image)
  local source = image.src
  local resource
  if source:match('^https?://') then
    resource = '<ri:url ri:value="' .. escape_attribute(source) .. '" />'
  else
    local filename = source:gsub('\\', '/'):match('([^/]+)$') or source
    resource = '<ri:attachment ri:filename="' .. escape_attribute(filename) .. '" />'
  end
  local alt = pandoc.utils.stringify(image.caption)
  local alt_attribute = alt ~= '' and ' ac:alt="' .. escape_attribute(alt) .. '"' or ''
  return pandoc.RawInline('html', '<ac:image' .. alt_attribute .. '>' .. resource .. '</ac:image>')
end

function Figure(figure)
  -- A standalone Markdown image becomes a Pandoc Figure. Confluence storage
  -- uses ac:image directly; the HTML figure/figcaption wrapper is unsupported.
  return figure.content
end
