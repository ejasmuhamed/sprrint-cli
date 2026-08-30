from sprrint.mcp_server import mcp


def test_mcp_server_loads():
    assert mcp.name == 'sprrint'
    tools = getattr(mcp, '_tool_manager').list_tools()
    names = {tool.name for tool in tools}
    assert 'sprrint_now' in names
    assert 'sprrint_tasks_create' in names
    assert 'sprrint_blackhole_pull' in names
    assert 'sprrint_workspace_invite' in names
    assert len(names) >= 30
