# Force Deploy - Aug 26 2025

Classification rules and rental contracts endpoints ARE working locally but not in production.

Local test shows all endpoints present:
- /classification-rules/ ✅
- /rental-contracts/ ✅
- /mortgage-details/ ✅

Production shows 405 errors for classification-rules and rental-contracts.

This deployment forces a full redeploy of the backend.