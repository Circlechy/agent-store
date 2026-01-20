# CodyFix - Agentic AI CI/CD Workflow

An intelligent automation system that monitors Jenkins pipelines, analyzes test failures, and automatically generates and applies code fixes.

## Overview

This project implements an agentic AI workflow that autonomously handles the CI/CD debugging cycle. CodyFix, a conversational chat agent, orchestrates four specialized workflows to transform failed Jenkins builds into passing ones with minimal human intervention.

## Architecture

![Architecture Diagram](architecture.png)

## Workflows

### 1. GetJenkinsJobsSummary

Retrieves and analyzes the latest Jenkins build logs.

**Responsibilities:**
- Fetches recent job execution logs from Jenkins API
- Parses test results and build outputs
- Categorizes tests into successful and failed groups
- Generates a structured summary report

**Output:** A summary distinguishing between passed and failed tests, including failure details and stack traces.

### 2. FailedJobsFixRecommendations

Analyzes failed tests and generates actionable fix recommendations.

**Responsibilities:**
- Receives failed test details from the summary workflow
- Analyzes error messages, stack traces, and test context
- Identifies root causes of failures
- Generates specific, actionable fix recommendations

**Output:** Detailed recommendations for each failed test, including suggested code changes and affected files.

### 3. WriteCodeFixes

Applies the recommended fixes to the codebase.

**Responsibilities:**
- Takes fix recommendations as input
- Applies code changes to the repository
- Commits and pushes the fixes

**Output:** Applied code fixes committed to the repository.

### 4. TriggerJenkinsBuild

Triggers a new Jenkins build to validate the applied fixes.

**Responsibilities:**
- Initiates a new Jenkins build via API
- Monitors build trigger status

**Output:** A newly triggered Jenkins job to validate the changes.

## CodyFix Chat Agent

The system is controlled through CodyFix, a conversational chat agent that serves as the main interface.

**Capabilities:**
- Accepts natural language commands
- Routes requests to the appropriate workflow
- Provides status updates and summaries
- Allows manual intervention at any stage

**Example Interactions:**

```
User: Check the latest Jenkins jobs
CodyFix: Running GetJenkinsJobsSummary...
         Found 15 tests: 12 passed, 3 failed.
         Failed tests: TestUserAuth, TestPaymentFlow, TestDataSync

User: Recommend a fix for the failed tests
CodyFix: I'll get fix recommendations for the failed jobs...

User: Fix the code according to the recommendations
CodyFix: I'll fix the code according to the recommendations...

User: Trigger Jenkins jobs
CodyFix: I'll trigger the Jenkins job for you.
         Summary: Successfully triggered Jenkins job.
         The job has been queued with response code 201.
```

## Workflow Pipeline

The complete automated cycle:

1. **Trigger** — CodyFix receives request to check Jenkins status
2. **Summarize** — GetJenkinsJobsSummary fetches and categorizes test results
3. **Analyze** — FailedJobsFixRecommendations examines failures and proposes solutions
4. **Fix** — WriteCodeFixes applies changes to the codebase
5. **Rebuild** — TriggerJenkinsBuild initiates a new Jenkins build
6. **Validate** — Monitor the new build results
7. **Repeat** — If failures persist, the cycle can repeat with refined fixes

## Getting Started

### Prerequisites

- Jiuwen instance for workflow orchestration
- Access to Jenkins API with appropriate credentials
- Repository write access for applying fixes

### Configuration

1. Set up Jenkins API credentials
2. Configure repository access tokens
3. Deploy the four workflows to your Jiuwen instance
4. Connect CodyFix to the workflow endpoints
5. under backend/proxy run `npm start`
6. under backend/file_services run `uvicorn fileservice:app --reload --host [host ip] --port 1080`

### Usage

Start a conversation with CodyFix and use natural language to:

- Check current Jenkins build status
- Get details on specific failures
- Request automatic fixes
- Monitor fix progress
