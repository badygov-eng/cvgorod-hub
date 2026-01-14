"""
API endpoint tests for cvgorod-hub.
"""



class TestHealth:
    """Tests for health endpoint."""
    
    def test_health_returns_ok(self, client):
        """Health endpoint should return ok status."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "cvgorod-hub"


class TestMessagesAPI:
    """Tests for /api/v1/messages endpoints."""
    
    def test_messages_requires_auth(self, client):
        """Messages endpoint should require API key."""
        response = client.get("/api/v1/messages")
        assert response.status_code == 401
    
    def test_messages_stats_requires_auth(self, client):
        """Stats endpoint should require API key."""
        response = client.get("/api/v1/messages/stats/total")
        assert response.status_code == 401


class TestClientsAPI:
    """Tests for /api/v1/clients endpoints."""
    
    def test_clients_requires_auth(self, client):
        """Clients endpoint should require API key."""
        response = client.get("/api/v1/clients")
        assert response.status_code == 401


class TestIntentsAPI:
    """Tests for /api/v1/intents endpoints."""
    
    def test_intents_requires_auth(self, client):
        """Intents endpoint should require API key."""
        response = client.get("/api/v1/intents")
        assert response.status_code == 401


class TestSandboxAPI:
    """Tests for /api/v1/send endpoints."""
    
    def test_send_requires_auth(self, client):
        """Send endpoint should require API key."""
        response = client.post("/api/v1/send", json={
            "chat_id": 123,
            "text": "test message"
        })
        assert response.status_code == 401
    
    def test_pending_requires_auth(self, client):
        """Pending endpoint should require API key."""
        response = client.get("/api/v1/sandbox/pending")
        assert response.status_code == 401
