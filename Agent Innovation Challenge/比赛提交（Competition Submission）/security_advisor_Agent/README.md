# **🛡️ Sentinel: AI-Driven Database Security Guardrails**

**Automated "Least Privilege" Enforcement using openJiuwen \& DeepSeek**

## **📖 Overview**

**Sentinel** is an autonomous, dual-workflow security system designed to protect databases from unauthorized access and data leakage. Unlike static WAFs or manual RBAC policies, Sentinel uses Large Language Models (LLMs) to **reverse-engineer business intent** from user behavior and strictly enforce dynamic security contracts.

The system operates on a "Legislator vs. Police" model:

1. **The learn Users behavior (Workflow 1):** Periodically analyzes history to draft strict "Security Contracts" and Data Masking policies.
2. **The Batch Queries Enforcer (Workflow 2):** Continuously audits live traffic against these contracts in real-time.

## **🏗️ System Architecture**

### **🧠 Workflow 1: learn Users behavior(Policy Generator)**

This workflow acts as the "Legislator." It does not run on live traffic but analyzes historical data to define what *should* be allowed.

+-------+      +-----------------+      +---------------------+  
| Start | ---> | Data Aggregator | ---> | Check Roles Cache   |  
+-------+      +-----------------+      +---------------------+  
|  
v  
/--------------\\  
|  Has Roles?  |  
\\--------------/  
|          |  
(No)|          |(Yes)  
v          |  
+-----------------+       +----------------+   |  
| Save Roles      | <---- | LLM Definer    |   |  
+-----------------+       +----------------+   |  
|                                      |  
+-------------> +-----------------+ <--+  
|  Unifier Roles  |  
+-----------------+  
|  
v  
/------------------\\  
|  Has Contracts?  |  
\\------------------/  
|              |  
(No)|              |(Yes)  
v              |  
+-----------------+     +----------------+     |  
| Save Contracts  | <-- | LLM Architect  |     |  
+-----------------+     +----------------+     |  
|                                      |  
+-----------> +-----------------+ <----+  
|  Unifier Final  |  
+-----------------+  
|  
v  
+-----------------+  
| Masking Officer |  
+-----------------+  
|  
v  
+-----------------+  
|   Save Script   | ---> ( End )  
+-----------------+

**Core Logic Flow:**

1. **Data Ingestion (Data\_Aggregator)**:

   * Fetches the active **Database Schema** (tables, columns, sensitivity labels).
   * Fetches recent **Query Logs** to understand actual user behavior.

2. **Semantic Role Discovery (LLM\_Definer)**:

   * **Model:** DeepSeek Reasoner.
   * **Task:** Analyzes raw SQL to define high-level business roles (e.g., *"User bob is a Billing Clerk who needs SELECT access to invoices but UPDATE access only for status flags"*).
   * **Output:** Cached to /tmp/roles\_cache.json.

3. **Contract Engineering (LLM\_Architect)**:

   * **Model:** DeepSeek Reasoner.
   * **Task:** Maps the "Role Definition" to the "Schema" to create a rigorous **Security Contract**.
   * **Principle:** **Least Privilege**. If a role doesn't explicitly need a sensitive column (like ssn or password\_hash), it is whitelisted OUT.
   * **Output:** Cached to /tmp/contracts\_cache.json.

4. **Dynamic Masking (masking\_officer)**:

   * **Model:** DeepSeek Chat V3.2.
   * **Task:** Generates executable SQL (CREATE MASKING POLICY...) to dynamically obfuscate PII (Personally Identifiable Information) for specific roles at the database level.
   * **Note:** this component emphasize the abiliry of the LLM agent to learn new SQL syntax and use it
   * **Output:** Saved to /tmp/masking.sql.



### **👮 Workflow 2: The Enforcer (Runtime Audit)**

This workflow acts as the "Police." It runs on a tight loop (e.g., every 30s) to audit new queries against the laws defined by the Architect.

+-------+     +---------------------------+     +-----------------------+  
| Start | --> | Fetch Queries \& Contracts | --> | Batch Policy Enforcer |  
+-------+     +---------------------------+     +-----------------------+  
|  
v  
+--------------+  
( End ) <---------------------------- | Batch Logger |  
+--------------+

**Core Logic Flow:**

1. **Batch Ingestion (Fetch\_Queries\_And\_Contracts)**:

   * Retrieves new queries executed since the last checkpoint (Auto-Windowing).
   * Loads the latest **Security Contracts** from /tmp/contracts\_cache.json.

2. **Policy Enforcement (Batch\_Policy\_Enforcer)**:

   * **Model:** DeepSeek Chat V3.2 (Optimized for speed).
   * **Task:** Evaluates the batch of queries against the specific user's contract.
   * **Logic:**

     * Does the user have a contract? (If no → **BLOCK**).
     * Is the table/column allowed? (If no → **BLOCK**).
     * Is the operation (DROP, DELETE) allowed? (If no → **BLOCK**).

3. **Audit Logging (Batch\_Logger)**:

   * Writes structured decisions (ALLOW/BLOCK + Reason) to /tmp/sql\_security\_audit.log.

## **🚀 Key Features**

* **Self-Healing Security**: The system adapts. If a legitimate user starts using a new, necessary table, the Architect (on its next run) will update the contract, while the Enforcer blocks anomalies in the interim.
* **Context-Aware WAF**: Standard WAFs block based on Regex (e.g., DROP TABLE). Sentinel blocks based on **Identity + Intent**. A DBA *can* drop tables; a Web App *cannot*.
* **Automated Data Masking**: Goes beyond simple blocking by generating actual SQL code to mask sensitive data, ensuring compliance without breaking applications.
* **Offline Resilience**: The Enforcer relies on local cache files (/tmp/\*.json). Even if the Architect workflow is down or the LLM is slow, the Enforcer continues to police traffic using the last known good state.

## **🛠️ Usage Guide**

### **Prerequisites**

* **openJiuwen Platform** installed.
* **Log Server** running at http://192.168.3.157:8015 (Endpoints: /schema, /queries).
* **DeepSeek API Key** configured in openJiuwen model settings.

### **Step 1: Initialize Policies (The Architect)**

Run **Workflow 1** once to baseline your security.

1. **Import**: Load the **Architect Workflow** (DSL) into openJiuwen Studio.
2. **Execute**: Run the workflow manually.
3. **Verify**: Check /tmp/contracts\_cache.json to see the generated JSON policies.
4. **Apply**: Execute the SQL script found in /tmp/masking.sql on your database to enable masking.

### **Step 2: Start Monitoring (The Enforcer)**

Run **Workflow 2** on a schedule (Cron).

1. **Import**: Load the **Enforcer Workflow** (DSL) into openJiuwen Studio.
2. **Configure**: Set the trigger to run every **30 seconds**.
3. **Parameter**: Set timestamp="AUTO" (This enables the sliding window logic).

### **Step 3: View Audits**

Monitor the enforcement logs in real-time:

tail -f /tmp/sql\_security\_audit.log

**Sample Output:**

\[2026-01-15 14:20:01] \[ALLOW] User:analytics\_service | Reason: "Matched Contract: Monthly Reporting" | Query: SELECT count(\*) FROM sales...  
\[2026-01-15 14:20:05] \[BLOCK] User:web\_app | Reason: "Unauthorized Access: 'salary' column prohibited" | Query: SELECT salary FROM employees WHERE id=...

## **📂 File Manifest**

|Component|Description|
|-:|-:|
|**Learn\_users\_workflow-export.json**|DSL for Schema Analysis \& Contract Generation.|
|**batch\_workflow.json**|DSL for Runtime Query Auditing.|
|model\_outputs/contracts\_cache.json|The single source of truth for active security policies.|
|model\_outputs/roles\_cache.json|Semantic definitions of user roles (LLM memory).|
|model\_outputs/masking.sql|Generated SQL commands for Dynamic Data Masking.|
|database\_demo|Folder with the database schema, users and data that was used in the challenge|

## 

## **🔮 Future Work: what are the steps for production**

### 

1. ### **Scaling with Hierarchical Intelligence**

As organizational databases grow to thousands of tables and millions of daily queries, the current single-agent "Architect" approach faces a hard limit: the **Context Window**. To solve this, we propose moving to a **Hierarchical MapReduce Architecture**.

#### **The Problem: Context Saturation**

Currently, LLM\_Architect loads the *entire* database schema and *all* role behaviors into a single prompt. For enterprise-scale systems (e.g., ERPs with 5,000+ tables), this exceeds the token limit of even the largest context models, leading to "forgetful" policies or hallucinated permissions.

##### **The Solution: MapReduce Policy Generation**

We plan to refactor **Workflow 1 (The Architect)** into a multi-stage distributed process:

1. **Map Phase (Shard Analysis)**:

   * Decompose the Database Schema into logical domains (e.g., Finance\_Schema, HR\_Schema, Inventory\_Schema).
   * Spin up parallel "Sub-Architect" agents. Each agent receives only the logs and schema relevant to its specific domain.
   * *Output*: Micro-contracts (e.g., "Finance Policy for User Bob").

2. **Reduce Phase (Global Unification)**:

   * A "Chief Architect" agent aggregates the micro-contracts from all domains.
   * It performs conflict resolution (e.g., ensuring User Bob's clearance in HR doesn't violate SOD - Segregation of Duties - rules defined in Finance).
   * *Output*: A single, unified contracts\_cache.json.

### **2. Detection speed up**

#### **The Problem: LLM inference is slow**

In real production databases, the amount of queries per seconds can be huge, and LLM inference for each query is not practical as shown in the demo. there are several techniques that can be used:

1. **Caching** - if a decision is made for a single query and a user, there is no need to run workflow again, cache shall be used to preserve the decisions
2. **Filtering out safe queries** - filter out safe queries that are detected with simple mechanisms.
3. **Focus on potential dangerous queries** - risky queries come in different forms: accessing sensitive data, queries with large amount of records, delete and update without a where clause, data definition queries etc. The detection workflow can be used to focus on these queries and reduce the load from the agent to what really matter.

### 

### **Impact**

* **Infinite Scaling**: The system can handle schemas of any size by simply adding more parallel "Map" agents.
* **Faster Processing**: Domain analysis happens in parallel rather than serial.
* **Higher Accuracy**: Agents focus on smaller, clearer contexts, reducing hallucination rates.
