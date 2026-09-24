-- Local images in Confluence Wiki markup refer to page attachments by name.
function Image(image)
  if not image.src:match('^https?://') then
    image.src = image.src:gsub('\\', '/'):match('([^/]+)$') or image.src
  end
  return image
end
