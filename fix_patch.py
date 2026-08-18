with open(r'D:\Composio Assignment\composio-app-research\agent\researcher.py', 'r') as f:
    content = f.read()

# Fix the FirecrawlResult constructor inside except block
old = '                    return FirecrawlResult(\n                url=url,\n                content="",\n                metadata={},\n                success=False,\n                error=str(e)\n            )'

new = '                    return FirecrawlResult(\n                        url=url,\n                        content="",\n                        metadata={},\n                        success=False,\n                        error=str(e)\n                    )'

content = content.replace(old, new)

with open(r'D:\Composio Assignment\composio-app-research\agent\researcher.py', 'w') as f:
    f.write(content)

print('Fixed')