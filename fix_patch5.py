with open(r'D:\Composio Assignment\composio-app-research\agent\researcher.py', 'r') as f:
    content = f.read()

# Fix the orphaned except block in HTTPScraper.scrape
old = '''            return FirecrawlResult(
                url=url,
                content=content,
                metadata={"status_code": resp.status_code},
                success=True,
                error=None
            )
            except Exception as e:
                        return FirecrawlResult(
                        url=url,
                        content="",
                        metadata={},
                        success=False,
                        error=str(e)
                    )'''

new = '''            except Exception as e:
                return FirecrawlResult(
                    url=url,
                    content="",
                    metadata={},
                    success=False,
                    error=str(e)
                )
            
            return FirecrawlResult(
                url=url,
                content=content,
                metadata={"status_code": resp.status_code},
                success=True,
                error=None
            )'''

content = content.replace(old, new)

with open(r'D:\Composio Assignment\composio-app-research\agent\researcher.py', 'w') as f:
    f.write(content)

print('Fixed orphaned except block')