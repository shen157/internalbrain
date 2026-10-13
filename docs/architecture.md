# InternalBrain Architecture and Trust Boundaries

## Design objective

InternalBrain provides unified enterprise question answering without allowing restricted content to enter retrieval results, LLM prompts, citations, or user-visible metadata. Authorization is evaluated at query time against the current permission state and occurs before retrieval.

## System context

~~~mermaid
flowchart LR
    USER[Enterprise User] --> UI[Streamlit Frontend]
    REVIEWER[Compliance Reviewer] --> UI
    UI -->|HTTP JSON| API[FastAPI Backend]

    API --> DATA[Bundled Source-Shaped Data]
    API --> LLM[Tencent TokenHub]
    API --> AUDIT[Local SHA-256 Audit Log]

    subgraph DATA[Enterprise Knowledge Sources - Synthetic]
        CONF[Confluence]
        JIRA[Jira]
        SLACK[Slack]
        DRIVE[Google Drive]
    end
~~~

The bundled records simulate source-native data and permission structures. They do not contain real company data or credentials.

## Query path

~~~mermaid
flowchart TB
    Q[Question plus Acting User] --> INPUT[Input Safety]
    INPUT -->|blocked| DENY[Safe Non-Disclosing Response]
    INPUT -->|allowed| ID[Resolve User and Groups]
    ID --> AUTH[Query-Time Permission Evaluation]
    AUTH --> POOL[Authorized Resource Pool]
    POOL --> BM25[BM25 Lexical Retrieval]
    POOL --> MINI[MiniLM Semantic Retrieval]
    BM25 --> RRF[Weighted Reciprocal Rank Fusion]
    MINI --> RRF
    RRF --> CONTENT[Retrieved-Content Safety]
    CONTENT -->|blocked| DENY
    CONTENT -->|allowed| CTX[Context and Citation Assembly]
    CTX --> MODEL[Tencent TokenHub LLM]
    MODEL --> CITE[Citation Validation]
    CITE --> OUTPUT[Output Safety]
    OUTPUT -->|valid| ANSWER[Grounded Answer and Citations]
    OUTPUT -->|unsafe or insufficient| DENY

    Q -. event .-> AUDIT[SHA-256 Chained Audit Trail]
    INPUT -. event .-> AUDIT
    AUTH -. event .-> AUDIT
    RRF -. event .-> AUDIT
    MODEL -. event .-> AUDIT
    OUTPUT -. event .-> AUDIT
~~~

### Security invariant

The permission engine filters the resource pool before BM25 or semantic ranking. The LLM receives only authorized, safety-checked context. There is no global retrieval followed by post-hoc permission filtering.

## Data and permission path

~~~mermaid
flowchart LR
    subgraph Sources
        C[Confluence Pages and Restrictions]
        J[Jira Issues, Roles, and Security]
        S[Slack Channels and Membership]
        G[Drive Files, Folders, and Permissions]
    end

    C --> CONN[Source Connectors]
    J --> CONN
    S --> CONN
    G --> CONN
    CONN --> URM[Unified Resource Model]
    URM --> INDEX[Lexical and Semantic Retrieval State]

    USERS[Users and Groups] --> STORE[Permission Store]
    C --> STORE
    J --> STORE
    S --> STORE
    G --> STORE
    STORE --> ENGINE[Permission Engine]
    ENGINE --> INDEX
~~~

Permissions remain logically separate from content indexing. A permission update changes the authorized view used by the next query without requiring the resource content to be re-embedded.

## Live permission-change path

~~~mermaid
sequenceDiagram
    participant E as Elena / Compliance Officer
    participant UI as Streamlit
    participant API as FastAPI
    participant PS as Permission Store
    participant PE as Permission Engine
    participant R as Retrieval
    participant A as Audit Trail

    E->>UI: Grant David access to C-PAY
    UI->>API: POST membership change plus reviewer identity
    API->>API: Verify compliance-officer role
    API->>PS: Apply membership change
    PS-->>PE: New permission state is available
    API->>A: Record actor, target, resource, action, result
    API-->>UI: Success, audit event ID, no re-index required
    E->>UI: Test the same query as David
    UI->>API: POST query
    API->>PE: Evaluate current C-PAY membership
    PE->>R: Supply authorized resources only
    R-->>UI: C-PAY citation is now available
~~~

The recorded grant-to-retrievable p95 is 447 ms inside InternalBrain after receipt of the permission update. This is not a claim about upstream source-platform webhook latency.

## Audit design

Each audit event contains identifiers, timestamp, event type, action, selected decision details, previous hash, and current hash. The current hash is calculated over a canonical representation of the event and its previous-hash pointer.

~~~text
GENESIS
   -> Event 1 hash
   -> Event 2 includes Event 1 hash
   -> Event 3 includes Event 2 hash
   -> ...
~~~

Changing or removing an earlier event breaks verification. The evaluation suite verifies both a valid chain and deliberate tampering.

## Trust boundaries

### Browser and Streamlit boundary

The UI presents acting-user choices for the demo and never performs permission filtering locally. Answers, citations, audit results, and permission status come from backend responses.

### Backend authorization boundary

FastAPI is the enforcement point for reviewer-only operations and validates the acting user's role. UI hiding is only a usability layer; direct requests from ordinary users receive HTTP 403.

### Enterprise data boundary

Connectors normalize source-specific records and permission metadata into the unified resource model. The repository uses synthetic local datasets, while a production version would authenticate to real enterprise sources.

### Remote model boundary

Only authorized, safety-checked context is transmitted to Tencent TokenHub. The API key is loaded from the untracked .env file and must never be committed.

### Audit boundary

The audit chain is stored locally in the prototype. It is tamper-evident but not externally immutable. A production system should ship events to access-controlled, append-only storage.

## Failure behavior

| Condition | System behavior |
|---|---|
| Prompt-injection input | Block before retrieval and LLM invocation |
| No authorized resources | Generic abstention; LLM not called |
| Authorized but irrelevant context | Model may assess context, then generic abstention |
| Malicious retrieved instruction | Block during retrieved-content safety |
| Invalid citation | Reject or abstain instead of presenting an unsupported citation |
| Potential secret in output | Block during output safety |
| Ordinary user calls reviewer endpoint | HTTP 403 |
| Audit chain altered | Verification reports invalid chain |

## Prototype boundaries

- Demo identity uses the X-InternalBrain-Actor header rather than production SSO.
- Synchronization is manually triggered rather than webhook-driven.
- Included source data is synthetic and loaded locally.
- Latency measurements are benchmark evidence, not production SLAs.
- The local audit file is not a substitute for an external immutable audit service.

