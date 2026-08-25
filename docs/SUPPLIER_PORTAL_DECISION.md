# Hosted supplier portal decision

## Status

**DEFERRED — external offline validation gate not yet met.**

BidLint 1.2 will not add a hosted supplier portal, supplier accounts, authentication, hosted evidence storage, or browser submission API before the offline supplier-clarification workflow is validated with a real external supplier response.

This is a product-scope gate, not a technical limitation.

## Current evidence

The supplier collaboration workflow already has the core product path needed for an external pilot:

1. deterministic clarification register;
2. self-contained offline supplier response form;
3. structured supplier response JSON;
4. buyer-side response ingestion with source provenance and mandatory human re-review;
5. explicit human evidence-adequacy assessment;
6. immutable revision history and conflict surfacing.

A real ASTM A182 F317L / material-offer clarification form has been dispatched externally. Until a supplier completes and returns the form and the buyer-side review path is exercised end-to-end, a hosted portal would add operational surface before the interaction model is validated.

## Why hosting is deferred

A portal would introduce product and security decisions that are not required to validate the core workflow:

- supplier identity and account lifecycle;
- authentication and recovery;
- tenant/project authorization;
- invitation expiry and link sharing;
- upload/storage retention policy;
- malware and unsafe-file handling;
- confidentiality and data residency;
- audit logging and evidence immutability;
- notification and reminder behavior;
- legal/contractual submission acknowledgement;
- hosting, availability, backup, and incident response.

Building these before validating the supplier interaction would risk hardening the wrong UX and data contract.

## Offline pilot hardening

Newly generated offline supplier forms include `source_register_sha256`, the canonical SHA-256 of the clarification register from which the form was generated. Buyer-side ingestion verifies that digest when present.

The first external pilot form predates this optional digest. Its returned response remains supported through the existing fail-closed structural binding of specification, vendor, requirement ID, category, parameter, and prior finding status. The pilot therefore does not need to be restarted or reissued only for this hardening change.

## Portal decision gate

Revisit hosted scope only after at least one real external supplier response completes the following path:

- supplier can understand and complete the offline form without guided data re-entry;
- response JSON returns through the normal project communication channel;
- buyer ingestion binds the response to the intended clarification register;
- buyer can assess certificate/test/calculation/supporting-document adequacy;
- at least one revision or correction can be represented without overwriting history, if a revision occurs;
- usability issues and missing fields are recorded from the real interaction.

## Scope if the gate passes

The first hosted version should be deliberately narrow:

- invitation-token access to a single clarification package;
- no general supplier marketplace or supplier master-data system;
- same response contract as the offline form;
- same provenance, evidence-review, and revision-history contracts on the buyer side;
- project-controlled evidence upload with explicit retention rules;
- append-only audit events;
- buyer-visible submission state and superseded revisions;
- zero automatic compliance acceptance.

The hosted layer should transport and manage the validated workflow, not replace the deterministic BidLint evaluator or invent a second set of supplier-response semantics.

## Decision rule

Until the external offline pilot is completed, the product decision is **do not build the hosted portal**. Continue strengthening the offline contract and buyer review path, then use real supplier behavior to determine whether hosting removes meaningful friction and which portal features are actually necessary.
