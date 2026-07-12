# Integrations

Shared platform services providing reusable capabilities across different employees (e.g., Gmail, Slack, HubSpot).

**Principles:**
- Integrations are independent of specific employees. They act as generic clients for external APIs.
- They handle OAuth tokens and direct interactions.
- The `runtime` leverages these integrations based on an employee's configuration.
