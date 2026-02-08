<!-- 
CodyFix Agent README
-->

# CodyFix

**[GitCode Repository](https://gitcode.com/nizzan/CodyFix)**

## Feature Introduction

CodyFix is an AI-powered CI/CD assistant that automates the Jenkins debugging cycle. Instead of manually investigating failed builds, developers interact with CodyFix through natural language to:

- **Check build status** — Get instant summaries of passed and failed tests
- **Analyze failures** — Receive AI-generated root cause analysis and fix recommendations
- **Apply fixes** — Automatically write code changes to the repository
- **Trigger rebuilds** — Start new Jenkins builds to validate fixes

The system is designed with a human-in-the-loop approach — each step requires user confirmation, giving developers full control over the resolution process.

## Quick Start

### Prerequisites

- Jiuwen instance for workflow orchestration
- Jenkins API access with appropriate credentials
- Repository write access

### Installation

1. Deploy the backend services:

```bash
# Start HTTP Proxy (Node.js)
cd proxy
npm install
npm start

# Start File Service (Python)
cd fileservice
pip install fastapi uvicorn
uvicorn fileservice:app --host 0.0.0.0 --port 8000
```

2. Import the four workflows into your Jiuwen instance:
   - GetJenkinsJobsSummary
   - FailedJobsFixRecommendations
   - WriteCodeFixes
   - TriggerJenkinsBuild

3. Configure environment variables:

```bash
# Proxy
PORT=3000

# File Service
BASE_FOLDER=/var/lib/jenkins/workspace/your-project/
REMOTE_SERVER=your.server.ip
REMOTE_USER=jenkins
```

4. Connect CodyFix chat agent to workflow endpoints

### Usage

```
User: Check the latest Jenkins jobs
CodyFix: Found 15 tests: 12 passed, 3 failed.
         Failed tests: TestUserAuth, TestPaymentFlow, TestDataSync

User: Recommend a fix for the failed tests
CodyFix: I'll get fix recommendations for the failed jobs...

User: Fix the code according to the recommendations
CodyFix: I'll fix the code according to the recommendations...

User: Trigger Jenkins jobs
CodyFix: Successfully triggered Jenkins job. Response code 201.
```

## Key Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| Workflow Orchestration | OpenJiuwen | Orchestrates the four modular workflows |
| Chat Agent | LLM-based | Natural language interface for user interaction |
| HTTP Proxy | Node.js | Bridges workflows to Jenkins API |
| File Service | Python FastAPI | Manages file read/write operations via SSH |
| CI/CD | Jenkins | Build and test execution |

## Architecture

![Architecture](architecture.png)

The system follows a modular design — each workflow is independent and can be used standalone or combined. This LEGO-like architecture enables:

- **Flexibility** — Use one workflow or all four
- **Reusability** — Plug workflows into other projects
- **Maintainability** — Update components independently

## Backend Architecture

![Backend Architecture](backend_architecture.png)

The backend consists of two lightweight services:

- **Proxy URL (Node.js)** — Handles all communication with Jenkins (trigger jobs, get build logs, get job status)
- **File Services (Python/Uvicorn)** — Manages file operations (get file content, write fixes to codebase)

## Workflows

| Workflow | Input | Output |
|----------|-------|--------|
| GetJenkinsJobsSummary | Jenkins job name | Test results summary (passed/failed) |
| FailedJobsFixRecommendations | Failed test details | AI-generated fix recommendations |
| WriteCodeFixes | Fix recommendations | Code changes committed to repo |
| TriggerJenkinsBuild | Job name | New build triggered |

## Authors

- [Nizzan Kimhi](https://gitcode.com/nizzan)
- [Amir Aharon](https://gitcode.com/aharonamir1)

## License

Apache License 2.0
