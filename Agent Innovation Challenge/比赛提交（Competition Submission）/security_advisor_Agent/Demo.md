## Demo Use case



### Intent-Aware Database Security Agent (openGauss)



#### Overview



This project demonstrates an AI security agent for openGauss that infers user intent, detects GDPR-relevant risk, and decides when human approval is required, using openGauss native security labels.



Unlike traditional database firewalls or static allowlists, the agent:

* Learns normal behavior per database role from historical queries
* Reasons about what data is being accessed, not just SQL syntax
* Uses openGauss resource labels as the semantic source of truth
* Escalates to Human-in-the-Loop (HITL) when access is risky or ambiguous
* 

**The result is an explainable, adaptive, and DB-native security control.**





#### Why openGauss



openGauss supports resource security labels at the schema, table, and column levels.

These labels express the semantic type of data (e.g. PII, PCI, secrets) directly inside the database.



This project leverages that capability by:

* Reading labels from openGauss system catalogs
* Using labels to evaluate GDPR risk and intent
* Aligning AI decisions with existing openGauss security mechanisms (audit, masking, policy)



This avoids external data classification heuristics and keeps enforcement inside the database trust boundary.





#### GDPR-Oriented Data Model



The demo database represents a simplified EU SaaS platform.



##### Tables

**customers**

Customer identity information.

* Email, name, phone → labeled as pii\_raw
* Country code → labeled as pii\_low



**auth\_accounts**

Authentication data.

* Password hash, MFA secret → labeled as auth\_secret



**payments**

Billing and financial data.

* Card token → labeled as pci
* Card last four digits → low sensitivity



**support\_tickets**

Customer-generated free-text.

* Message column → labeled as free\_text\_pii



usage\_events

Behavioral and analytics data.

* Entire table labeled as behavioral





#### Roles in the Demo



###### analytics\_user — Data Analytics



**Purpose**

* Analyze product usage and customer behavior.



**GDPR principle**

Purpose limitation — analytics access does not justify identity data access.



**Expected behavior**

* Read-only aggregate queries
* Access to usage\_events
* Business-hour activity



**What the agent learns**

* Only behavioral data is accessed
* No PII or free-text access
* Stable query patterns



**Escalation triggers**

* Access to pii\_raw, pci, or free\_text\_pii
* Bulk customer exports
* Schema reconnaissance





###### billing\_service — Automated Billing



**Purpose**

* Process subscriptions and payments.



**GDPR principle**

Lawful processing \& accountability — automation does not imply unrestricted access.



**Expected behavior**

* Automated, batch-style queries
* Access to payments and limited customer identifiers
* Night-time execution



**What the agent learns**

* Consistent access to pci-labeled data
* No exploratory or interactive queries



**Escalation triggers**

* Access to customer PII (email, name)
* Access to support tickets or free-text data
* Daytime interactive queries or schema discovery



##### support\_agent (secondary role)



Handles customer support tickets with per-customer scope and limited data access.



