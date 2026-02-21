import asyncio
import json
import random

async def simulate_remediation(service_name: str, incident_summary: str):
    """Yields simulated terminal log lines for fixing an incident."""
    logs = [
        f"Initializing Strands Action Agent...",
        f"Targeting cluster for service: {service_name}",
        f"Parsing remediation plan from consensus...",
        f"Plan recognized. Establishing SSH tunnel to production bastion...",
        f"Tunnel established. Authenticating via short-lived certificate...",
        f"Access granted. Retrieving current deployment state...",
        f"Executing primary remediation steps for {service_name}...",
    ]
    
    # generate some random looking hash updates
    for i in range(1, 4):
        logs.append(f"Applying configuration patch ({i}/3): {random.randbytes(4).hex()}...")
    
    logs.extend([
        f"Waiting for pods to cycle and health checks to pass...",
        f"Health checks passing. Verifying error rates...",
        f"Remediation successfully applied to {service_name}.",
        f"Closing connections and revoking certificates.",
        "[DONE]"
    ])

    for log in logs:
        # random jitter to feel like a real terminal stream
        await asyncio.sleep(random.uniform(0.4, 1.2))
        yield log
