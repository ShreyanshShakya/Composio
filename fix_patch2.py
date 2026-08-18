with open(r'D:\Composio Assignment\composio-app-research\agent\researcher.py', 'r') as f:
    content = f.read()

# Fix the except body indentation - should be at indent 12 (4 more than try at 8)
old = '        except Exception as e:\n                    return FirecrawlResult(\n                        url=url,\n                        content="",\n                        metadata={},\n                        success=False,\n                        error=str(e)\n                    )'

new = '        except Exception as e:\n            return FirecrawlResult(\n                url=url,\n                content="",\n                metadata={},\n                success=False,\n                error=str(e)\n            )'

content = content.replace(old, new)

with open(r'D:\Composio Assignment\composio-app-research\agent\researcher.py', 'w') as f:
    f.write(content)

print('Fixed except body indentation')