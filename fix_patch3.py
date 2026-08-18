with open(r'D:\Composio Assignment\composio-app-research\agent\researcher.py', 'r') as f:
    content = f.read()

# Add a pass statement after except block to properly close the try/except
old = '''                )
        except Exception as e:
            return FirecrawlResult(
                url=url,
                content="",
                metadata={},
                success=False,
                error=str(e)
            )

        async def firecrawl_crawl'''

new = '''                )
        except Exception as e:
            return FirecrawlResult(
                url=url,
                content="",
                metadata={},
                success=False,
                error=str(e)
            )
        pass

        async def firecrawl_crawl'''

content = content.replace(old, new)

with open(r'D:\Composio Assignment\composio-app-research\agent\researcher.py', 'w') as f:
    f.write(content)

print('Added pass statement')