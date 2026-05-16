from main import mcp

if __name__ == "__main__":
    # Run the FastMCP server natively over stdio
    # This completely eliminates the need for HTTP, SSE, or running the server separately.
    mcp.run(transport="stdio")
