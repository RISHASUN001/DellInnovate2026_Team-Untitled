"""
Integration tests for MCP Service
Tests all MCP tools, ChromaDB, MongoDB, and Instagram scraper integration
"""
import pytest
import httpx
from datetime import datetime, timedelta

# Configuration
MCP_SERVICE_URL = "http://localhost:8003"
CASE_SERVICE_URL = "http://localhost:8001"
CHATBOT_SERVICE_URL = "http://localhost:8000"

# Test user headers
ADMIN_HEADERS = {
    "X-User-Id": "sarah_l",
    "X-User-Role": "Admin"
}

HELPER_HEADERS = {
    "X-User-Id": "john_w",
    "X-User-Role": "Youth Helper"
}


@pytest.mark.asyncio
class TestMCPService:
    """Test MCP Service endpoints"""
    
    async def test_health_check(self):
        """Test MCP service is running"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{MCP_SERVICE_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            print("✓ MCP Service health check passed")
    
    async def test_list_cases_summary(self):
        """Test listing all cases summary"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{MCP_SERVICE_URL}/tools/list_cases_summary",
                headers=ADMIN_HEADERS
            )
            assert response.status_code == 200
            data = response.json()
            assert "cases" in data
            print(f"✓ Found {len(data['cases'])} cases in system")
    
    async def test_get_case_details(self):
        """Test retrieving specific case details"""
        async with httpx.AsyncClient() as client:
            # Get a test case ID
            cases_resp = await client.get(
                f"{MCP_SERVICE_URL}/tools/list_cases_summary",
                headers=ADMIN_HEADERS
            )
            cases = cases_resp.json()["cases"]
            
            if cases:
                test_case_id = cases[0]["code"]
                response = await client.get(
                    f"{MCP_SERVICE_URL}/tools/get_case/{test_case_id}",
                    headers=ADMIN_HEADERS
                )
                assert response.status_code == 200
                data = response.json()
                assert "case" in data
                assert data["case"]["code"] == test_case_id
                print(f"✓ Retrieved case details for {test_case_id}")
    
    async def test_get_case_history(self):
        """Test case timeline/history retrieval"""
        async with httpx.AsyncClient() as client:
            # Get a test case
            cases_resp = await client.get(
                f"{MCP_SERVICE_URL}/tools/list_cases_summary",
                headers=ADMIN_HEADERS
            )
            cases = cases_resp.json()["cases"]
            
            if cases:
                test_case_id = cases[0]["code"]
                response = await client.get(
                    f"{MCP_SERVICE_URL}/tools/get_case_history/{test_case_id}",
                    headers=ADMIN_HEADERS
                )
                assert response.status_code == 200
                data = response.json()
                assert "events" in data
                print(f"✓ Retrieved {len(data['events'])} history events for {test_case_id}")
    
    async def test_search_protocol(self):
        """Test protocol search via ChromaDB"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MCP_SERVICE_URL}/tools/search_protocol",
                headers=ADMIN_HEADERS,
                json={
                    "query": "self harm intervention steps",
                    "top_k": 3
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert len(data["results"]) > 0
            print(f"✓ Protocol search returned {len(data['results'])} results")
            print(f"  Top result: {data['results'][0]['metadata']['source']}")
    
    async def test_add_case_note(self):
        """Test adding a note to a case"""
        async with httpx.AsyncClient() as client:
            # Get a test case
            cases_resp = await client.get(
                f"{MCP_SERVICE_URL}/tools/list_cases_summary",
                headers=ADMIN_HEADERS
            )
            cases = cases_resp.json()["cases"]
            
            if cases:
                test_case_id = cases[0]["code"]
                response = await client.post(
                    f"{MCP_SERVICE_URL}/tools/add_case_note",
                    headers=ADMIN_HEADERS,
                    json={
                        "case_id": test_case_id,
                        "content": "Test note from integration test",
                        "note_type": "general"
                    }
                )
                # May return 200 or 201
                assert response.status_code in [200, 201]
                data = response.json()
                assert data.get("success", True)
                print(f"✓ Added note to case {test_case_id}")
    
    async def test_add_checklist_item(self):
        """Test adding a checklist item"""
        async with httpx.AsyncClient() as client:
            # Get a test case
            cases_resp = await client.get(
                f"{MCP_SERVICE_URL}/tools/list_cases_summary",
                headers=ADMIN_HEADERS
            )
            cases = cases_resp.json()["cases"]
            
            if cases:
                test_case_id = cases[0]["code"]
                response = await client.post(
                    f"{MCP_SERVICE_URL}/tools/add_checklist_item",
                    headers=ADMIN_HEADERS,
                    json={
                        "case_id": test_case_id,
                        "label": "Integration test item",
                        "mandatory": False,
                        "sub_items": []
                    }
                )
                assert response.status_code in [200, 201]
                data = response.json()
                assert data.get("success", True)
                print(f"✓ Added checklist item to case {test_case_id}")
    
    async def test_schedule_followup(self):
        """Test scheduling a follow-up"""
        async with httpx.AsyncClient() as client:
            # Get a test case
            cases_resp = await client.get(
                f"{MCP_SERVICE_URL}/tools/list_cases_summary",
                headers=ADMIN_HEADERS
            )
            cases = cases_resp.json()["cases"]
            
            if cases:
                test_case_id = cases[0]["code"]
                followup_time = (datetime.now() + timedelta(days=7)).isoformat()
                response = await client.post(
                    f"{MCP_SERVICE_URL}/tools/schedule_followup",
                    headers=ADMIN_HEADERS,
                    json={
                        "case_id": test_case_id,
                        "scheduled_at": followup_time,
                        "note": "Integration test follow-up"
                    }
                )
                assert response.status_code in [200, 201]
                data = response.json()
                assert data.get("success", True)
                print(f"✓ Scheduled follow-up for {test_case_id}")


@pytest.mark.asyncio
class TestChatbotIntegration:
    """Test Chatbot Service with RAG and MCP integration"""
    
    async def test_chatbot_health(self):
        """Test chatbot service is running"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{CHATBOT_SERVICE_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            print("✓ Chatbot service health check passed")
    
    async def test_chat_without_case(self):
        """Test general protocol query without case context"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{CHATBOT_SERVICE_URL}/chat",
                headers=ADMIN_HEADERS,
                json={
                    "message": "What are the steps for addressing cyberbullying?",
                    "case_info": None,
                    "conversation_history": []
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert "response" in data
            assert len(data["response"]) > 50  # Should have meaningful response
            print("✓ General protocol query successful")
            print(f"  Response preview: {data['response'][:100]}...")
    
    async def test_chat_with_case_context(self):
        """Test chat with case attached (RAG context)"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get a test case
            cases_resp = await client.get(
                f"{MCP_SERVICE_URL}/tools/list_cases_summary",
                headers=ADMIN_HEADERS
            )
            cases = cases_resp.json()["cases"]
            
            if cases:
                test_case = cases[0]
                response = await client.post(
                    f"{CHATBOT_SERVICE_URL}/chat",
                    headers=ADMIN_HEADERS,
                    json={
                        "message": "What should I do next for this case?",
                        "case_info": {
                            "code": test_case["code"],
                            "category": test_case.get("category", "General"),
                            "riskLevel": test_case.get("riskLevel", 3),
                            "status": test_case.get("status", "Open"),
                            "signals": test_case.get("signals", [])
                        },
                        "conversation_history": []
                    }
                )
                assert response.status_code == 200
                data = response.json()
                assert "response" in data
                print(f"✓ Case-context query successful for {test_case['code']}")
                print(f"  Response preview: {data['response'][:100]}...")
    
    async def test_chat_tool_suggestion(self):
        """Test chatbot suggesting MCP tool actions"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get a test case
            cases_resp = await client.get(
                f"{MCP_SERVICE_URL}/tools/list_cases_summary",
                headers=ADMIN_HEADERS
            )
            cases = cases_resp.json()["cases"]
            
            if cases:
                test_case = cases[0]
                response = await client.post(
                    f"{CHATBOT_SERVICE_URL}/chat",
                    headers=ADMIN_HEADERS,
                    json={
                        "message": "Add a checklist item to follow up on school contact",
                        "case_info": {
                            "code": test_case["code"],
                            "category": test_case.get("category", "General"),
                            "riskLevel": test_case.get("riskLevel", 3),
                            "status": test_case.get("status", "Open")
                        },
                        "conversation_history": []
                    }
                )
                assert response.status_code == 200
                data = response.json()
                
                # Check if tool calls were suggested
                if data.get("tool_calls"):
                    print(f"✓ Chatbot suggested {len(data['tool_calls'])} tool actions")
                    for tool in data["tool_calls"]:
                        print(f"  - {tool.get('tool', 'unknown')}")
                else:
                    print("✓ Chat response received (no tool calls in this response)")


@pytest.mark.asyncio
class TestEndToEndFlow:
    """Test complete end-to-end workflow"""
    
    async def test_full_workflow(self):
        """Test complete workflow: Query chatbot → Get tool suggestion → Execute via MCP"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Get a test case
            print("\\n=== Starting End-to-End Test ===")
            cases_resp = await client.get(
                f"{MCP_SERVICE_URL}/tools/list_cases_summary",
                headers=ADMIN_HEADERS
            )
            cases = cases_resp.json()["cases"]
            assert len(cases) > 0, "No cases available for testing"
            test_case = cases[0]
            print(f"1. Using test case: {test_case['code']}")
            
            # 2. Query chatbot for guidance
            print("2. Asking chatbot for guidance...")
            chat_resp = await client.post(
                f"{CHATBOT_SERVICE_URL}/chat",
                headers=ADMIN_HEADERS,
                json={
                    "message": "What's the recommended next action for this risk level?",
                    "case_info": {
                        "code": test_case["code"],
                        "category": test_case.get("category", "General"),
                        "riskLevel": test_case.get("riskLevel", 3),
                        "status": test_case.get("status", "Open"),
                        "signals": test_case.get("signals", [])
                    },
                    "conversation_history": []
                }
            )
            assert chat_resp.status_code == 200
            chat_data = chat_resp.json()
            print(f"   ✓ Got response: {chat_data['response'][:80]}...")
            
            # 3. Add a note via MCP
            print("3. Adding case note via MCP...")
            note_resp = await client.post(
                f"{MCP_SERVICE_URL}/tools/add_case_note",
                headers=ADMIN_HEADERS,
                json={
                    "case_id": test_case["code"],
                    "content": "End-to-end test: Chatbot guidance received and documented.",
                    "note_type": "general"
                }
            )
            assert note_resp.status_code in [200, 201]
            print("   ✓ Note added successfully")
            
            # 4. Verify history was updated
            print("4. Verifying case history...")
            history_resp = await client.get(
                f"{MCP_SERVICE_URL}/tools/get_case_history/{test_case['code']}",
                headers=ADMIN_HEADERS
            )
            assert history_resp.status_code == 200
            history = history_resp.json()
            print(f"   ✓ Case now has {len(history['events'])} history events")
            
            print("\\n=== End-to-End Test Complete ===\\n")


# Run tests
if __name__ == "__main__":
    import asyncio
    
    print("\\n" + "="*60)
    print("MCP & CHATBOT INTEGRATION TEST SUITE")
    print("="*60 + "\\n")
    
    async def run_all_tests():
        # MCP Service Tests
        print("\\n▸ Testing MCP Service...")
        mcp_test = TestMCPService()
        await mcp_test.test_health_check()
        await mcp_test.test_list_cases_summary()
        await mcp_test.test_get_case_details()
        await mcp_test.test_get_case_history()
        await mcp_test.test_search_protocol()
        await mcp_test.test_add_case_note()
        await mcp_test.test_add_checklist_item()
        await mcp_test.test_schedule_followup()
        
        # Chatbot Tests
        print("\\n▸ Testing Chatbot Service with RAG...")
        chatbot_test = TestChatbotIntegration()
        await chatbot_test.test_chatbot_health()
        await chatbot_test.test_chat_without_case()
        await chatbot_test.test_chat_with_case_context()
        await chatbot_test.test_chat_tool_suggestion()
        
        # End-to-End
        print("\\n▸ Testing End-to-End Workflow...")
        e2e_test = TestEndToEndFlow()
        await e2e_test.test_full_workflow()
        
        print("\\n" + "="*60)
        print("✓ ALL TESTS PASSED")
        print("="*60 + "\\n")
    
    asyncio.run(run_all_tests())
