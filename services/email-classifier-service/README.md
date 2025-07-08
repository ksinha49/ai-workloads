# Email Classifier Service

This service monitors an email inbox, applies dynamic rules to incoming
messages and routes extracted data to the appropriate downstream workflow.

## Components

### Email Listener
Connects to the configured mail server and fetches new messages.  All
evaluation logic has been removed from this component.  Each email is
forwarded unchanged to the rules engine.

### Rules Engine & Parser
For every incoming message the engine queries the business rules database
for an active rule that matches the email's sender, subject or content.
When a rule matches, its `extractionMap` instructions are used to parse
the email and extract key data. The result is packaged into a JSON
object and delivered to the rule's destination such as an Appian
workflow, webhook or queue.

### Business Rules Database
Defines how to identify relevant emails, what data to extract and where
to send the results. Adding new rules enables new workflows without
updating the service code.

## Rule Schema
Rules are stored in the `email_classification_rules` table with the
fields below.  Values are JSON strings so that match criteria and
extraction logic remain flexible.

| Field           | Description                                                    |
|-----------------|----------------------------------------------------------------|
| `ruleName`      | Unique name describing the rule.                               |
| `priority`      | Numeric priority evaluated in ascending order.                 |
| `matchCriteria` | JSON map of conditions applied to the email.                   |
| `extractionMap` | JSON map of fields to extract using regex or other methods.    |
| `outputAction`  | JSON object describing where the parsed result should be sent. |

### Example
```json
{
  "ruleName": "Classify DocuSign New Account Form",
  "priority": 1,
  "matchCriteria": {"from": {"contains": "docusign.net"},
                     "subject": {"startsWith": "Completed: New Account"}},
  "extractionMap": {"envelopeId": {"source": "body",
                                     "regex": "Envelope ID: ([A-Z0-9]+)"}},
  "outputAction": {"type": "appian", "workflowId": "proc_model_12345"}
}
```

By adding another row to the table the service can classify invoices,
alerts or any other type of message.

## Local Testing
Build and run the container with Docker Compose:

```bash
docker compose build
docker compose up
```
