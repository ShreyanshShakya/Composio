with open(r'D:\Composio Assignment\composio-app-research\agent\researcher.py', 'r') as f:
    content = f.read()

# Add a finally block to explicitly close the try
old = '''            except Exception as e:
                return FirecrawlResult(
                    url=url,
                    content="",
                    metadata={},
                    success=False,
                    error=str(e)
                )
            
            return FirecrawlResult('''

new = '''            except Exception as e:
                return FirecrawlResult(
                    url=url,
                    content="",
                    metadata={},
                    success=False,
                    error=str(e)
                )
            finally:
                pass
            
            return FirecrawlResult('''

content = content.replace(old, new)

with open(r'D:\Composio Assignment\composio-app-research\agent\researcher.py', 'w') as f:
    f.write(content)

print('Added finally block')